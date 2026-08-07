import dataclasses

import pytest

from ghr_pypi.config import Filters, _normalize
from ghr_pypi.index import normalize


@pytest.mark.parametrize(
    "name",
    [
        "demo-lib",
        "Demo_Lib",
        "Demo.Lib",
        "DEMO--LIB",
        "demo..__--lib",
        "Zope-Interface",
        "already-normal",
    ],
)
def test_normalize_matches_index_normalize(name):
    # config._normalize is a deliberate copy of index.normalize (config cannot
    # import index without a cycle) -- this guards against the two drifting.
    assert _normalize(name) == normalize(name)


def test_empty_filters_are_a_noop():
    filters = Filters()
    assert filters.yanked == {}
    assert filters.exclude == {}
    assert filters.yank_reason("demo-lib", "1.0.0") is False
    assert filters.is_excluded("demo-lib", "1.0.0") is False


def test_yank_reason_string():
    filters = Filters(yanked={"demo-lib": {"1.0.0": "built from a dirty tree"}})
    assert filters.yank_reason("demo-lib", "1.0.0") == "built from a dirty tree"


def test_yank_reason_true():
    filters = Filters(yanked={"demo-lib": {"1.0.1": True}})
    assert filters.yank_reason("demo-lib", "1.0.1") is True


def test_yank_unknown_project_and_version():
    filters = Filters(yanked={"demo-lib": {"1.0.0": True}})
    assert filters.yank_reason("other-lib", "1.0.0") is False
    assert filters.yank_reason("demo-lib", "2.0.0") is False


def test_is_excluded():
    filters = Filters(exclude={"demo-lib": ("0.9.0",)})
    assert filters.is_excluded("demo-lib", "0.9.0") is True
    assert filters.is_excluded("demo-lib", "0.9.1") is False
    assert filters.is_excluded("other-lib", "0.9.0") is False


@pytest.mark.parametrize(
    "configured,found",
    [
        ("1.0", "1.0.0"),
        ("1.0.0", "1.0"),
        ("1.0.0", "1.0.0"),
        ("1.0.0", "1.0.0.0"),
        ("1.0.0-alpha1", "1.0.0a1"),
        ("1.0", "v1.0"),
    ],
)
def test_equivalent_versions_match(configured, found):
    yanked = Filters(yanked={"demo-lib": {configured: True}})
    excluded = Filters(exclude={"demo-lib": (configured,)})
    assert yanked.yank_reason("demo-lib", found) is True
    assert excluded.is_excluded("demo-lib", found) is True


@pytest.mark.parametrize("configured,found", [("1.0", "1.1"), ("1.0", "2.0.0")])
def test_different_versions_do_not_match(configured, found):
    yanked = Filters(yanked={"demo-lib": {configured: True}})
    excluded = Filters(exclude={"demo-lib": (configured,)})
    assert yanked.yank_reason("demo-lib", found) is False
    assert excluded.is_excluded("demo-lib", found) is False


def test_unparseable_versions_fall_back_to_exact_string_equality():
    yanked = Filters(yanked={"demo-lib": {"not-a-version": "bad"}})
    excluded = Filters(exclude={"demo-lib": ("not-a-version",)})
    assert yanked.yank_reason("demo-lib", "not-a-version") == "bad"
    assert excluded.is_excluded("demo-lib", "not-a-version") is True
    assert yanked.yank_reason("demo-lib", "other-nonversion") is False
    assert excluded.is_excluded("demo-lib", "other-nonversion") is False


def test_unparseable_version_does_not_match_a_parseable_one():
    yanked = Filters(yanked={"demo-lib": {"1.0.0": True}})
    excluded = Filters(exclude={"demo-lib": ("1.0.0",)})
    assert yanked.yank_reason("demo-lib", "not-a-version") is False
    assert excluded.is_excluded("demo-lib", "not-a-version") is False


def test_none_version_matches_nothing():
    yanked = Filters(yanked={"demo-lib": {"1.0.0": True}})
    excluded = Filters(exclude={"demo-lib": ("1.0.0",)})
    assert yanked.yank_reason("demo-lib", None) is False
    assert excluded.is_excluded("demo-lib", None) is False


def test_lookups_normalize_the_project_name():
    filters = Filters(
        yanked={"Demo_Lib": {"1.0.0": True}}, exclude={"Demo.Lib": ("0.9.0",)}
    )
    assert filters.yanked == {"demo-lib": {"1.0.0": True}}
    assert filters.exclude == {"demo-lib": ("0.9.0",)}
    assert filters.yank_reason("Demo.Lib", "1.0.0") is True
    assert filters.yank_reason("demo-lib", "1.0.0") is True
    assert filters.is_excluded("DEMO--LIB", "0.9.0") is True


def test_filters_are_immutable():
    filters = Filters(yanked={"demo-lib": {"1.0.0": True}}, exclude={"demo-lib": ()})
    with pytest.raises(dataclasses.FrozenInstanceError):
        filters.yanked = {}
    with pytest.raises(TypeError):
        filters.yanked["other"] = {}
    with pytest.raises(TypeError):
        filters.yanked["demo-lib"]["2.0.0"] = True
    with pytest.raises(TypeError):
        filters.exclude["other"] = ()


def test_colliding_project_keys_are_rejected():
    with pytest.raises(ValueError, match="yanked has two entries for project"):
        Filters(yanked={"Demo_Lib": {"1.0": True}, "demo-lib": {"2.0": True}})
    with pytest.raises(ValueError, match="exclude has two entries for project"):
        Filters(exclude={"Demo.Lib": ("1.0",), "demo-lib": ("2.0",)})


def test_filters_do_not_alias_their_input():
    yanked = {"demo-lib": {"1.0.0": True}}
    filters = Filters(yanked=yanked)
    yanked["demo-lib"]["2.0.0"] = True
    yanked["other-lib"] = {"1.0.0": True}
    assert filters.yank_reason("demo-lib", "2.0.0") is False
    assert filters.yank_reason("other-lib", "1.0.0") is False
