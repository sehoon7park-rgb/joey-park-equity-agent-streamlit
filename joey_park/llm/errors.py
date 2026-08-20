"""Error-unwrapping helper.

tenacity.RetryError.__str__ returns repr(self.last_attempt), which for a
concurrent.futures.Future only shows the exception CLASS NAME (e.g.
"<Future at 0x... state=finished raised UnicodeEncodeError>") — the actual
message (which character, which codec) is silently dropped. Every
str(exc) in the LLM-calling agents was logging that uninformative repr
instead of the real error, which is why an earlier deploy's logs showed
"raised UnicodeEncodeError" with no way to tell what actually broke.
"""
from __future__ import annotations


def unwrap(exc: BaseException) -> BaseException:
    """Returns the real underlying exception if `exc` is a tenacity
    RetryError wrapping a finished Future, else returns `exc` unchanged.
    """
    last_attempt = getattr(exc, "last_attempt", None)
    if last_attempt is not None and last_attempt.done():
        inner = last_attempt.exception()
        if inner is not None:
            return inner
    return exc


def describe(exc: BaseException) -> str:
    real = unwrap(exc)
    return f"{type(real).__name__}: {real}"
