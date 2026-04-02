from atlas.ingest.discovery import is_url_in_domain, parse_candidate_urls, safe_canonicalize_url


def test_parse_candidate_urls_from_json_list_string() -> None:
    output = '["https://example.com/a","https://example.com/b"]'
    parsed = parse_candidate_urls(output)
    assert "https://example.com/a" in parsed
    assert "https://example.com/b" in parsed


def test_parse_candidate_urls_from_json_dict() -> None:
    output = {"urls": ["https://example.com/a"], "links": ["https://example.com/b"]}
    parsed = parse_candidate_urls(output)
    assert "https://example.com/a" in parsed
    assert "https://example.com/b" in parsed


def test_parse_candidate_urls_from_plain_text() -> None:
    output = "See https://example.com/a and https://example.com/b."
    parsed = parse_candidate_urls(output)
    assert "https://example.com/a" in parsed
    assert any(item.startswith("https://example.com/b") for item in parsed)


def test_is_url_in_domain_supports_subdomains() -> None:
    assert is_url_in_domain("https://www.strongerbyscience.com/articles", "strongerbyscience.com")
    assert not is_url_in_domain("https://example.com", "strongerbyscience.com")


def test_safe_canonicalize_url_rejects_invalid_values() -> None:
    assert safe_canonicalize_url("javascript:alert(1)") is None
    assert safe_canonicalize_url("not a url") is None
