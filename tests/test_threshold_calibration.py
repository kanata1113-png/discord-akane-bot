from tools.calibrate_routing_thresholds import evaluate


def test_threshold_calibration_prefers_human_label():
    metrics = [
        {
            "event": "routing_decision",
            "event_id": "abc",
            "legacy_route": "normal-chat",
            "jev_route": "reasoning",
            "confidence": 0.90,
        }
    ]
    labels = {"abc": "reasoning"}

    accepted = evaluate(metrics, labels, 0.85)
    rejected = evaluate(metrics, labels, 0.95)

    assert accepted["accuracy"] == 1.0
    assert accepted["jev_rate"] == 1.0
    assert rejected["accuracy"] == 0.0
    assert rejected["jev_rate"] == 0.0
