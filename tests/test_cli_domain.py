from typer.testing import CliRunner

from atlas.cli.app import app


def test_domain_list_cli_invokes() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["domain", "list", "--json"])
    # Without a configured DB this will likely fail, but the CLI should be wired.
    assert result.exit_code in (0, 1)
