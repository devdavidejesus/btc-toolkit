# Security

btc-toolkit is a read-only Bitcoin explorer for the terminal. This document
describes exactly what it does, what it protects you from, and — just as
important — what it does not.

## What the tool does

- Reads public blockchain data from a Mempool-compatible API: over HTTPS from
  `https://mempool.space/api` by default, or from any instance you point it at
  with `--api-url` / `$BTC_TOOLKIT_API_URL` (your own node stack, often plain
  HTTP on your local network).
- Validates input **locally** before any request is made: transaction IDs and
  block hashes must be 64 hex characters and heights non-negative integers;
  addresses get a format check (length and characters) — full address
  validation is left to the API, which rejects invalid addresses.
- Prints results. That's it.

## What it does NOT do

- **No private keys.** It never generates, stores, imports, or touches keys,
  seeds, or wallets. There is nothing to steal from it.
- **No transaction broadcasting.** It cannot move funds.
- **No telemetry, analytics, or crash reporting.** Zero outbound requests other
  than the API queries you explicitly trigger.
- **No background activity.** Every run starts, queries, prints, and exits.
- **No configuration files.** State lives only in the flags and environment
  variables of the current invocation.

## Zero dependencies — as a security property

The package depends on the Python standard library only. There is no
`requirements.txt`, no lockfile, nothing to resolve at install time. That means:

- **No supply-chain surface** through third-party packages: a compromised
  upstream library cannot ship inside btc-toolkit, because there are none.
- The full auditable surface is this repository — about a dozen small modules.
- Monetary math uses integer satoshis, never floating point.

## Threat model

### What btc-toolkit protects you against

- Supply-chain compromise via Python dependencies (there are none)
- Hidden telemetry or data exfiltration (there is no outbound traffic except your queries)
- Floating-point errors in balances and fees (integer satoshis throughout)
- Terminal escape sequences hidden in on-chain text (OP_RETURN messages are printed with control characters escaped)
- Crashes on malformed API responses (every field is type-checked: a wrong type is a clean error, exit code 1)
- Malformed transaction IDs, block references and obviously malformed addresses reaching the network (validated locally first, exit code 2)
- Hanging on a dead endpoint (configurable `--timeout`, bounded retries on transient errors only)

### What btc-toolkit does NOT protect you against

- **A compromised or lying API backend.** By default you are trusting
  `mempool.space` to report the chain honestly. `--api-url` lets you trust
  *your own* node instead — that is the intended path to sovereignty.
- **Consensus validation.** The tool does not validate blocks, headers, or
  proofs. It reports what an API says. Only a full node validates consensus.
- **A compromised operating system, Python installation, or PyPI account.**
  See *Verifying releases* below for what you can check.
- **Privacy of your queries** toward the API operator. Queries reveal which
  addresses/txids you look at. Use your own instance or a privacy network if
  that matters to you.

## Verifying releases

Releases from 1.5.0 on are built and published by GitHub Actions through PyPI
Trusted Publishing, with PEP 740 attestations that anyone can verify; from
1.6.1 on, every file attached to a GitHub Release also carries a Sigstore bundle.
Every release is a git tag `vX.Y.Z` matching the version in `pyproject.toml`
and `btc_toolkit/__init__.py`. The published sdist on PyPI is built from that
tag; you can diff its contents against the repository. See
[`docs/releases.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/releases.md) for the exact process and how to verify
a package before installing it.

## Reporting a vulnerability

Please **do not** open a public issue for security-sensitive reports.
Report privately through GitHub:
[**Report a vulnerability**](https://github.com/devdavidejesus/btc-toolkit/security/advisories/new)
(the report is visible only to you and the maintainer). If you can't use GitHub,
email the maintainer at the address on the GitHub profile
([@devdavidejesus](https://github.com/devdavidejesus)).

You will get an initial response within 14 days — usually much sooner. Fixes
ship as patch releases, and the release notes identify the fixed issue.
