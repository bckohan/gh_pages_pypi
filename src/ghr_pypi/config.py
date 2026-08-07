"""Load and validate the YAML configuration for multi-repository indexes."""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, cast

import yaml
from packaging.version import InvalidVersion, Version

MissingDigest = Literal["download", "no-fragment", "omit"]

Formats = Literal["html", "json"]

_KNOWN_KEYS = {
    "repositories",
    "templates",
    "title",
    "url",
    "missing_digest",
    "formats",
    "mirror",
    "metadata",
    "yanked",
    "exclude",
}


class ConfigError(ValueError):
    """Raised when the YAML configuration is missing or invalid."""


def _normalize(name: str) -> str:
    """Normalize a project name per PEP 503.

    A copy of ``index.normalize``: ``config`` cannot import ``index`` because
    ``index`` imports this module.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _same_version(configured: str, found: str) -> bool:
    """Return True when two version strings denote the same release.

    Compares as :class:`packaging.version.Version` so ``1.0`` matches
    ``1.0.0``, falling back to exact string equality when either side is not a
    valid version.
    """
    if configured == found:
        return True
    try:
        return Version(configured) == Version(found)
    except InvalidVersion:
        return False


@dataclass(frozen=True)
class Filters:
    """Per-project, per-version yank and exclusion rules.

    ``yanked`` maps a project to a mapping of version to PEP 592 reason (a
    string, or True for "yanked, no reason given"). ``exclude`` maps a project
    to the versions to keep out of the index entirely. Project keys are
    PEP 503-normalized and both mappings are made read-only on construction;
    keys that normalize to the same project raise ``ValueError`` rather than
    silently discarding one of them.
    """

    yanked: Mapping[str, Mapping[str, str | bool]] = field(default_factory=dict)
    exclude: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        yanked: dict[str, Mapping[str, str | bool]] = {}
        for project, reasons in self.yanked.items():
            if (normalized := _normalize(project)) in yanked:
                raise ValueError(
                    f"Filters.yanked has two entries for project {normalized!r}"
                )
            yanked[normalized] = MappingProxyType(dict(reasons))
        exclude: dict[str, tuple[str, ...]] = {}
        for project, versions in self.exclude.items():
            if (normalized := _normalize(project)) in exclude:
                raise ValueError(
                    f"Filters.exclude has two entries for project {normalized!r}"
                )
            exclude[normalized] = tuple(versions)
        object.__setattr__(self, "yanked", MappingProxyType(yanked))
        object.__setattr__(self, "exclude", MappingProxyType(exclude))

    def yank_reason(self, project: str, version: str | None) -> str | bool:
        """Return the yank reason for ``project`` ``version``, else False.

        The reason is the configured string, or True when the version is
        yanked without one. A ``version`` of None (unparseable filename)
        matches nothing.

        Callers test the result for truth, so a falsy reason reads as "not
        yanked": :func:`load` rejects an empty string, but ``Filters`` is
        directly constructible and does not.
        """
        if version is None:
            return False
        for configured, reason in self.yanked.get(_normalize(project), {}).items():
            if _same_version(configured, version):
                return reason
        return False

    def is_excluded(self, project: str, version: str | None) -> bool:
        """Return whether ``project`` ``version`` is excluded from the index.

        A ``version`` of None (unparseable filename) matches nothing.
        """
        if version is None:
            return False
        return any(
            _same_version(configured, version)
            for configured in self.exclude.get(_normalize(project), ())
        )


NO_FILTERS = Filters()
"""The empty :class:`Filters` — yanks nothing, excludes nothing.

Deeply immutable, so it is safe to share as a default argument.
"""


@dataclass(frozen=True)
class Config:
    """Validated build configuration."""

    repositories: tuple[str, ...]
    templates: Path | None = None
    title: str = "Package index"
    url: str | None = None
    missing_digest: MissingDigest = "download"
    formats: tuple[Formats, ...] = ("html", "json")
    mirror: bool = False
    metadata: bool = True
    filters: Filters = NO_FILTERS


def _yanked(path: Path, raw: Any) -> dict[str, dict[str, str | bool]]:
    """Validate the ``yanked`` key's value, keyed by normalized project name."""
    if not isinstance(raw, dict):
        raise ConfigError(
            f"{path}: 'yanked' must be a mapping of project name to "
            "a mapping of version to reason"
        )
    yanked: dict[str, dict[str, str | bool]] = {}
    for project, reasons in raw.items():
        if not isinstance(project, str):
            raise ConfigError(
                f"{path}: 'yanked' project keys must be strings, got {project!r}"
            )
        if not isinstance(reasons, dict):
            raise ConfigError(
                f"{path}: 'yanked.{project}' must be a mapping of version to reason"
            )
        seen: list[str] = []
        for version, reason in reasons.items():
            if not isinstance(version, str):
                raise ConfigError(
                    f"{path}: 'yanked.{project}' version keys must be quoted "
                    f'strings, got {version!r}; write it as "{version}"'
                )
            if reason is False:
                raise ConfigError(
                    f"{path}: 'yanked.{project}.{version}' is false; remove the "
                    "entry to un-yank the version"
                )
            if reason == "":
                raise ConfigError(
                    f"{path}: 'yanked.{project}.{version}' has an empty reason; "
                    "use true for a yank with no reason"
                )
            if reason is not True and not isinstance(reason, str):
                raise ConfigError(
                    f"{path}: 'yanked.{project}.{version}' must be a reason "
                    f"string or true, got {reason!r}"
                )
            if any(_same_version(version, prior) for prior in seen):
                raise ConfigError(
                    f"{path}: 'yanked.{project}' has two entries for version "
                    f"{version!r}"
                )
            seen.append(version)
        if (normalized := _normalize(project)) in yanked:
            raise ConfigError(
                f"{path}: 'yanked' has two entries for project {normalized!r}"
            )
        yanked[normalized] = dict(reasons)
    return yanked


def _exclude(path: Path, raw: Any) -> dict[str, tuple[str, ...]]:
    """Validate the ``exclude`` key's value, keyed by normalized project name."""
    if not isinstance(raw, dict):
        raise ConfigError(
            f"{path}: 'exclude' must be a mapping of project name to a list of versions"
        )
    exclude: dict[str, tuple[str, ...]] = {}
    for project, versions in raw.items():
        if not isinstance(project, str):
            raise ConfigError(
                f"{path}: 'exclude' project keys must be strings, got {project!r}"
            )
        if not isinstance(versions, list):
            raise ConfigError(
                f"{path}: 'exclude.{project}' must be a list of version strings"
            )
        seen: list[str] = []
        for version in versions:
            if not isinstance(version, str):
                raise ConfigError(
                    f"{path}: 'exclude.{project}' versions must be quoted "
                    f'strings, got {version!r}; write it as "{version}"'
                )
            if any(_same_version(version, prior) for prior in seen):
                raise ConfigError(
                    f"{path}: 'exclude.{project}' has two entries for version "
                    f"{version!r}"
                )
            seen.append(version)
        if (normalized := _normalize(project)) in exclude:
            raise ConfigError(
                f"{path}: 'exclude' has two entries for project {normalized!r}"
            )
        exclude[normalized] = tuple(versions)
    return exclude


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
    raw_formats = raw.get("formats", ["html", "json"])
    if not isinstance(raw_formats, list) or not raw_formats:
        raise ConfigError(f"{path}: 'formats' must be a non-empty list")
    for fmt in raw_formats:
        if fmt not in ("html", "json"):
            raise ConfigError(
                f"{path}: 'formats' entries must be html or json, got {fmt!r}"
            )
    if len(set(raw_formats)) != len(raw_formats):
        raise ConfigError(f"{path}: 'formats' contains duplicates")
    formats = cast(tuple[Formats, ...], tuple(raw_formats))
    mirror = raw.get("mirror", False)
    if not isinstance(mirror, bool):
        raise ConfigError(f"{path}: 'mirror' must be true or false")
    if mirror and "missing_digest" in raw:
        raise ConfigError(
            f"{path}: 'missing_digest' has no effect when 'mirror' is enabled"
        )
    metadata = raw.get("metadata", True)
    if not isinstance(metadata, bool):
        raise ConfigError(f"{path}: 'metadata' must be true or false")
    filters = Filters(
        yanked=_yanked(path, raw.get("yanked", {})),
        exclude=_exclude(path, raw.get("exclude", {})),
    )
    return Config(
        repositories=tuple(repositories),
        templates=templates,
        title=title,
        url=url,
        missing_digest=cast(MissingDigest, missing_digest),
        formats=formats,
        mirror=mirror,
        metadata=metadata,
        filters=filters,
    )
