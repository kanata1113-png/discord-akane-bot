from services.response_guard import ResponseGuard


def test_response_guard_accepts_normal_text():
    result = ResponseGuard.check("ok response")
    assert result.ok is True
    assert result.reason is None


def test_response_guard_detects_empty_short_and_incomplete():
    assert ResponseGuard.check("").reason == "empty"
    assert ResponseGuard.check("x").reason == "too_short"
    assert ResponseGuard.check("partial", incomplete=True).reason == "incomplete"
