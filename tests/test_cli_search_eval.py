import json

from typer.testing import CliRunner

from atlas.cli.app import app


def test_search_eval_cli_json_output(monkeypatch, tmp_path) -> None:
    fixture = tmp_path / "eval.json"
    fixture.write_text('{"queries":[]}', encoding="utf-8")

    monkeypatch.setattr(
        "atlas.cli.commands.search.run_search_eval_suite",
        lambda _session, _suite: {
            "queries_total": 1,
            "queries_passed": 1,
            "pass_rate": 1.0,
            "results": [],
        },
    )
    monkeypatch.setattr(
        "atlas.cli.commands.search.SessionLocal",
        lambda: type(
            "_Ctx",
            (),
            {"__enter__": lambda self: object(), "__exit__": lambda self, *_args: None},
        )(),
    )

    runner = CliRunner()
    result = runner.invoke(app, ["search", "eval", "--fixture", str(fixture), "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["queries_total"] == 1
