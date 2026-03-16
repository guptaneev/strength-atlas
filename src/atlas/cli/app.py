from typer import Typer

from atlas.config.settings import get_settings

app = Typer(add_completion=False, help="Strength Atlas CLI")


@app.callback()
def main() -> None:
    """Initialize configuration and CLI context."""
    get_settings()


if __name__ == "__main__":
    app()
