from atlas.ingest.url_policy import (
    apply_discovery_url_policy,
    build_discovery_url_policy,
)


def test_discovery_policy_blocks_asset_and_taxonomy_paths() -> None:
    policy = build_discovery_url_policy(
        blocked_path_tokens_csv="tag,author,wp-admin",
        max_candidates=10,
    )
    filtered = apply_discovery_url_policy(
        [
            "https://example.com/how-to-bench",
            "https://example.com/tag/bench",
            "https://example.com/image.png",
            "https://example.com/author/coach",
        ],
        policy,
    )
    assert filtered.accepted_urls == ["https://example.com/how-to-bench"]
    assert len(filtered.rejected_urls) == 3


def test_discovery_policy_enforces_candidate_cap() -> None:
    policy = build_discovery_url_policy(
        blocked_path_tokens_csv="",
        max_candidates=2,
    )
    filtered = apply_discovery_url_policy(
        [
            "https://example.com/a",
            "https://example.com/b",
            "https://example.com/c",
        ],
        policy,
    )
    assert filtered.accepted_urls == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert filtered.rejected_urls == ["https://example.com/c"]
