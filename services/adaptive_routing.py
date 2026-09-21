from __future__ import annotations

import os
from dataclasses import dataclass

from services.router_provider import RouteDecision


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if 0.0 <= value <= 1.0 else default


@dataclass(frozen=True)
class AdaptiveRoutingProfile:
    normal_chat_threshold: float = 0.88
    reasoning_threshold: float = 0.82
    deep_reasoning_threshold: float = 0.90
    followup_discount: float = 0.02
    name: str = "balanced-v1"


@dataclass(frozen=True)
class AdaptiveAcceptance:
    accepted: bool
    threshold: float
    profile_name: str
    reason: str


class AdaptiveRoutingController:
    """Route-specific confidence policy, disabled by default.

    The controller never mutates environment variables or learns online. Phase C
    only makes a calibrated profile executable behind an explicit feature gate.
    """

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        profile: AdaptiveRoutingProfile | None = None,
    ) -> None:
        self.enabled = (
            _env_flag("AI_ADAPTIVE_ROUTING_POLICY", False)
            if enabled is None
            else bool(enabled)
        )
        self.profile = profile or AdaptiveRoutingProfile(
            normal_chat_threshold=_env_float("AI_ROUTE_THRESHOLD_NORMAL", 0.88),
            reasoning_threshold=_env_float("AI_ROUTE_THRESHOLD_REASONING", 0.82),
            deep_reasoning_threshold=_env_float("AI_ROUTE_THRESHOLD_DEEP", 0.90),
            followup_discount=_env_float("AI_ROUTE_FOLLOWUP_DISCOUNT", 0.02),
        )

    def threshold_for(self, route: str | None, *, followup_like: bool = False) -> float:
        if route == "deep-reasoning":
            threshold = self.profile.deep_reasoning_threshold
        elif route == "reasoning":
            threshold = self.profile.reasoning_threshold
        else:
            threshold = self.profile.normal_chat_threshold

        if followup_like and route in {"reasoning", "deep-reasoning"}:
            threshold = max(0.0, threshold - self.profile.followup_discount)
        return round(threshold, 4)

    def evaluate(
        self,
        decision: RouteDecision,
        *,
        followup_like: bool = False,
    ) -> AdaptiveAcceptance:
        if decision.error or decision.route is None:
            return AdaptiveAcceptance(
                accepted=False,
                threshold=1.0,
                profile_name=self.profile.name,
                reason="provider_error",
            )

        threshold = self.threshold_for(
            decision.route,
            followup_like=followup_like,
        )
        if not self.enabled:
            return AdaptiveAcceptance(
                accepted=decision.accepted,
                threshold=threshold,
                profile_name=self.profile.name,
                reason="controller_disabled",
            )

        accepted = decision.confidence >= threshold
        return AdaptiveAcceptance(
            accepted=accepted,
            threshold=threshold,
            profile_name=self.profile.name,
            reason="adaptive_threshold",
        )
