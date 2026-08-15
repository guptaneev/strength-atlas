from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "src/atlas/web/templates/index.html").read_text(encoding="utf-8")
JS = (ROOT / "src/atlas/web/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "src/atlas/web/static/styles.css").read_text(encoding="utf-8")


def test_program_discovery_is_the_primary_accessible_surface() -> None:
    assert HTML.index("Program Discovery") < HTML.index("Ask Atlas")
    assert 'id="tab-program"' in HTML
    assert 'id="tab-program" class="tab" role="tab" aria-selected="true"' in HTML
    assert 'id="panel-program" class="panel"' in HTML
    assert 'id="panel-ask" class="panel hidden"' in HTML


def test_public_result_copy_avoids_internal_ranking_jargon() -> None:
    rendered_copy = HTML + JS
    for forbidden in ("cross-encoder", "raw score", "Program #", "source ${row.source_id}"):
        assert forbidden not in rendered_copy
    assert "Evidence used for this answer" in JS
    assert "View original source" in JS


def test_ui_has_responsive_focus_loading_empty_timeout_and_uncertainty_states() -> None:
    assert "@media (max-width: 768px)" in CSS
    assert ":focus-visible" in CSS
    assert 'aria-live="polite"' in HTML
    assert 'aria-busy", "true"' in JS
    assert "renderEmpty" in JS
    assert "timed out" in JS or "too long" in JS
    assert "Limited source quality" in JS
