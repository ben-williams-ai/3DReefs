"""Colour profile CLI defaults."""

from pathlib import Path

from click.testing import CliRunner

from reefs.cli import app


def test_profile_create_help_makes_output_optional() -> None:
    result = CliRunner().invoke(app, ["colour", "profile", "create", "--help"])

    assert result.exit_code == 0
    assert "--output FILE" in result.output
    assert "[required]" not in result.output.split("--output FILE", 1)[1].splitlines()[0]
