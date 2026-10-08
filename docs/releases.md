# Release process & verification

btc-toolkit ships to PyPI from a git tag, built and published by GitHub Actions.
This is the exact process — written down so anyone can check that what's on
PyPI is what's in the repository.

## Versioning

- Semantic versioning: `MAJOR.MINOR.PATCH`. Changes are listed in
  [`CHANGELOG.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/CHANGELOG.md).
- The version lives in two places that must match: `pyproject.toml` and
  `btc_toolkit/__init__.py` (`--version` prints the latter). CI checks that the
  built wheel reports the version declared in `pyproject.toml`.
- A release is an annotated git tag `vX.Y.Z` on `main`. Tags are never moved.
- JSON output changes follow the stability policy in
  [`json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md):
  breaking changes require a major version.

## How a release is made

1. Changes land on `main` through a pull request. `main` is protected: the test
   matrix must be green and admins cannot bypass it. CI runs the suite on
   Python 3.11–3.14 (plus macOS and Windows), installs and tests the **built
   wheel**, verifies it declares zero dependencies, and lints.
2. The maintainer pushes a tag `vX.Y.Z` on the merge commit.
3. The [`release`](https://github.com/devdavidejesus/btc-toolkit/blob/main/.github/workflows/release.yml)
   workflow checks that the tag points to a commit on `main` and matches the
   package version, builds the sdist and wheel from a clean checkout, with the
   build tool and the build backend (setuptools) pinned by hash, and
   smoke-tests the wheel. Runs for the same tag never overlap, and a run for a
   version already on PyPI publishes nothing. If a later job fails, use
   "Re-run failed jobs" (re-running everything would skip publishing).
4. The same workflow publishes to PyPI through **Trusted Publishing**: PyPI
   accepts the upload because GitHub proves, with a short-lived OIDC token,
   which repository and workflow produced it. There is no API token to leak.
5. Publishing generates **PEP 740 attestations**: a Sigstore signature binding
   each file on PyPI to this repository, workflow and commit. PyPI shows them on
   the release page ("Verified details").
6. The same workflow signs the files with Sigstore (keyless, with the workflow's own
   identity) and creates the GitHub Release, with the notes taken from `CHANGELOG.md`
   and the signed files attached. A tag without a CHANGELOG entry, or with an
   empty one, fails before anything is published.

A weekly workflow also reads known on-chain facts from mainnet
([`live-smoke.yml`](https://github.com/devdavidejesus/btc-toolkit/blob/main/.github/workflows/live-smoke.yml)),
catching upstream API changes that the mocked test suite cannot see.

## Supported Python versions

btc-toolkit supports every CPython version that is still maintained upstream
(see [devguide.python.org/versions](https://devguide.python.org/versions/)). When a
version reaches end of life, it is dropped in the **next minor release**, and the
change is listed in `CHANGELOG.md`. Existing releases keep working on it; `pip`
simply stops offering newer ones to that interpreter. Python 3.10 reached end of
life on 2026-10-01 and was dropped in 1.7.0.

## How to verify a package yourself

**GitHub Release files** — every file attached to a release (from 1.6.1 on) has a
Sigstore bundle next to it (`<file>.sigstore.json`):

```bash
pip install sigstore
python -m sigstore verify github btc_toolkit-X.Y.Z-py3-none-any.whl \
  --cert-identity https://github.com/devdavidejesus/btc-toolkit/.github/workflows/release.yml@refs/tags/vX.Y.Z
```

**Provenance** — confirm a file on PyPI was built by this repository's workflow
(releases from 1.5.0 on):

```bash
pip install pypi-attestations
pypi-attestations verify pypi --repository https://github.com/devdavidejesus/btc-toolkit \
  pypi:btc_toolkit-X.Y.Z-py3-none-any.whl
```

**Source** — confirm the published sdist matches the tagged code:

```bash
pip download btc-toolkit==X.Y.Z --no-deps --no-binary :all: -d /tmp/verify
tar xzf /tmp/verify/btc_toolkit-X.Y.Z.tar.gz -C /tmp/verify
git clone --branch vX.Y.Z https://github.com/devdavidejesus/btc-toolkit /tmp/verify/src
diff -r /tmp/verify/btc_toolkit-X.Y.Z/btc_toolkit /tmp/verify/src/btc_toolkit && echo "source matches tag"
```

**Dependencies** — there is nothing to resolve:

```bash
grep -A3 '^dependencies' /tmp/verify/src/pyproject.toml
```

PyPI also publishes SHA256 digests for every file on the release page; `pip`
verifies them on install.

## What is not (yet) provided

- Reproducible-build byte identity of the wheel. The attestation proves where a
  file was built; the sdist ↔ tag diff above proves what it contains.
- Releases up to 1.4.0 were uploaded manually and carry no attestations.
