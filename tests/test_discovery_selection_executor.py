from types import SimpleNamespace

import pytest

from services.discovery_execution_policy import (
    DIRECT_EXECUTION_CAPABILITY_IDS,
    can_direct_execute_discovery_capability,
)
from services.discovery_selection_executor import execute_discovery_selection


def test_direct_execution_policy_is_fail_closed_and_excludes_fortune_rankings():
    assert DIRECT_EXECUTION_CAPABILITY_IDS == frozenset(
        {"level", "weekly", "profile", "achievements"}
    )
    assert can_direct_execute_discovery_capability("level") is True
    assert can_direct_execute_discovery_capability("weekly") is True
    assert can_direct_execute_discovery_capability("profile") is True
    assert can_direct_execute_discovery_capability("achievements") is True
    assert can_direct_execute_discovery_capability("rankings") is False
    assert can_direct_execute_discovery_capability("fortune") is False
    assert can_direct_execute_discovery_capability("admin") is False
    assert can_direct_execute_discovery_capability("unknown") is False


class FakeCommand:
    def __init__(self, capability_id, calls):
        async def callback(binding, interaction, member_marker="not-passed"):
            calls.append(
                (
                    capability_id,
                    binding,
                    interaction.user.id,
                    member_marker,
                )
            )

        self.callback = callback


class FakeGeneralCog:
    def __init__(self, calls):
        for capability_id in ("level", "weekly", "profile", "achievements"):
            setattr(self, capability_id, FakeCommand(capability_id, calls))


class FakeClient:
    def __init__(self, cog):
        self._cog = cog

    def get_cog(self, name):
        assert name == "GeneralCog"
        return self._cog


def interaction_with(cog, user_id=123):
    return SimpleNamespace(
        client=FakeClient(cog),
        user=SimpleNamespace(id=user_id),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("capability_id", "expected_member_marker"),
    [
        ("level", "not-passed"),
        ("weekly", "not-passed"),
        ("profile", None),
        ("achievements", None),
    ],
)
async def test_executor_reuses_existing_general_cog_callbacks(
    capability_id,
    expected_member_marker,
):
    calls = []
    cog = FakeGeneralCog(calls)
    interaction = interaction_with(cog)
    selection = SimpleNamespace(capability_id=capability_id)

    executed = await execute_discovery_selection(interaction, selection)

    assert executed is True
    assert calls == [
        (capability_id, cog, 123, expected_member_marker)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("capability_id", ["rankings", "fortune", "unknown"])
async def test_executor_never_resolves_cog_for_non_allowlisted_capability(
    capability_id,
):
    class ExplodingClient:
        def get_cog(self, name):
            raise AssertionError("non-allowlisted capability reached execution")

    interaction = SimpleNamespace(
        client=ExplodingClient(),
        user=SimpleNamespace(id=123),
    )

    executed = await execute_discovery_selection(
        interaction,
        SimpleNamespace(capability_id=capability_id),
    )

    assert executed is False
