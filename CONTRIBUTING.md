# Contributing to btc-toolkit

Thanks for considering a contribution. Bug reports, questions and pull requests
are all welcome.

## Reporting bugs and requesting features

Open an [issue](https://github.com/devdavidejesus/btc-toolkit/issues). For a bug,
include the command you ran, what you expected, what happened, and the output of
`btc-toolkit --version`. Transaction IDs and addresses are public data, so
including them is fine.

**Security issues are different:** please do not open a public issue. Follow
[`SECURITY.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/SECURITY.md).

## How changes are made

1. Fork the repository and create a branch from `main`.
2. Make your change, with tests (see below).
3. Open a pull request against `main`. Every pull request runs the full CI:
   the test suite on Python 3.10–3.14 (Linux) and on macOS and Windows, a test of
   the built wheel, `ruff`, `mypy --strict` and CodeQL. `main` is protected — a
   pull request can only be merged when all required checks pass.
4. The maintainer reviews and merges. Releases are cut from `main` by tag and
   published by GitHub Actions (see
   [`docs/releases.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/releases.md)).

## Requirements for contributions

- **Standard library only.** btc-toolkit has zero runtime dependencies; a change
  that adds one will not be merged.
- **Tests come with the change.** New functionality and bug fixes must include
  tests in `tests/`, written with `unittest`. All API calls are mocked — the
  suite must run offline.
- **Types and lint are clean:** `mypy --strict btc_toolkit/` and
  `ruff check btc_toolkit/ tests/` pass.
- **The `--json` output is a contract.** Follow the stability policy in
  [`docs/json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md):
  adding keys is fine; renaming or removing them needs a major version.
- **Claims are verifiable.** Any transaction ID, address or on-chain fact in docs
  or tests must be checkable against the chain.
- User-visible changes get a line in
  [`CHANGELOG.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/CHANGELOG.md) under `[Unreleased]`.

## Running the checks locally

```bash
python -m unittest discover -s tests -t . -v   # tests — nothing to install
pip install ruff mypy                            # only for lint and types
ruff check btc_toolkit/ tests/
mypy --strict btc_toolkit/
```

By contributing, you agree that your contributions are licensed under the
project's [MIT License](https://github.com/devdavidejesus/btc-toolkit/blob/main/LICENSE).
