from pathlib import Path


def test_initial_migration_declares_all_mvp_tables_and_indexes() -> None:
    path = Path("migrations/versions/0f6331267571_init.py")
    text = path.read_text()

    for table_name in ("domains", "sources", "documents", "programs", "claims", "crawl_jobs"):
        assert f"op.create_table('{table_name}'" in text

    assert "documents_content_tsv_idx" in text
    assert "ix_domains_domain" in text
    assert "ix_sources_canonical_url" in text
