<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/devdavidejesus/btc-toolkit/main/assets/logo-dark.svg"/>
  <img src="https://raw.githubusercontent.com/devdavidejesus/btc-toolkit/main/assets/logo.svg" alt="btc-toolkit" width="480"/>
</picture>

**Read and verify Bitcoin from your terminal.** Zero dependencies, no Bitcoin Core required.

Reads the chain through the [Mempool.space](https://mempool.space) public API, or your own Mempool instance, and checks what it can by computation: address checksums offline, and a transaction against its block's Merkle proof and proof of work.

[![Tests](https://github.com/devdavidejesus/btc-toolkit/actions/workflows/tests.yml/badge.svg)](https://github.com/devdavidejesus/btc-toolkit/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/btc-toolkit?label=PyPI&color=F7931A&logo=pypi&logoColor=white)](https://pypi.org/project/btc-toolkit/)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://github.com/devdavidejesus/btc-toolkit/blob/main/pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success)](https://github.com/devdavidejesus/btc-toolkit/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/devdavidejesus/btc-toolkit/blob/main/LICENSE)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/devdavidejesus/btc-toolkit/badge)](https://scorecard.dev/viewer/?uri=github.com/devdavidejesus/btc-toolkit)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14966/badge)](https://www.bestpractices.dev/projects/14966)

</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/devdavidejesus/btc-toolkit/main/assets/demo.gif" alt="btc-toolkit decoding the Liquid Network negotiation: first contact and the 2-byte :( that ended it" width="820"/>
</p>

<p align="center"><sub>The $320M Liquid Network drain was negotiated on-chain. Two of its messages, decoded live — <a href="https://dev.to/devdavidejesus/i-read-a-320m-ransom-negotiation-from-my-terminal-1159">read the whole story</a>.</sub></p>

---

## Quick start

```bash
pipx install btc-toolkit        # or: pip install btc-toolkit · uv tool install btc-toolkit · brew install devdavidejesus/tap/btc-toolkit
btc-toolkit fees                # current fee rates
btc-toolkit opreturn f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab
btc-toolkit verify c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19   # check it is in a block
btc-toolkit validate bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq                         # offline: nothing sent
```

Try it without installing anything: `uvx btc-toolkit block 0`. Options go after the command (`btc-toolkit fees -n signet`).
Python 3.11+, no dependencies; shell completions for
bash, zsh and fish are in [`completions/`](https://github.com/devdavidejesus/btc-toolkit/blob/main/completions) (the Homebrew formula installs them).

## Commands

| Command | Description |
|---|---|
| `btc-toolkit opreturn <txid>` | Decode OP_RETURN messages from a transaction |
| `btc-toolkit tx <txid>` | Transaction details: status, fees, size, input/output totals, RBF |
| `btc-toolkit address <address>` | Aggregated overview: type, balance, lifetime totals |
| `btc-toolkit balance <address>` | Confirmed + unconfirmed balance of any address |
| `btc-toolkit fees` | Recommended fee rates + mempool backlog |
| `btc-toolkit block <height\|hash\|latest>` | Block metadata by height, hash, or latest |
| `btc-toolkit utxo <address>` | Unspent outputs of any address |
| `btc-toolkit verify <txid>` | Check a transaction is in a block **by computation**: its Merkle proof and the header's proof of work |
| `btc-toolkit decode <rawtx>` | Decode a raw transaction **offline** (or `--txid`: fetch it and check its hash) |
| `btc-toolkit validate <address>` | Check an address **offline**: checksum, network, type — nothing is sent |
| `btc-toolkit inscription <txid>` | Ordinals inscription envelopes in a transaction: content type, size, SHA-256, text |

Every command, option and example: [**command reference**](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/commands.md).

## What it verifies, and what it doesn't

**Inspect Bitcoin data. Verify what you can. Know what you trust.**

- **Offline, nothing sent:** `validate`, and `decode` given a raw transaction, work only from the bytes you give them.
- **Checked by computation:** `verify` recomputes the txid, the Merkle root and the proof of work instead of taking
  the API's "confirmed" on faith.
- **Reported by the API:** the other commands show what a Mempool API says — mempool.space by default, or
  [your own instance](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/commands.md#use-your-own-mempool-instance) on your own node with `--api-url`, so no
  third party sees your queries.

No command validates blocks or follows the most-work chain; for that, run [Bitcoin Core](https://bitcoincore.org).
What each command computes and what it trusts: [command reference](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/commands.md#what-each-command-verifies);
threat model: [`SECURITY.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/SECURITY.md).

## verify — check a transaction is in a block

```bash
btc-toolkit verify c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19
```

**`✓ VERIFIED`** means the block header carries strong proof of work; **`⚠ CONSISTENT, WEAK WORK`** means everything
matches but that work is cheap to fake. With `--json`, scripts that must reject forged proofs should require
`"work": "strong"`. How it works: [command reference](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/commands.md#verify--check-a-transaction-is-in-a-block).

## Scripting

Every command takes `--json`, reads many items from stdin or `--file`, and has stable exit codes
(`0` ok · `1` network/API failure or a failed `verify` · `2` invalid input):

```bash
cat txids.txt | btc-toolkit tx - --json | jq -r '.fee_rate_sat_vb'
```

Every command is also a typed Python function: [`docs/python-api.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/python-api.md). Output schemas:
[`docs/json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md).
Copy-paste `jq` recipes: [`docs/cookbook.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/cookbook.md).

## Seen in the wild

- [*I Read a $320M Ransom Negotiation From My Terminal*](https://dev.to/devdavidejesus/i-read-a-320m-ransom-negotiation-from-my-terminal-1159):
  the Liquid Network drain, negotiated on-chain via OP_RETURN, every message decoded with `opreturn`.
- [*49 Messages to a Thief*](https://dev.to/devdavidejesus/49-messages-to-a-thief-what-people-wrote-to-the-coldcard-hackers-bitcoin-wallet-l1n):
  the OP_RETURN messages sent to the wallet holding 562 BTC from the Coldcard hack.

Listed on bitcoin.org's [Development page](https://bitcoin.org/en/development#more), among the
[developer tools](https://www.lopp.net/bitcoin-information/developer-tools.html) in Jameson Lopp's Bitcoin resources,
and in [awesome-osint](https://github.com/jivoi/awesome-osint).

## Roadmap

Next: testnet4 ([#64](https://github.com/devdavidejesus/btc-toolkit/issues/64)), plain Esplora backends
([#65](https://github.com/devdavidejesus/btc-toolkit/issues/65)) and a `--json` cookbook ([#63](https://github.com/devdavidejesus/btc-toolkit/issues/63)).
Out of scope, for good: keys, signing, broadcasting and runtime dependencies. Past releases: [CHANGELOG](https://github.com/devdavidejesus/btc-toolkit/blob/main/CHANGELOG.md).

## Support

btc-toolkit is free, MIT-licensed and has no sponsor. If it's useful to you, you can support its development on-chain:

**Bitcoin:** `bc1qulq8xfcmgxxumjx3yndkfktqgw2exh0rym45sn`

*(Public address — donations are visible on-chain, as everything here is.)*

## Contributing

Bug reports, ideas and pull requests are welcome: [issues](https://github.com/devdavidejesus/btc-toolkit/issues) ·
[`CONTRIBUTING.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/CONTRIBUTING.md) (stdlib only, tests with every change, claims verifiable on-chain).

---

<div align="center">

Licensed under [MIT](https://github.com/devdavidejesus/btc-toolkit/blob/main/LICENSE) · Built by [@devdavidejesus](https://github.com/devdavidejesus)

*"Don't Trust, Verify."*

</div>
