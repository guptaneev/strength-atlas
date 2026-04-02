from atlas.search.programs import ProgramSearchFilters


def test_program_filters_default() -> None:
    filters = ProgramSearchFilters()
    assert filters.days_per_week is None
    assert filters.domain is None
