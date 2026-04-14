from atlas.ingest.normalization import (
    build_content_tsv_text,
    infer_programs,
    is_program_focused_url,
    normalize_extraction,
    validate_normalized_extraction,
)


def test_normalize_extraction_from_json_string() -> None:
    output = '{"title":"T","author":"A","main_text":"Body","summary":"S","programs":[],"claims":[]}'
    normalized = normalize_extraction(output, url="https://example.com/program")
    assert normalized.title == "T"
    assert normalized.author == "A"
    assert normalized.raw_text == "Body"
    assert normalized.summary == "S"
    assert normalized.payload_type == "object"
    assert "schema_invalid" not in normalized.warnings


def test_normalize_extraction_uses_plain_text_fallback() -> None:
    output = "This is plain extracted text when no JSON is returned."
    normalized = normalize_extraction(output)
    assert normalized.raw_text == output
    assert normalized.payload_type == "string"
    assert "schema_invalid" in normalized.warnings


def test_normalize_extraction_reads_alternate_keys() -> None:
    output = {
        "page_title": "Bench Guide",
        "byline": "Coach",
        "content": "Long body",
        "description": "Short summary",
    }
    normalized = normalize_extraction(output)
    assert normalized.title == "Bench Guide"
    assert normalized.author == "Coach"
    assert normalized.raw_text == "Long body"
    assert normalized.summary == "Short summary"


def test_normalize_extraction_clamps_confidence_and_coerces_days() -> None:
    output = {
        "title": "Program",
        "main_text": "text body " * 40,
        "programs": [
            {
                "name": "Bench Builder",
                "days_per_week": "4 days",
                "confidence": 1.7,
                "specialization": "Bench press",
                "experience_level": "Intermediate lifters",
            }
        ],
    }
    normalized = normalize_extraction(output)
    assert normalized.programs[0]["days_per_week"] == 4
    assert normalized.programs[0]["confidence"] == 1.0
    assert normalized.programs[0]["specialization"] == "bench"
    assert normalized.programs[0]["experience_level"] == "intermediate"


def test_normalize_extraction_drops_unmapped_long_enum_values() -> None:
    output = {
        "title": "Program",
        "main_text": "text body " * 40,
        "programs": [
            {
                "name": "Bench Builder",
                "progression_type": "periodized - specificity increases as meet approaches",
                "split_type": "strength-focused: squat, press, deadlift, bench press",
            }
        ],
    }
    normalized = normalize_extraction(output)
    assert normalized.programs[0]["progression_type"] is None
    assert normalized.programs[0]["split_type"] is None


def test_validate_normalized_extraction_flags_low_quality_and_program_page() -> None:
    normalized = normalize_extraction({"title": "Program", "main_text": "Too short", "programs": []})
    errors = validate_normalized_extraction(normalized, url="https://example.com/program-bundle")
    assert "low_quality_output" in errors
    assert "no_programs_on_program_page" in errors


def test_infer_programs_only_for_program_focused_urls() -> None:
    assert not is_program_focused_url("https://example.com/how-to-bench")
    inferred = infer_programs(
        url="https://example.com/program-bundle",
        title="Program Bundle",
        summary="Great bundle",
        raw_text="Train 4 days per week",
    )
    assert len(inferred) == 1
    assert inferred[0]["name"] == "Program Bundle"
    assert inferred[0]["days_per_week"] == 4


def test_build_content_tsv_text() -> None:
    text = build_content_tsv_text("Title", "Summary", "Body")
    assert text == "Title\nSummary\nBody"
