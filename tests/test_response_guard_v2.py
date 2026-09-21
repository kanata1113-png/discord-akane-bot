from services.response_guard import ResponseGuard


def test_guard_detects_unclosed_code_fence():
    result = ResponseGuard.check("```python\nprint('x')")
    assert not result.ok
    assert result.reason == "unclosed_code_fence"


def test_guard_detects_missing_requested_bullets():
    result = ResponseGuard.check("これは通常の文章です。", requested_format="bullets")
    assert not result.ok
    assert result.reason == "missing_bullets"


def test_guard_accepts_requested_bullets():
    result = ResponseGuard.check("- 一つ目\n- 二つ目", requested_format="bullets")
    assert result.ok


def test_guard_preserves_existing_incomplete_priority():
    result = ResponseGuard.check("- text", incomplete=True, requested_format="bullets")
    assert not result.ok
    assert result.reason == "incomplete"
