from atlas.ingest.normalization import build_content_tsv_text, normalize_extraction


def test_normalize_extraction_from_json_string() -> None:
    output = '{"title":"T","author":"A","text":"Body","summary":"S","programs":[],"claims":[]}'
    normalized = normalize_extraction(output)
    assert normalized.title == "T"
    assert normalized.author == "A"
    assert normalized.raw_text == "Body"
    assert normalized.summary == "S"


def test_build_content_tsv_text() -> None:
    text = build_content_tsv_text("Title", "Summary", "Body")
    assert text == "Title\nSummary\nBody"
