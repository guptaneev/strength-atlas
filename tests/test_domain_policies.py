from atlas.ops.domain_policies import load_domain_policies


def test_load_domain_policies_parses_file(tmp_path) -> None:
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(
        """{
  "example.com": {
    "seed_urls": ["https://example.com/start"],
    "per_domain_limit": 7,
    "stale_after_days": 14
  }
}""",
        encoding="utf-8",
    )
    policies = load_domain_policies(str(policy_file))
    assert "example.com" in policies
    assert policies["example.com"].seed_urls == ["https://example.com/start"]
    assert policies["example.com"].per_domain_limit == 7
    assert policies["example.com"].stale_after_days == 14
