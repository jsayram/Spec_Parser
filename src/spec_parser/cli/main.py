"""Main CLI entry point for spec-parser."""

import click
from .commands.device import device_commands


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """POCT1 Specification Parser and Device Lifecycle Manager."""
    pass


# Register command groups
cli.add_command(device_commands)


if __name__ == "__main__":
    cli()
