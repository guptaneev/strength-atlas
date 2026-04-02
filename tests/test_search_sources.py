from atlas.search.sources import search_sources


def test_search_sources_signature() -> None:
    # Signature smoke test
    assert callable(search_sources)
