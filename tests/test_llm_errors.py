from concurrent.futures import Future

from joey_park.llm.errors import describe, unwrap


class _FakeRetryError(Exception):
    def __init__(self, last_attempt):
        self.last_attempt = last_attempt
        super().__init__("retry exhausted")


def test_unwrap_extracts_real_exception_from_retry_error():
    fut = Future()
    fut.set_exception(ValueError("bad value: 'abc' is not numeric"))
    retry_err = _FakeRetryError(fut)

    real = unwrap(retry_err)

    assert isinstance(real, ValueError)
    assert "bad value" in str(real)


def test_unwrap_passthrough_for_plain_exception():
    exc = RuntimeError("plain failure")
    assert unwrap(exc) is exc


def test_describe_includes_class_name_and_message():
    fut = Future()
    fut.set_exception(UnicodeEncodeError("ascii", "abc가나다", 3, 4, "ordinal not in range(128)"))
    retry_err = _FakeRetryError(fut)

    text = describe(retry_err)

    assert "UnicodeEncodeError" in text
    assert "ordinal not in range" in text


def test_describe_unfinished_future_falls_back_to_outer_exception():
    fut = Future()  # never completed
    retry_err = _FakeRetryError(fut)
    assert unwrap(retry_err) is retry_err
