from types import SimpleNamespace

import pytest

from services.capability_core import CapabilityRisk
from services.capability_discovery import DiscoveryCandidate
from services.discovery_direct_execution import (
    DIRECT_READ_ONLY_CAPABILITY_IDS,
    execute_selected_read_only,
)
from services.progression_capabilities import (
    ACHIEVEMENTS_SPEC,
    FORTUNE_SPEC,
    LEVEL_SPEC,
    PROFILE_SPEC,
    RANKINGS_SPEC,
    WEEKLY_SPEC,
)


def candidate(capability_id):
    return DiscoveryCandidate(
        capability_id=capability_id,
        name=capability_id,
        description=capability_id,
        slash_command=f"/{capability_id}",
        score=1.0,
        matched_terms=(capability_id,),
    )


class FakeCommand:
    def __init__(self, calls, capability_id):
        async def callback(cog, interaction):
            calls.append((capability_id, cog, interaction))

        self.callback = callback


class FakeGeneralCog:
    def __init__(self, calls):
        for capability_id in DIRECT_READ_ONLY_CAPABILITY_IDS:
            setattr(
                self,
                capability_id,
                FakeCommand(calls, capability_id),
            )


class FakeClient:
    def __init__(self, cog):
        self.cog = cog
        self.lookups = []

    def get_cog(self, name):
        self.lookups.append(name)
        return self.cog


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "capability_id",
    sorted(DIRECT_READ_ONLY_CAPABILITY_IDS),
)
async def test_explicit_supported_selection_invokes_existing_command_callback(
    capability_id,
):
    calls = []
    cog = FakeGeneralCog(calls)
    interaction = SimpleNamespace(client=FakeClient(cog))

    executed = await execute_selected_read_only(
        interaction,
        candidate(capability_id),
    )

    assert executed is True
    assert interaction.client.lookups == ["GeneralCog"]
    assert calls == [(capability_id, cog, interaction)]


@pytest.mark.asyncio
@pytest.mark.parametrize("capability_id", ["rankings", "fortune", "admin"])
async def test_unsupported_or_side_effectful_selection_never_executes(
    capability_id,
):
    calls = []
    interaction = SimpleNamespace(client=FakeClient(FakeGeneralCog(calls)))

    executed = await execute_selected_read_only(
        interaction,
        candidate(capability_id),
    )

    assert executed is False
    assert calls == []
    assert interaction.client.lookups == []


@pytest.mark.asyncio
async def test_missing_general_cog_fails_closed_without_execution():
    interaction = SimpleNamespace(client=FakeClient(None))

    executed = await execute_selected_read_only(
        interaction,
        candidate("level"),
    )

    assert executed is False
    assert interaction.client.lookups == ["GeneralCog"]


def test_direct_execution_allowlist_is_read_policy_and_argument_complete():
    specs = {
        spec.capability_id: spec
        for spec in (
            LEVEL_SPEC,
            WEEKLY_SPEC,
            PROFILE_SPEC,
            ACHIEVEMENTS_SPEC,
            RANKINGS_SPEC,
            FORTUNE_SPEC,
        )
    }

    assert DIRECT_READ_ONLY_CAPABILITY_IDS == {
        "level",
        "weekly",
        "profile",
        "achievements",
    }
    assert all(
        specs[capability_id].risk is CapabilityRisk.READ_ONLY
        for capability_id in DIRECT_READ_ONLY_CAPABILITY_IDS
    )
    assert "rankings" not in DIRECT_READ_ONLY_CAPABILITY_IDS
    assert "fortune" not in DIRECT_READ_ONLY_CAPABILITY_IDS
