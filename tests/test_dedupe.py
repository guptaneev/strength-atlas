from atlas.ingest.discovery import is_duplicate_canonical


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, value):
        self._value = value

    def execute(self, _stmt):
        return FakeResult(self._value)


def test_is_duplicate_canonical_true() -> None:
    session = FakeSession(value=object())
    assert is_duplicate_canonical(session, "https://example.com") is True


def test_is_duplicate_canonical_false() -> None:
    session = FakeSession(value=None)
    assert is_duplicate_canonical(session, "https://example.com") is False
