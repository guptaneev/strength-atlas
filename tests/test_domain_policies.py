from atlas.ops.domain_policies import load_domain_policies


def test_load_domain_policies_parses_file(tmp_path) -> None:
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(
        """{
  "example.com": {
    "seed_urls": ["https://example.com/start"],
    "per_domain_limit": 7,
    "stale_after_days": 14,
    "admission_min_succeeded_sources": 5,
    "admission_max_recent_failure_rate": 0.3,
    "admission_min_avg_parse_confidence": 0.8,
    "admission_max_zero_program_rate": 0.2,
    "admission_recent_crawl_window": 30
  }
}""",
        encoding="utf-8",
    )
    policies = load_domain_policies(str(policy_file))
    assert "example.com" in policies
    assert policies["example.com"].seed_urls == ["https://example.com/start"]
    assert policies["example.com"].per_domain_limit == 7
    assert policies["example.com"].stale_after_days == 14
    assert policies["example.com"].admission_min_succeeded_sources == 5
    assert policies["example.com"].admission_max_recent_failure_rate == 0.3
    assert policies["example.com"].admission_min_avg_parse_confidence == 0.8
    assert policies["example.com"].admission_max_zero_program_rate == 0.2
    assert policies["example.com"].admission_recent_crawl_window == 30
