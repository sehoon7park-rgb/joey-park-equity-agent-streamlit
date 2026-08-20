from joey_park.config.settings import _validate_anthropic_api_key


def test_clean_ascii_key_passes_through():
    key, error = _validate_anthropic_api_key("sk-ant-api03-abc123")
    assert key == "sk-ant-api03-abc123"
    assert error is None


def test_none_key_passes_through():
    key, error = _validate_anthropic_api_key(None)
    assert key is None
    assert error is None


def test_whitespace_is_stripped():
    key, error = _validate_anthropic_api_key("  sk-ant-api03-abc123  \n")
    assert key == "sk-ant-api03-abc123"
    assert error is None


def test_non_ascii_key_is_rejected_with_position():
    key, error = _validate_anthropic_api_key("sk-ant-api03-abc" + chr(0xAC00) + "123")
    assert key is None
    assert error is not None
    assert "ANTHROPIC_API_KEY" in error
