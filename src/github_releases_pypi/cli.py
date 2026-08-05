"""Typer command line interface for github-releases-pypi."""

import urllib.error
from pathlib import Path
from typing import Annotated

import typer

from github_releases_pypi import index

app = typer.Typer(add_completion=False)


@app.command()
def build(
    repo: Annotated[str, typer.Argument(help="GitHub repository as OWNER/NAME")],
    out: Annotated[Path, typer.Option(help="Directory to write the index to")],
    token: Annotated[
        str | None,
        typer.Option(envvar="GITHUB_TOKEN", help="GitHub API token"),
    ] = None,
) -> None:
    """Build a PEP 503 package index from the repository's release assets."""
    if not token:
        typer.echo("error: provide --token or set GITHUB_TOKEN", err=True)
        raise typer.Exit(1)
    try:
        releases = index.fetch_releases(repo, token)
        # pass via module attribute so tests can monkeypatch index.hash_url
        projects = index.collect_projects(releases, hash_url=index.hash_url)
    except urllib.error.URLError as error:
        typer.echo(f"error: GitHub API request for {repo} failed: {error}", err=True)
        raise typer.Exit(1) from error
    if not projects:
        typer.echo(
            f"error: no package assets found in releases of {repo}; "
            "refusing to build an empty index",
            err=True,
        )
        raise typer.Exit(1)
    index.write_site(projects, out, repo)
    typer.echo(f"wrote index for {len(projects)} project(s) to {out}")
