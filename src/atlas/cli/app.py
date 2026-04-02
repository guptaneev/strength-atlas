from typer import Typer

from atlas.cli.commands.crawl import app as crawl_app
from atlas.cli.commands.domain import app as domain_app
from atlas.cli.commands.ingest import app as ingest_app
from atlas.cli.commands.search import app as search_app
from atlas.cli.commands.source import app as source_app
from atlas.config.settings import get_settings

app = Typer(add_completion=False, help="Strength Atlas CLI")
app.add_typer(domain_app, name="domain")
app.add_typer(ingest_app, name="ingest")
app.add_typer(crawl_app, name="crawl")
app.add_typer(source_app, name="source")
app.add_typer(search_app, name="search")


@app.callback()
def main() -> None:
    """Initialize configuration and CLI context."""
    get_settings()


if __name__ == "__main__":
    app()
