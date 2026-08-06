"""Typer command line interface for ghr-pypi."""

import urllib.error
from pathlib import Path
from typing import Annotated

import typer

from ghr_pypi import index
from ghr_pypi.config import Config, ConfigError, load

app = typer.Typer(add_completion=False)


@app.command()
def build(
    out: Annotated[Path, typer.Option(help="Directory to write the index to")],
    repo: Annotated[
        str | None,
        typer.Argument(
            help="GitHub repository as OWNER/NAME (exactly one of REPO or --config)"
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help=(
                "YAML config aggregating multiple repositories "
                "(exactly one of REPO or --config)"
            ),
        ),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option(envvar="GITHUB_TOKEN", help="GitHub API token"),
    ] = None,
    mirror: Annotated[
        bool,
        typer.Option(
            "--mirror",
            help="Download assets into the site instead of linking to GitHub "
            "(with --config, set 'mirror' in the config file instead)",
        ),
    ] = False,
) -> None:
    """Build a PEP 503 package index from GitHub release assets."""
    if (repo is None) == (config is None):
        typer.echo("error: provide exactly one of REPO or --config", err=True)
        raise typer.Exit(1)
    if not token:
        typer.echo("error: provide --token or set GITHUB_TOKEN", err=True)
        raise typer.Exit(1)
    if config is not None:
        if mirror:
            typer.echo(
                "error: with --config, set 'mirror' in the config file", err=True
            )
            raise typer.Exit(1)
        try:
            cfg = load(config)
        except ConfigError as error:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(1) from error
    else:
        assert repo is not None
        parts = repo.split("/")
        if len(parts) != 2 or not all(parts):
            typer.echo(f"error: repository {repo!r} is not OWNER/NAME", err=True)
            raise typer.Exit(1)
        cfg = Config(
            repositories=(repo,),
            title=f"{repo} package index",
            url=index.pages_url(repo),
            mirror=mirror,
        )
    releases = []
    try:
        for current in cfg.repositories:
            fetched = index.fetch_releases(current, token)
            for release in fetched:
                # fetched payloads are fresh json.load output; safe to tag in place
                release["_source_repo"] = current
            releases.extend(fetched)
    except urllib.error.URLError as error:
        typer.echo(f"error: GitHub API request for {current} failed: {error}", err=True)
        raise typer.Exit(1) from error
    try:
        # pass via module attribute so tests can monkeypatch index.hash_url
        projects = index.collect_projects(
            releases,
            hash_url=index.hash_url,
            missing_digest=cfg.missing_digest,
            defer_hash=cfg.mirror,
            metadata=cfg.metadata,
        )
    except urllib.error.URLError as error:
        typer.echo(f"error: downloading a release asset failed: {error}", err=True)
        raise typer.Exit(1) from error
    if not projects:
        typer.echo(
            f"error: no package assets found in releases of "
            f"{', '.join(cfg.repositories)}; refusing to build an empty index",
            err=True,
        )
        raise typer.Exit(1)
    if cfg.mirror:
        try:
            index.mirror_files(projects, out, token)
        except index.MirrorError as error:
            typer.echo(f"error: {error}", err=True)
            raise typer.Exit(1) from error
        except urllib.error.URLError as error:
            typer.echo(f"error: downloading a release asset failed: {error}", err=True)
            raise typer.Exit(1) from error
        if cfg.metadata:
            index.extract_metadata(projects, out)
    elif cfg.metadata:
        for repo_name, (missing, total) in index.metadata_coverage(projects).items():
            if missing:
                typer.echo(
                    f"warning: {repo_name}: {missing} of {total} wheels have no "
                    ".metadata asset; resolvers must download full wheels for "
                    "dependency metadata",
                    err=True,
                )
    index_url = cfg.url.rstrip("/") + "/simple/" if cfg.url else None
    index.write_site(
        projects,
        out,
        title=cfg.title,
        index_url=index_url,
        templates_dir=cfg.templates,
        formats=cfg.formats,
    )
    typer.echo(f"wrote index for {len(projects)} project(s) to {out}")
