import pytest

from services.admin_capabilities import (
    ADMIN_WRITE_CAPABILITY_SPECS,
    build_admin_capability_dispatcher,
    dispatch_admin_action,
)
from services.capability_core import CapabilityRisk


class FakeAdminDataSource:
    def __init__(self):
        self.calls = []

    async def perform_admin_action(self, *, context, capability_id, arguments):
        self.calls.append((capability_id, dict(arguments)))
        return {"ok": True}


def test_admin_write_specs_are_hidden_and_confirmation_gated():
    assert len(ADMIN_WRITE_CAPABILITY_SPECS) == 11
    for spec in ADMIN_WRITE_CAPABILITY_SPECS:
        assert spec.risk is CapabilityRisk.ADMIN
        assert spec.requires_confirmation is True
        assert spec.discoverable is False
        assert spec.slash_command.startswith("/admin ")


@pytest.mark.asyncio
@pytest.mark.parametrize("spec", ADMIN_WRITE_CAPABILITY_SPECS)
async def test_admin_write_fails_closed_without_confirmation(spec):
    source = FakeAdminDataSource()
    dispatcher = build_admin_capability_dispatcher(source)
    with pytest.raises(PermissionError):
        await dispatch_admin_action(
            dispatcher,
            capability_id=spec.capability_id,
            user_id=1,
            guild_id=2,
            channel_id=3,
            arguments={},
            confirmed=False,
        )
    assert source.calls == []


@pytest.mark.asyncio
async def test_confirmed_admin_write_reaches_adapter():
    source = FakeAdminDataSource()
    dispatcher = build_admin_capability_dispatcher(source)
    spec = ADMIN_WRITE_CAPABILITY_SPECS[0]
    result = await dispatch_admin_action(
        dispatcher,
        capability_id=spec.capability_id,
        user_id=1,
        guild_id=2,
        channel_id=3,
        arguments={"channel_id": 99},
        confirmed=True,
    )
    assert result.ok is True
    assert source.calls == [(spec.capability_id, {"channel_id": 99})]
