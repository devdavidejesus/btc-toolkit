<div align="center">

<img src="https://raw.githubusercontent.com/devdavidejesus/btc-toolkit/main/assets/logo.svg" alt="btc-toolkit" width="640"/>

**Bitcoin CLI toolkit — zero dependencies, no Bitcoin Core required.**

Query the Bitcoin network directly via the [Mempool.space](https://mempool.space) public API.

[![Tests](https://github.com/devdavidejesus/btc-toolkit/actions/workflows/tests.yml/badge.svg)](https://github.com/devdavidejesus/btc-toolkit/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/btc-toolkit?label=PyPI&color=F7931A&logo=pypi&logoColor=white)](https://pypi.org/project/btc-toolkit/)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://github.com/devdavidejesus/btc-toolkit/blob/main/pyproject.toml)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-success)](https://github.com/devdavidejesus/btc-toolkit/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/devdavidejesus/btc-toolkit/blob/main/LICENSE)

</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/devdavidejesus/btc-toolkit/main/assets/demo.gif" alt="btc-toolkit decoding the Liquid Network negotiation: first contact and the 2-byte :( that ended it" width="820"/>
</p>

<p align="center"><sub>The $320M Liquid Network drain was negotiated on-chain. Two of its messages, decoded live — <a href="https://dev.to/devdavidejesus/i-read-a-320m-ransom-negotiation-from-my-terminal-1159">read the whole story</a>.</sub></p>

---

## Commands

| Command | Description |
|---|---|
| `btc-toolkit opreturn <txid>` | Decode OP_RETURN messages from a transaction |
| `btc-toolkit tx <txid>` | Full transaction details: status, fees, size, I/O, RBF |
| `btc-toolkit address <address>` | Aggregated overview: type, balance, lifetime totals |
| `btc-toolkit balance <address>` | Confirmed + unconfirmed balance of any address |
| `btc-toolkit fees` | Recommended fee rates + mempool backlog |
| `btc-toolkit block <height\|hash\|latest>` | Block metadata by height, hash, or latest |
| `btc-toolkit utxo <address>` | Unspent outputs of any address |

## Installation

**Requirements:** Python 3.10+

```bash
pip install btc-toolkit
```

Or isolated, via [pipx](https://pipx.pypa.io):

```bash
pipx install btc-toolkit
```

From source:

```bash
git clone https://github.com/devdavidejesus/btc-toolkit.git
cd btc-toolkit
pip install -e .
```

**Shell completion** (optional): static scripts in
[`completions/`](https://github.com/devdavidejesus/btc-toolkit/blob/main/completions) for bash and zsh — tab-complete
commands, networks and flags, zero dependencies as always.

## Usage

### tx — inspect any transaction

```bash
btc-toolkit tx f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab
```

Shows confirmation status and block, fee and fee rate (sat/vB), total input/output, size/weight/vsize, version, locktime — and flags coinbase and RBF-signaling transactions.

![btc-toolkit tx demo](https://raw.githubusercontent.com/devdavidejesus/btc-toolkit/main/assets/demo.png)

```bash
# JSON output for scripting
btc-toolkit tx <txid> --json
```

### address — aggregated overview

```bash
btc-toolkit address 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

One call, full picture: address type (P2PKH, P2SH, P2WPKH, P2WSH, P2TR — detected offline from the prefix, per BIP 13/173/350), confirmed and unconfirmed balance, lifetime received/spent, and transaction counts.

```bash
# JSON output for scripting
btc-toolkit address <address> --json
```

### balance — check any address

```bash
btc-toolkit balance 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

Shows confirmed balance, unconfirmed (mempool) balance, and total — in BTC and satoshis. Supports all address types: Legacy (P2PKH), P2SH, SegWit (Bech32), and Taproot.

```bash
# JSON output for scripting
btc-toolkit balance <address> --json

# Testnet or signet
btc-toolkit balance <address> --network testnet
btc-toolkit balance <address> --network signet
```

BTC conversion uses integer arithmetic (no floats) — satoshi-exact, always.

### fees — current rates and mempool backlog

```bash
btc-toolkit fees
```

Shows the five recommended fee tiers (sat/vB) — fastest, half hour, hour, economy, minimum — plus mempool backlog: pending tx count, size in vMB, and a rough estimate of blocks needed to clear it.

```bash
# JSON output for scripting
btc-toolkit fees --json

# Testnet
btc-toolkit fees --network testnet
```

### block — inspect any block

```bash
btc-toolkit block latest          # chain tip
btc-toolkit block 0               # by height (genesis)
btc-toolkit block 000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f   # by hash
```

Shows height, hash, mined timestamp (UTC), tx count, size, weight, difficulty, nonce, and previous block hash.

```bash
# JSON output for scripting
btc-toolkit block latest --json

# Testnet
btc-toolkit block latest --network testnet
```

### utxo — unspent outputs of any address

```bash
btc-toolkit utxo bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq
```

Lists every UTXO sorted by value (largest first), with txid:vout, value in BTC and sats, confirmation status, and block height. Shows aggregate count and total value.

> **Known limitation:** addresses with tens of thousands of UTXOs (e.g. Satoshi's genesis address, ~76k donation outputs) exceed the upstream electrs response limit and return HTTP 400. Use `balance` for aggregate stats on such addresses — discovered and verified in production.

```bash
# Only confirmed UTXOs
btc-toolkit utxo <address> --confirmed-only

# Show more than 15 entries
btc-toolkit utxo <address> --limit 50

# JSON output (always includes all UTXOs)
btc-toolkit utxo <address> --json
```

### opreturn — decode embedded messages

```bash
btc-toolkit opreturn f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab
```

```bash
# JSON output
btc-toolkit opreturn <txid> --json

# Raw hex only
btc-toolkit opreturn <txid> --raw
```

**Seen in the wild:** the $320M Liquid Network drain (Sept 2026) was negotiated on-chain via OP_RETURN — every message of it decoded with this command, transaction IDs included: [*I Read a $320M Ransom Negotiation From My Terminal*](https://dev.to/devdavidejesus/i-read-a-320m-ransom-negotiation-from-my-terminal-1159).

### Transactions to Try

Real, verified OP_RETURN transactions on mainnet. Verify each one yourself on [mempool.space](https://mempool.space).

| TXID | Description |
|---|---|
| `f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab` | "Craig Wright is a liar and a fraud" — 34 bytes ([verify on-chain](https://mempool.space/tx/f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab)) |
| `2033435de7ce307341231e818ed937cd3a5e8597381fd83a7e5b0234f61b38d3` | "learnmeabitcoin" — 75-byte OP_RETURN with null-padded ASCII ([verify on-chain](https://mempool.space/tx/2033435de7ce307341231e818ed937cd3a5e8597381fd83a7e5b0234f61b38d3)) |

> **Note:** Satoshi's famous "Chancellor on brink of second bailout for banks" message is in the
> **coinbase scriptSig** of the genesis block — NOT in an OP_RETURN output. That's a common
> misconception. This tool reads OP_RETURN outputs only, which is the standard mechanism
> for embedding data in Bitcoin transactions (introduced as standard in Bitcoin Core v0.9.0, March 2014).

## Architecture

```
btc-toolkit/
├── btc_toolkit/
│   ├── __init__.py       # Package version
│   ├── __main__.py       # python -m entry point
│   ├── cli.py            # Unified CLI: subcommands, batch mode, env vars, exit codes
│   ├── api.py            # Shared Mempool HTTP client: retry, timeout, custom base URL
│   ├── colors.py         # Shared terminal color helpers
│   ├── opreturn.py       # OP_RETURN decoder
│   ├── balance.py        # Address balance
│   ├── fees.py           # Fee estimator
│   ├── block.py          # Block explorer
│   ├── utxo.py           # UTXO inspector
│   ├── tx.py             # Transaction inspector
│   └── address.py        # Address overview + offline type detection
├── tests/                # One file per module + test_cli.py — all API calls mocked
├── completions/          # Static bash + zsh completions
├── docs/
│   ├── json-schema.md    # --json output per command + stability policy
│   └── releases.md       # How releases are built and verified
├── SECURITY.md           # Threat model + vulnerability reporting
├── pyproject.toml
├── LICENSE               # MIT
└── README.md
```

Every subcommand shares one HTTP client (`api.py`) — new phases add a module + a subcommand, nothing else.

Zero external dependencies — Python standard library only (`urllib`, `json`, `argparse`).

## Reliability

- **Retry with backoff** — transient failures (HTTP 429, 5xx, network errors) are retried up to 3 times with exponential backoff (0.5s, 1s). Definitive errors (400, 404) fail immediately.
- **Sovereignty** — `--api-url` points every command at your own Mempool instance; `--network` covers mainnet, testnet and signet.
- **Bounded waits** — `--timeout` (default 15s) and retries only on transient failures (429/5xx/network), never on 400/404.
- **Exit codes** — `0` success, `1` network/API error, `2` invalid input. Script accordingly.

## Testing

```bash
python -m pytest tests/ -v
```

123 tests, all API calls mocked — the suite runs offline.


## How balance is computed

The Mempool.space `/address` endpoint returns `chain_stats` (confirmed) and `mempool_stats` (unconfirmed), each with `funded_txo_sum` and `spent_txo_sum` in satoshis.

```
confirmed   = chain_stats.funded_txo_sum   - chain_stats.spent_txo_sum
unconfirmed = mempool_stats.funded_txo_sum - mempool_stats.spent_txo_sum
total       = confirmed + unconfirmed
```

This is the same model used by Esplora/Electrs. Don't trust this README — verify against `https://mempool.space/api/address/<address>` yourself.

## Automation

btc-toolkit is built to sit inside pipelines. Every command takes `--json`,
and the inspecting commands read **one item per line** from stdin (`-`) or a
file (`--file`), emitting JSON Lines you can pipe straight into `jq`:

```bash
# many txids -> one JSON object per line
cat txids.txt | btc-toolkit tx - --json | jq -r '.fee_rate_sat_vb'

# or from a file (blank lines and # comments are ignored)
btc-toolkit balance --file addresses.txt --json
```

Configuration through the environment — for Docker, CI, cron:

| Variable | Effect |
|---|---|
| `BTC_TOOLKIT_API_URL` | Default for `--api-url` (your own Mempool instance) |
| `BTC_TOOLKIT_NETWORK` | Default for `--network` (`mainnet`, `testnet`, `signet`) |
| `BTC_TOOLKIT_TIMEOUT` | Default for `--timeout` (seconds, default 15) |

Flags always win over environment variables. Exit codes are a contract
(`0` ok · `1` network/API failure · `2` invalid input) in both text and JSON
mode; in batch mode the worst code wins. Full output schemas and the
stability policy: [`docs/json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md).

## Use your own node

Every command accepts `--api-url` pointing to any self-hosted
[Mempool](https://github.com/mempool/mempool) instance (Umbrel, Start9,
RaspiBlitz and similar node stacks ship one):

```bash
btc-toolkit balance <address> --api-url http://umbrel.local:3006/api
```

With your own instance, no third party sees your queries — the public
mempool.space API is the zero-setup default, not a requirement.

## What this is / What this isn't

The full threat model — what the tool protects against and what it does **not** — lives in [`SECURITY.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/SECURITY.md); how releases are built and how to verify one yourself is in [`docs/releases.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/releases.md).

**This is** an explorer client for the terminal - a fast, scriptable way to
inspect the Bitcoin blockchain without running infrastructure. Ideal for
learning, scripting, quick lookups, and teaching how Bitcoin data is
structured.

**This isn't** a substitute for a full node. All data comes from the
Mempool.space API: this tool does not validate blocks, verify merkle proofs,
or check consensus rules. You are trusting the API's view of the chain -
that's the explicit trade-off for requiring zero infrastructure. For
sovereign, trustless verification, run [Bitcoin Core](https://bitcoincore.org)
and query your own node.

## Roadmap

- [x] **Phase 1** — OP_RETURN Reader
- [x] **Phase 2** — Address Balance Checker
- [x] **Phase 3** — Fee Estimator (mempool-based)
- [x] **Phase 4** — Block Info Explorer
- [x] **Phase 5** — UTXO Set Inspector

The original roadmap shipped in v1.0.0; later releases added `tx`, `address`, sovereignty (`--api-url`, signet) and automation (batch mode, env vars). What's next lives in the [issues](https://github.com/devdavidejesus/btc-toolkit/issues) — one philosophy throughout: **zero dependencies, no Bitcoin Core, verify everything on-chain.**

## Don't Trust, Verify

Every txid, address, hex value, and technical claim in this README can be independently verified:
- Transaction data: `https://mempool.space/api/tx/<txid>`
- Address data: `https://mempool.space/api/address/<address>`
- Fee data: `https://mempool.space/api/v1/fees/recommended`
- Block data: `https://mempool.space/api/block/<hash>`
- UTXO data: `https://mempool.space/api/address/<address>/utxo`
- OP_RETURN spec: [learnmeabitcoin.com/technical/script/return](https://learnmeabitcoin.com/technical/script/return/)
- Esplora API model: [github.com/Blockstream/esplora/blob/master/API.md](https://github.com/Blockstream/esplora/blob/master/API.md)

## Support

btc-toolkit is free, MIT-licensed and has no sponsor. If it's useful to you, you can support its development on-chain:

**Bitcoin:** `bc1qulq8xfcmgxxumjx3yndkfktqgw2exh0rym45sn`

*(Single address, rotated each release. Verify it against this README's git history before sending.)*

## Contributing

Found a bug or want to propose or build a new command? Open an [issue](https://github.com/devdavidejesus/btc-toolkit/issues) or a PR. Every contribution must keep the core rules: stdlib only, tests mocked, claims verifiable on-chain.

---

<div align="center">

Licensed under [MIT](https://github.com/devdavidejesus/btc-toolkit/blob/main/LICENSE) · Built by [@devdavidejesus](https://github.com/devdavidejesus)

*"Don't Trust, Verify."*

</div>
