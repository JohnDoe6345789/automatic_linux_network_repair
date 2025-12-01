"""Console script for automatic_linux_network_repair."""

import typer
from rich.console import Console

from automatic_linux_network_repair import utils

app = typer.Typer()
console = Console()


@app.command()
def main():
    """Console script for automatic_linux_network_repair."""
    console.print("Replace this message by putting your code into "
               "automatic_linux_network_repair.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    utils.do_something_useful()


if __name__ == "__main__":
    app()
