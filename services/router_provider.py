from __future__ import annotations

from typing import Protocol

from services.jev_model_router import JevRouteDecision


class RouterProvider(Protocol):
    """Structural interface for model-tier routing providers.

    JevModelRouter already satisfies this protocol. Future experimental
    providers can be substituted without changing RoutingPolicy.
    """

    mode: str

    @property
    def is_configured(self) -> bool: ...

    async def route(self, content: str) -> JevRouteDecision: ...
