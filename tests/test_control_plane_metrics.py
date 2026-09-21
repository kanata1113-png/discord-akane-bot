from dataclasses import fields

from services.control_plane_metrics import ControlPlaneEvent


def test_control_plane_event_schema_has_no_content_or_identity_fields():
    names = {field.name for field in fields(ControlPlaneEvent)}
    forbidden = {
        "content",
        "prompt",
        "user_id",
        "guild_id",
        "channel_id",
        "message_id",
    }
    assert names.isdisjoint(forbidden)


def test_control_plane_event_serializes_sparse_metadata():
    event = ControlPlaneEvent(
        event_id="abc",
        phase="plan_built",
        route="reasoning",
        intent="analysis",
        max_output_tokens=2000,
    )
    payload = event.to_dict()
    assert payload["event_id"] == "abc"
    assert payload["phase"] == "plan_built"
    assert "latency_ms" not in payload
