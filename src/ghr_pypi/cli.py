"""Typer command line interface for ghr-pypi."""

import os
import urllib.error
from dataclasses import replace
from pathlib import Path
from typing import Annotated

import typer

from ghr_pypi import index
from ghr_pypi.config import Config, ConfigError, check_slug, load

app = typer.Typer(add_completion=False)


def _resolve_config(
    repos: list[str] | None,
    config_path: Path | None,
    *,
    mirror: bool,
    env_repo: str | None,
) -> Config:
    """Resolve the build configuration from the command line and environment.

    ``env_repo`` is ``$GITHUB_REPOSITORY``; an empty value counts as unset. It
    is the last fallback in both branches and never conflicts with anything the
    user typed: GitHub Actions sets it for every step, so treating it as a
    conflict would break every config file user in CI. It is checked eagerly
    whenever it is set, before any network request, so a broken environment
    fails fast rather than at whichever later point first reads it — even in
    the cases where nothing ends up reading it at all.
    """
    env_repo = env_repo or None
    if env_repo is not None:
        check_slug(env_repo, "GITHUB_REPOSITORY")
    repos = list(repos or [])
    if config_path is not None:
        if repos:
            raise ConfigError("with --config, list repositories in the config file")
        if mirror:
            raise ConfigError("with --config, set 'mirror' in the config file")
        cfg = load(config_path)
        repositories = cfg.repositories
        if not repositories:
            if env_repo is None:
                raise ConfigError(
                    f"{config_path} has no 'repositories' and "
                    "GITHUB_REPOSITORY is not set"
                )
            repositories = (env_repo,)
    else:
        seen: set[str] = set()
        for repo in repos:
            check_slug(repo, "repository")
            if repo.casefold() in seen:
                raise ConfigError(f"repository {repo!r} given more than once")
            seen.add(repo.casefold())
        if repos:
            repositories = tuple(repos)
        elif env_repo is not None:
            repositories = (env_repo,)
        else:
            raise ConfigError("provide REPO..., set GITHUB_REPOSITORY, or use --config")
        cfg = Config(
            repositories=repositories,
            title=(
                f"{repositories[0]} package index"
                if len(repositories) == 1
                else "Package index"
            ),
            mirror=mirror,
        )
    url = cfg.url
    if url is None:
        if env_repo is not None:
            url = index.pages_url(env_repo)
        elif config_path is None and len(repositories) == 1:
            # Command line form only. A config that omits `url` has always
            # meant "no install example", and a repository listed there is not
            # necessarily the one serving the site.
            url = index.pages_url(repositories[0])
    return replace(cfg, repositories=repositories, url=url)


@app.command()
def build(
    repos: Annotated[
        list[str] | None,
        typer.Argument(
            metavar="[REPO]...",
            help="GitHub repositories as OWNER/NAME; defaults to "
            "$GITHUB_REPOSITORY (omit when using --config)",
        ),
    ] = None,
    out: Annotated[Path, typer.Option(help="Directory to write the index to")] = Path(
        "_site"
    ),
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help=(
                "YAML config aggregating multiple repositories "
                "(list the repositories in it, not on the command line)"
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
    if not token:
        typer.echo("error: provide --token or set GITHUB_TOKEN", err=True)
        raise typer.Exit(1)
    try:
        cfg = _resolve_config(
            repos,
            config,
            mirror=mirror,
            env_repo=os.environ.get("GITHUB_REPOSITORY"),
        )
    except ConfigError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error
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
            filters=cfg.filters,
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
