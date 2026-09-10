# Release process & verification

btc-toolkit ships to PyPI from a git tag. This is the exact process — written
down so anyone can check that what's on PyPI is what's in the repository.

## Versioning

- Semantic versioning: `MAJOR.MINOR.PATCH`.
- The version lives in two places that must match: `pyproject.toml` and
  `btc_toolkit/__init__.py` (`--version` prints the latter).
- A release is an annotated git tag `vX.Y.Z` on `main`. Tags are never moved.
- JSON output changes follow the stability policy in
  [`json-schema.md`](json-schema.md): breaking changes require a major version.

## How a release is made

1. Changes land on `main` through a pull request. `main` is protected:
   the CI matrix (Python 3.10 → 3.13) must be green, and admins cannot bypass it.
2. `git tag -a vX.Y.Z` on the merge commit, `git push origin vX.Y.Z`.
3. `python -m build` produces the sdist and wheel from a clean `dist/`.
4. `twine upload dist/*` with a **scoped** PyPI token (project-only, 2FA on the account).
5. A GitHub Release is published for the tag with the changelog.
6. Post-release checks: the packaged README has no dead links or images, and a
   clean `pipx install btc-toolkit==X.Y.Z` runs a live command against the chain.

## How to verify a package yourself

```bash
# 1. Download the sdist that PyPI serves
pip download btc-toolkit==X.Y.Z --no-deps --no-binary :all: -d /tmp/verify
tar xzf /tmp/verify/btc_toolkit-X.Y.Z.tar.gz -C /tmp/verify

# 2. Compare it with the tagged source
git clone --branch vX.Y.Z https://github.com/devdavidejesus/btc-toolkit /tmp/verify/src
diff -r /tmp/verify/btc_toolkit-X.Y.Z/btc_toolkit /tmp/verify/src/btc_toolkit && echo "source matches tag"

# 3. Confirm there is nothing to resolve: zero dependencies
grep -A3 '^dependencies' /tmp/verify/src/pyproject.toml
```

PyPI also publishes SHA256 digests for every file on the release page
(`https://pypi.org/project/btc-toolkit/X.Y.Z/#files`); `pip` verifies them on
install. `pip hash` reproduces them locally.

## What is not (yet) provided

- Signed releases (Sigstore / PyPI attestations) — planned.
- Reproducible-build byte identity of the wheel — the sdist ↔ tag diff above is
  the current verification path.
