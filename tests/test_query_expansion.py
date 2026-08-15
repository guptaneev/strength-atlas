from atlas.search.query_expansion import expand_query


def test_expansion_infers_days_and_experience() -> None:
    intent = expand_query("beginner powerlifting program four days per week")
    assert intent.days_per_week == 4
    assert intent.experience_level == "beginner"
    assert "novice" in intent.terms
    assert "powerlifting" in intent.terms


def test_expansion_handles_multiword_semantic_aliases() -> None:
    intent = expand_query("minimum effective dose full body program")
    assert "minimal" in intent.terms
    assert "low volume" in intent.terms
    assert intent.split_type == "full-body"
