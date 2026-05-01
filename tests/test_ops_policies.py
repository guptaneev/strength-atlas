from atlas.ops.policies import classify_error_code, error_kind_from_code


def test_classify_error_code_maps_db_truncation() -> None:
    code = classify_error_code(RuntimeError("value too long for type character varying(64)"))
    assert code == "value_too_long"
    assert error_kind_from_code(code) == "terminal"


def test_classify_error_code_maps_dns_and_rate_limit() -> None:
    assert classify_error_code(RuntimeError("failed to resolve host xyz")) == "dns_resolution_failed"
    assert classify_error_code(RuntimeError("429 too many requests")) == "rate_limited"
    assert error_kind_from_code("dns_resolution_failed") == "retryable"
    assert error_kind_from_code("rate_limited") == "retryable"
