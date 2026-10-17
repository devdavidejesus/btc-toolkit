## What and why

Closes #

## Checklist

- [ ] Standard library only: no new runtime dependency
- [ ] Tests added or updated in `tests/` (`unittest`, API calls mocked, runs offline)
- [ ] `python -m coverage run -m unittest discover -s tests -t .` then `python -m coverage report` (90% or more)
- [ ] `ruff check btc_toolkit/ tests/ fuzz/ .github/scripts/` and `mypy --strict btc_toolkit/` pass
- [ ] A new parser of untrusted data has a fuzz target in `fuzz/fuzz_parsers.py`
- [ ] `--json` keys only added, never renamed or removed (`docs/json-schema.md`)
- [ ] Every txid, address or on-chain fact in docs or tests can be checked against the chain
- [ ] A user-visible change has a line under `[Unreleased]` in `CHANGELOG.md`
