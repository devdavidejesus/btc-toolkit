# Changelog

All notable changes to btc-toolkit. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning follows [SemVer](https://semver.org/). The `--json` output follows the stability policy in
[`docs/json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md).

## [1.6.1] — 2026-09-27

### Fixed
- A malformed OP_RETURN script in an API response was reported as *invalid input* (exit code 2), blaming the
  user for bad upstream data. It is now a clean API error (exit code 1). Found by the new fuzzer.

### Added
- Coverage-guided fuzzing ([Atheris](https://github.com/google/atheris)) of every parser of untrusted data, on each
  push and pull request and weekly: `fuzz/fuzz_parsers.py`.
- GitHub Releases are created by the release workflow, with the files signed by Sigstore (keyless, using the
  workflow's identity) and the notes taken from this changelog. A tag without a changelog entry cannot be published.
- A documented policy for supported Python versions: each is dropped in the first minor release after its end of life.
- CodeQL static analysis (SAST) of the Python package and of the GitHub Actions workflows, on every push and pull request.

### Changed
- CI runs the test suite with the standard library's `unittest`, straight from the source tree: no package
  and no test runner are installed. `pytest` still works for contributors who prefer it.
- The CI tools that are still installed (`build`, `ruff`, `mypy`) are pinned by hash in `.github/requirements/`
  and installed with `--require-hashes`: a tampered package on PyPI fails the build instead of running in it.
- `CONTRIBUTING.md` documents the contribution process and requirements, including tests with every change.
- `SECURITY.md` links the private vulnerability reporting form directly and commits to a 14-day initial response.

## [1.6.0] — 2026-09-27 — Typed

### Added
- The package ships `py.typed`: projects using btc-toolkit as a library get real types in their type checker.
  The whole package passes `mypy --strict`, enforced in CI.
- `docs/python-api.md`: functions, result types and error hierarchy of the Python API.
- OpenSSF Scorecard: an independent, signed supply-chain assessment, published weekly, with a README badge.
- Private vulnerability reporting enabled on the repository (referenced by `SECURITY.md`).

### Fixed
- An unexpected JSON shape from the API (upstream drift) now raises a clean `MempoolAPIError` — exit code 1 with a
  readable message — instead of crashing with an `AttributeError` traceback.

## [1.5.0] — 2026-09-26 — Provenance

### Added
- Releases are published by GitHub Actions through **PyPI Trusted Publishing** — no API token exists anymore —
  with **PEP 740 attestations**: signed provenance linking every file on PyPI to this repository and workflow run.
- `NO_COLOR` support ([no-color.org](https://no-color.org)).
- Weekly live smoke test against mainnet: reads known on-chain facts to catch upstream API drift that mocked
  tests cannot see.
- CI: Python 3.14; macOS and Windows jobs; the built wheel is installed and tested as users get it; zero
  dependencies enforced on the wheel metadata; ruff lint.
- `CHANGELOG.md`; Changelog and Security links on PyPI.

### Changed
- Packaging uses PEP 639 SPDX license metadata (the deprecated form stops building in 2027).
- GitHub Actions pinned by commit SHA, kept current by Dependabot.
- Test coverage of the CLI layer from 62% to 92% (144 tests).

## [1.4.0] — 2026-09-10 — Automation & Trust

### Added
- Environment variables `BTC_TOOLKIT_API_URL`, `BTC_TOOLKIT_NETWORK`, `BTC_TOOLKIT_TIMEOUT` (flags always win).
- `--timeout`.
- Batch mode: stdin (`-`) and `--file` on tx, opreturn, balance, address, utxo, block; `--json` emits JSON Lines.
- `SECURITY.md` (threat model), `docs/json-schema.md` (stability policy), `docs/releases.md`.

### Fixed
- `--json` mode now exits 2 on invalid input in every command, matching text mode.

## [1.3.1] — 2026-09-07

### Fixed
- Python 3.10/3.11: two multi-line nested f-strings (3.12+ grammar) made the CLI fail to import. Broken since
  July; exposed by the new CLI test suite.

## [1.3.0] — 2026-09-07 — Sovereignty

### Added
- `--api-url` on every command: point the toolkit at your own Mempool instance.
- Signet (`--network signet`).
- Static bash and zsh completions.

## [1.2.1] — 2026-09-02

### Fixed
- PyPI page: repackaged README without a reference to a deleted screenshot.

## [1.2.0] — 2026-09-02

### Added
- `address`: aggregated overview with offline address-type detection.
- Retry with backoff on transient failures (429, 5xx, network); documented exit codes.

## [1.1.1] — 2026-07-26

### Fixed
- Images render on the PyPI page (absolute URLs).

## [1.1.0] — 2026-07-26

### Added
- `tx`: full transaction inspector (status, fees, size, I/O, coinbase and RBF flags).

## [1.0.0] — 2026-07-25

First stable release: `opreturn`, `balance`, `fees`, `block`, `utxo` — the original five-phase roadmap.

## Pre-1.0 — 2026-07-25

- 0.4.0 — block explorer · 0.3.0 — fee estimator · 0.2.0 — balance checker and unified CLI.
- Phase 1 (untagged) — OP_RETURN reader.

[1.6.1]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.2.1...v1.3.0
[1.2.1]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/devdavidejesus/btc-toolkit/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/devdavidejesus/btc-toolkit/releases/tag/v1.0.0
