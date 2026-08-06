"""Load and validate the YAML configuration for multi-repository indexes."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml

MissingDigest = Literal["download", "no-fragment", "omit"]

_KNOWN_KEYS = {"repositories", "templates", "title", "url", "missing_digest"}


class ConfigError(ValueError):
    """Raised when the YAML configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    """Validated build configuration."""

    repositories: tuple[str, ...]
    templates: Path | None = None
    title: str = "Package index"
    url: str | None = None
    missing_digest: MissingDigest = "download"


def load(path: Path) -> Config:
    """Parse and validate the YAML config file at ``path``."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"cannot read config file {path}: {error}") from error
    except UnicodeDecodeError as error:
        raise ConfigError(f"config file {path} is not valid UTF-8: {error}") from error
    except yaml.YAMLError as error:
        raise ConfigError(f"invalid YAML in {path}: {error}") from error
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    if unknown := set(raw) - _KNOWN_KEYS:
        raise ConfigError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    repositories = raw.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ConfigError(f"{path}: 'repositories' must be a non-empty list")
    for repo in repositories:
        parts = repo.split("/") if isinstance(repo, str) else []
        if len(parts) != 2 or not all(parts):
            raise ConfigError(f"{path}: repository {repo!r} is not OWNER/NAME")
    if len({r.casefold() for r in repositories}) != len(repositories):
        raise ConfigError(f"{path}: 'repositories' contains duplicates")
    templates = None
    if (raw_templates := raw.get("templates")) is not None:
        if not isinstance(raw_templates, str):
            raise ConfigError(f"{path}: 'templates' must be a string path")
        templates = (path.parent / raw_templates).resolve()
        if not templates.is_dir():
            raise ConfigError(f"{path}: templates directory not found: {templates}")
    url = raw.get("url")
    if url is not None and not isinstance(url, str):
        raise ConfigError(f"{path}: 'url' must be a string")
    if url is not None and not url.startswith("https://"):
        raise ConfigError(f"{path}: 'url' must be https")
    title = raw.get("title", "Package index")
    if not isinstance(title, str):
        raise ConfigError(f"{path}: 'title' must be a string")
    missing_digest = raw.get("missing_digest", "download")
    if missing_digest not in ("download", "no-fragment", "omit"):
        raise ConfigError(
            f"{path}: 'missing_digest' must be one of "
            f"download, no-fragment, omit, got {missing_digest!r}"
        )
    return Config(
        repositories=tuple(repositories),
        templates=templates,
        title=title,
        url=url,
        missing_digest=cast(MissingDigest, missing_digest),
    )
