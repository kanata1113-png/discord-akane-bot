from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Awaitable, Callable, Mapping


class CapabilityRisk(str, Enum):
    """Execution-policy risk for a capability."""

    READ_ONLY = "READ_ONLY"
    WRITE_CONFIRM = "WRITE_CONFIRM"
    MODERATION = "MODERATION"
    ADMIN = "ADMIN"


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """Stable metadata for one user-addressable bot capability.

    ``risk`` describes authorization / confirmation policy. External model or
    service spend is tracked separately through ``incurs_external_cost`` so a
    non-destructive AI capability does not masquerade as a write/admin risk.
    """

    capability_id: str
    name: str
    description: str
    risk: CapabilityRisk
    category: str
    slash_command: str | None = None
    requires_confirmation: bool = False
    discoverable: bool = True
    incurs_external_cost: bool = False
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability_id or not self.capability_id.strip():
            raise ValueError("capability_id must not be empty")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if not self.category or not self.category.strip():
            raise ValueError("category must not be empty")
        if self.risk is not CapabilityRisk.READ_ONLY and not self.requires_confirmation:
            raise ValueError(
                f"{self.risk.value} capability must require confirmation"
            )


@dataclass(frozen=True, slots=True)
class CapabilityContext:
    """Runtime context supplied to a capability handler.

    The core deliberately carries IDs and optional interaction metadata only.
    Authorization remains the responsibility of Discord-facing policy/handlers.
    """

    user_id: int
    guild_id: int | None = None
    channel_id: int | None = None
    interaction: Any | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class CapabilityRequest:
    capability_id: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    confirmed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "arguments",
            MappingProxyType(dict(self.arguments)),
        )


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    capability_id: str
    ok: bool
    value: Any = None
    message: str | None = None


CapabilityHandler = Callable[
    [CapabilityContext, Mapping[str, Any]],
    Awaitable[CapabilityResult],
]


class CapabilityRegistry:
    """In-memory registry of immutable capability specifications."""

    def __init__(self) -> None:
        self._specs: dict[str, CapabilitySpec] = {}

    def register(self, spec: CapabilitySpec) -> None:
        if spec.capability_id in self._specs:
            raise ValueError(
                f"duplicate capability_id: {spec.capability_id}"
            )
        self._specs[spec.capability_id] = spec

    def get(self, capability_id: str) -> CapabilitySpec | None:
        return self._specs.get(capability_id)

    def require(self, capability_id: str) -> CapabilitySpec:
        spec = self.get(capability_id)
        if spec is None:
            raise KeyError(f"unknown capability: {capability_id}")
        return spec

    def all(self) -> tuple[CapabilitySpec, ...]:
        return tuple(self._specs.values())

    def discoverable(self) -> tuple[CapabilitySpec, ...]:
        return tuple(spec for spec in self._specs.values() if spec.discoverable)


class CapabilityDispatcher:
    """Dispatches validated requests to registered handlers.

    A1 intentionally does not perform natural-language routing or Discord
    permission checks. It enforces only registry membership, handler presence,
    and the explicit confirmation contract.
    """

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry
        self._handlers: dict[str, CapabilityHandler] = {}

    def register_handler(
        self,
        capability_id: str,
        handler: CapabilityHandler,
    ) -> None:
        self._registry.require(capability_id)
        if capability_id in self._handlers:
            raise ValueError(f"duplicate handler: {capability_id}")
        self._handlers[capability_id] = handler

    async def dispatch(
        self,
        request: CapabilityRequest,
        context: CapabilityContext,
    ) -> CapabilityResult:
        spec = self._registry.require(request.capability_id)
        if spec.requires_confirmation and not request.confirmed:
            raise PermissionError(
                f"confirmation required: {request.capability_id}"
            )
        handler = self._handlers.get(request.capability_id)
        if handler is None:
            raise LookupError(
                f"no handler registered: {request.capability_id}"
            )
        result = await handler(context, request.arguments)
        if result.capability_id != request.capability_id:
            raise ValueError(
                "handler returned a result for a different capability"
            )
        return result
