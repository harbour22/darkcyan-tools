import typer
from . import notify_run

app = typer.Typer()
app.add_typer(notify_run.app, name="notify-run")

if __name__ == "__main__":
    app()