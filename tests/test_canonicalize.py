from atlas.ingest.discovery import canonicalize_url


def test_canonicalize_url_basic() -> None:
    assert canonicalize_url("HTTP://Example.com/Test/") == "http://example.com/Test"
    assert canonicalize_url("https://example.com") == "https://example.com/"
    assert canonicalize_url("example.com/path") == "https://example.com/path"
