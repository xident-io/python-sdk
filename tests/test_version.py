"""The SDK version must be declared exactly once.

This suite exists because it was not: ``pyproject.toml`` shipped 1.2.0 while
``_config.SDK_VERSION`` said 1.0.1, so every request from a 1.2.0 install
introduced itself as 1.0.1 in the User-Agent.

The fix makes ``src/xident/_config.py::SDK_VERSION`` the only declaration and
has hatchling read it at build time. These tests hold that shape in place:
re-adding a literal ``version = "..."`` to ``pyproject.toml``, or pointing
``[tool.hatch.version]`` somewhere else, turns them red.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

import xident
from xident._config import SDK_VERSION, Config

#: Env var the release workflow injects with the pushed git tag
#: (`github.ref_name`, e.g. "v2.0.0"). Unset outside a release, so the guard
#: below has nothing to compare and skips.
RELEASE_VERSION_ENV = "XIDENT_RELEASE_VERSION"

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
REPO_ROOT = PYPROJECT.parent


def _distribution_is_this_checkout(dist: importlib.metadata.Distribution) -> bool:
    """True when `dist` is an editable/local install of THIS source tree.

    pip records the origin of a non-index install in ``direct_url.json``
    (PEP 610). An editable install from this repo carries this directory as its
    ``url``; a copy installed from PyPI has no such file. Anything else is an
    unrelated distribution that happens to share the name, and comparing its
    version against ours would be comparing two different packages.
    """
    try:
        raw = dist.read_text("direct_url.json")
    except (OSError, ValueError):
        return False
    if not raw:
        return False
    try:
        url = json.loads(raw).get("url", "")
    except json.JSONDecodeError:
        return False
    if not url.startswith("file://"):
        return False
    return Path(url_to_path(url)).resolve() == REPO_ROOT.resolve()


def url_to_path(file_url: str) -> str:
    """`file:///a/b` -> `/a/b`, without pulling in a URL library for one line."""
    return unquote(urlparse(file_url).path)

#: PEP 440 / semver core, optionally with a pre-release or build suffix.
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-.a-zA-Z0-9]+)?$")


def _pyproject_text() -> str:
    if not PYPROJECT.is_file():
        pytest.skip("pyproject.toml is not present (running from an installed distribution)")
    return PYPROJECT.read_text(encoding="utf-8")


class TestSingleSourceOfVersion:
    def test_pyproject_declares_no_literal_version(self) -> None:
        # The exact regression: a second, hand-maintained version number.
        literal = re.search(r"^version\s*=", _pyproject_text(), re.MULTILINE)
        assert literal is None, (
            "pyproject.toml declares its own version again. The version lives in "
            "src/xident/_config.py::SDK_VERSION and is read from there at build time."
        )

    def test_pyproject_declares_version_dynamic(self) -> None:
        assert re.search(
            r"^dynamic\s*=\s*\[\s*\"version\"\s*\]", _pyproject_text(), re.MULTILINE
        ), 'pyproject.toml must declare `dynamic = ["version"]` for hatchling to supply it'

    def test_hatch_reads_the_version_from_the_config_module(self) -> None:
        # Resolve the version the way the BUILD does -- apply the configured
        # pattern to the configured path -- and check it against the version
        # the package reports at RUNTIME. Disagreement here is the bug.
        tomllib = pytest.importorskip("tomllib", reason="tomllib requires Python 3.11+")
        config = tomllib.loads(_pyproject_text())

        version_source = config["tool"]["hatch"]["version"]
        source_path = PYPROJECT.parent / version_source["path"]
        pattern = version_source["pattern"]

        assert source_path == PYPROJECT.parent / "src" / "xident" / "_config.py"

        match = re.search(pattern, source_path.read_text(encoding="utf-8"))
        assert match is not None, f"pattern {pattern!r} matches nothing in {source_path}"
        assert match.group("version") == xident.__version__

    def test_installed_metadata_matches_the_runtime_version(self) -> None:
        # Catches a stale install: an editable checkout whose .dist-info was
        # written before the last bump reports the OLD number to anything
        # reading package metadata (pip, dependency resolvers, Sentry tags).
        #
        # It asserts ONLY when the installed distribution is THIS checkout.
        # Without that narrowing the test fails on ambient machine state it does
        # not control: a developer with an unrelated `pip install xident` in
        # their system Python sees this suite go red over a distribution that
        # has nothing to do with the code under test. Observed in practice — a
        # global xident 1.0.0 failed this against a 1.3.0 tree.
        try:
            dist = importlib.metadata.distribution("xident")
        except importlib.metadata.PackageNotFoundError:
            pytest.skip("xident is not installed; running straight from the source tree")

        if not _distribution_is_this_checkout(dist):
            pytest.skip(
                "the installed xident distribution is not this checkout "
                "(an unrelated install elsewhere on this machine) -- nothing to compare"
            )

        assert dist.version == xident.__version__, (
            f"installed distribution says {dist.version} but the package reports "
            f"{xident.__version__} -- reinstall with `pip install -e .`"
        )


class TestVersionIsExposedConsistently:
    def test_every_accessor_reports_the_same_version(self) -> None:
        assert xident.__version__ == SDK_VERSION
        assert xident.Xident.version() == SDK_VERSION
        assert xident.AsyncXident.version() == SDK_VERSION

    def test_version_is_a_semver_string(self) -> None:
        assert SEMVER_RE.match(SDK_VERSION), f"{SDK_VERSION!r} is not a semver string"

    def test_user_agent_carries_the_same_version(self) -> None:
        # The User-Agent is where the mismatch was actually visible on the wire.
        user_agent = Config(api_key="sk_test_123").user_agent
        assert user_agent.startswith(f"Xident-Python/{SDK_VERSION} ")

    def test_version_is_exported(self) -> None:
        assert "__version__" in xident.__all__


class TestSDKVersionMatchesReleaseTag:
    """Fails a release whose git tag disagrees with SDK_VERSION.

    Mirrors go-sdk's ``TestSDKVersionMatchesReleaseTag``: the tag is INJECTED
    by the release workflow (`github.ref_name`, no git history needed) rather
    than discovered by shelling out to git, because a build from a source
    tarball (no `.git` directory -- e.g. a `pip download` sdist) would fail a
    check that tried to read the tag itself, on exactly the artifact that
    matters. Outside a release the env var is unset and this test skips --
    there is no tag yet to compare against.
    """

    def test_tag_matches_sdk_version(self) -> None:
        tag = os.environ.get(RELEASE_VERSION_ENV)
        if not tag:
            pytest.skip(
                f"{RELEASE_VERSION_ENV} is unset -- this guard runs only on a tag push "
                "(see .github/workflows/release.yml)"
            )

        want = tag.removeprefix("v")
        assert want == SDK_VERSION, (
            f"SDK_VERSION is {SDK_VERSION!r} but the release tag is {tag!r}. "
            f"Set SDK_VERSION in _config.py to {want!r}, or re-cut the tag to match."
        )
