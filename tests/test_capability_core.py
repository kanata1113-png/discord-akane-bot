import pytest

from services.capability_core import (
    CapabilityContext,
    CapabilityDispatcher,
    CapabilityRegistry,
    CapabilityRequest,
    CapabilityResult,
    CapabilityRisk,
    CapabilitySpec,
)


def make_spec(
    capability_id="level",
    *,
    risk=CapabilityRisk.READ_ONLY,
    requires_confirmation=False,
    discoverable=True,
):
    return CapabilitySpec(
        capability_id=capability_id,
        name=capability_id,
        description=f"{capability_id} capability",
        risk=risk,
        category="progression",
        slash_command=f"/{capability_id}",
        requires_confirmation=requires_confirmation,
        discoverable=discoverable,
    )


def test_registry_rejects_duplicate_capability_ids():
    registry = CapabilityRegistry()
    registry.register(make_spec())

    with pytest.raises(ValueError, match="duplicate capability_id"):
        registry.register(make_spec())


def test_registry_separates_discoverable_from_internal_specs():
    registry = CapabilityRegistry()
    registry.register(make_spec("level"))
    registry.register(make_spec("internal", discoverable=False))

    assert [spec.capability_id for spec in registry.all()] == [
        "level",
        "internal",
    ]
    assert [spec.capability_id for spec in registry.discoverable()] == [
        "level",
    ]


@pytest.mark.parametrize(
    "risk",
    [
        CapabilityRisk.WRITE_CONFIRM,
        CapabilityRisk.MODERATION,
        CapabilityRisk.ADMIN,
    ],
)
def test_non_read_only_risks_require_confirmation_contract(risk):
    with pytest.raises(ValueError, match="must require confirmation"):
        make_spec("unsafe", risk=risk, requires_confirmation=False)


def test_request_arguments_are_immutable_snapshot():
    source = {"minutes": 10}
    request = CapabilityRequest("remind", source)
    source["minutes"] = 99

    assert request.arguments["minutes"] == 10
    with pytest.raises(TypeError):
        request.arguments["minutes"] = 20


@pytest.mark.asyncio
async def test_dispatcher_executes_registered_read_only_handler():
    registry = CapabilityRegistry()
    registry.register(make_spec("level"))
    dispatcher = CapabilityDispatcher(registry)
    seen = {}

    async def handler(context, arguments):
        seen["user_id"] = context.user_id
        seen["arguments"] = dict(arguments)
        return CapabilityResult(
            capability_id="level",
            ok=True,
            value={"level": 3},
        )

    dispatcher.register_handler("level", handler)
    result = await dispatcher.dispatch(
        CapabilityRequest("level", {"member_id": 123}),
        CapabilityContext(user_id=123, guild_id=456, channel_id=789),
    )

    assert result.ok is True
    assert result.value == {"level": 3}
    assert seen == {
        "user_id": 123,
        "arguments": {"member_id": 123},
    }


@pytest.mark.asyncio
async def test_dispatcher_blocks_unconfirmed_write():
    registry = CapabilityRegistry()
    registry.register(
        make_spec(
            "remind",
            risk=CapabilityRisk.WRITE_CONFIRM,
            requires_confirmation=True,
        )
    )
    dispatcher = CapabilityDispatcher(registry)

    async def handler(context, arguments):
        return CapabilityResult("remind", True)

    dispatcher.register_handler("remind", handler)

    with pytest.raises(PermissionError, match="confirmation required"):
        await dispatcher.dispatch(
            CapabilityRequest("remind", {"minutes": 10}),
            CapabilityContext(user_id=1),
        )


@pytest.mark.asyncio
async def test_dispatcher_allows_confirmed_write():
    registry = CapabilityRegistry()
    registry.register(
        make_spec(
            "remind",
            risk=CapabilityRisk.WRITE_CONFIRM,
            requires_confirmation=True,
        )
    )
    dispatcher = CapabilityDispatcher(registry)

    async def handler(context, arguments):
        return CapabilityResult(
            capability_id="remind",
            ok=True,
            value=dict(arguments),
        )

    dispatcher.register_handler("remind", handler)
    result = await dispatcher.dispatch(
        CapabilityRequest(
            "remind",
            {"minutes": 10, "message": "test"},
            confirmed=True,
        ),
        CapabilityContext(user_id=1),
    )

    assert result.value["minutes"] == 10


def test_handler_registration_requires_known_capability():
    dispatcher = CapabilityDispatcher(CapabilityRegistry())

    async def handler(context, arguments):
        return CapabilityResult("missing", True)

    with pytest.raises(KeyError, match="unknown capability"):
        dispatcher.register_handler("missing", handler)
