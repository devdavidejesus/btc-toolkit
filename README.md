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
pipx install btc-toolkit        # or: pip install btc-toolkit · brew install devdavidejesus/tap/btc-toolkit
btc-toolkit fees                # current fee rates
btc-toolkit opreturn f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab
btc-toolkit verify c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19   # check it is in a block
btc-toolkit validate bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq                         # offline: nothing sent
```

Try it without installing anything: `uvx btc-toolkit block 0`.

Options go **after** the command: `btc-toolkit fees --network signet`, not
`btc-toolkit --network signet fees`. `-n` is short for `--network`, and
`btc-toolkit <command> --help` lists every option of a command.

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

btc-toolkit is an explorer client for the terminal: a fast, scriptable way to inspect the Bitcoin blockchain
without running infrastructure, for scripting, quick lookups, and learning how Bitcoin data is structured. It reads
a Mempool API — mempool.space by default, or your own instance. Most commands report what that API says; some
check it, or need no API at all:

| Command | Computed by btc-toolkit | Taken from the API |
|---|---|---|
| `validate` | Checksum, network and type — offline | Nothing |
| `decode` | Everything, from the raw bytes — offline | With `--txid`, the raw transaction, checked against the txid (which does not cover the witness) |
| `verify` | The txid, the Merkle root, the header hash and its proof of work | The raw transaction, the Merkle proof and the header (each checked), and the block height |
| `tx` | The addresses in `--inputs` / `--outputs`, from each output script, on a named network | Status, fee, values and what spent each output |
| `address` | The address type, from the checksum-verified address | Balances, lifetime totals and counts |
| `opreturn`, `inscription` | The decoding of the scripts and envelopes | The transaction, unchecked (`decode --txid` checks one); inscriptions could not be checked even then, as a txid does not commit to the witness |
| `balance`, `utxo` | The address check, before any request | Balances and UTXOs |
| `block`, `fees` | Nothing | Everything shown |

What no command does: validate blocks, follow the most-work chain, or check consensus rules. For sovereign,
trustless verification, run [Bitcoin Core](https://bitcoincore.org) and query it directly. The full threat model is
in [`SECURITY.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/SECURITY.md); how releases are built and how to verify one yourself, in
[`docs/releases.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/releases.md).

## verify — check a transaction is in a block

```bash
btc-toolkit verify c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19
```

Instead of taking the API's "confirmed" on faith, `verify` recomputes the txid from the raw transaction, folds it up
the Merkle proof to the root (refusing 64-byte transactions posing as nodes, CVE-2017-12842), hashes the 80-byte
header that must contain that root, and checks its proof of work against the target its `bits` encode. The verdict
depends only on the work proven:

- **`✓ VERIFIED`** (`"work": "strong"`): a mainnet header at difficulty 50 T or more (btc-toolkit's own threshold, not a consensus rule) — about 2^77.5 hashes to forge.
- **`⚠ CONSISTENT, WEAK WORK`** (`"work": "weak"`): everything checks out, but the header carries less work. That is cheap to fake: treat it as consistency, not proof. With `--json`, `verified` is `true` in both cases, so a script that must reject forged proofs should also require `"work": "strong"`.

It does **not** prove the block height (the API reports it) or that the block is in the chain everyone follows.
Details: [command reference](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/commands.md#verify--check-a-transaction-is-in-a-block).

## Installation

Python 3.11+ ([supported versions](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/releases.md#supported-python-versions)), no dependencies:

```bash
pipx install btc-toolkit                       # isolated, via pipx
pip install btc-toolkit                        # or with pip
uv tool install btc-toolkit                    # or with uv (uvx btc-toolkit ... runs it without installing)
brew install devdavidejesus/tap/btc-toolkit    # or Homebrew, on macOS and Linux
git clone https://github.com/devdavidejesus/btc-toolkit.git && pip install -e btc-toolkit   # or from source
```

**Shell completion** (optional): static scripts in [`completions/`](https://github.com/devdavidejesus/btc-toolkit/blob/main/completions) for bash, zsh and fish —
tab-complete commands, networks and flags. The Homebrew formula installs them for you.

## Scripting

Every command takes `--json`, and the commands that take a txid, address or block read one item per line from
stdin (`-`) or a file (`--file`), emitting JSON Lines:

```bash
cat txids.txt | btc-toolkit tx - --json | jq -r '.fee_rate_sat_vb'
```

Exit codes are a contract: `0` ok · `1` network/API failure (or a failed `verify`) · `2` invalid input. Output
schemas and the stability policy: [`docs/json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md); environment variables
(`BTC_TOOLKIT_API_URL`, `BTC_TOOLKIT_NETWORK`, `BTC_TOOLKIT_TIMEOUT`, `NO_COLOR`), retries and timeouts:
[scripting and configuration](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/commands.md#scripting-and-configuration).

Every command is also a plain, typed Python function (the package ships `py.typed`):

```python
from btc_toolkit.opreturn import decode_op_return

for out in decode_op_return("c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19"):
    print(out.decoded_text)   # we are whitehats. contact us on chain
```

Functions, result types and errors: [`docs/python-api.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/python-api.md).

## Use your own Mempool instance

Every command accepts `--api-url` pointing to a self-hosted [Mempool](https://github.com/mempool/mempool) instance,
which runs on top of your own Bitcoin node (Umbrel, Start9, RaspiBlitz and similar node stacks offer it as an app):

```bash
btc-toolkit balance <address> --api-url http://umbrel.local:3006/api -n mainnet
```

`-n` tells btc-toolkit which chain your instance serves. Without it the chain is `custom` (unknown): addresses of
any Bitcoin network (mainnet, testnet/signet, regtest) are accepted, `tx` shows the API's addresses, and `verify`
reports the work as weak. Results never link to mempool.space when you use your own instance. With your own
instance, no third party sees your queries — the public mempool.space API is the zero-setup default, not a
requirement.

## Seen in the wild

- The $320M Liquid Network drain (Sept 2026) was negotiated on-chain via OP_RETURN — every message of it decoded
  with `opreturn`, transaction IDs included: [*I Read a $320M Ransom Negotiation From My Terminal*](https://dev.to/devdavidejesus/i-read-a-320m-ransom-negotiation-from-my-terminal-1159).
- The wallet holding 562 BTC from the Coldcard hack (July 2026) became a message board: 49 OP_RETURN messages, read
  with `opreturn --file`: [*49 Messages to a Thief*](https://dev.to/devdavidejesus/49-messages-to-a-thief-what-people-wrote-to-the-coldcard-hackers-bitcoin-wallet-l1n).

btc-toolkit is listed on bitcoin.org's [Development page](https://bitcoin.org/en/development#more) and among the
[developer tools](https://www.lopp.net/bitcoin-information/developer-tools.html) in Jameson Lopp's Bitcoin resources.

## Roadmap

The original five-phase roadmap (OP_RETURN reader, balance, fees, blocks, UTXOs) shipped in v1.0.0; every release
since is in the [CHANGELOG](https://github.com/devdavidejesus/btc-toolkit/blob/main/CHANGELOG.md). What's next lives in the [issues](https://github.com/devdavidejesus/btc-toolkit/issues) — testnet4
([#64](https://github.com/devdavidejesus/btc-toolkit/issues/64)), plain Esplora backends ([#65](https://github.com/devdavidejesus/btc-toolkit/issues/65)) and a `--json` cookbook ([#63](https://github.com/devdavidejesus/btc-toolkit/issues/63));
[`good first issue`](https://github.com/devdavidejesus/btc-toolkit/contribute) marks the easy ones. Out of scope,
for good: keys, signing, broadcasting and runtime dependencies.

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

*(Public address — donations are visible on-chain, as everything here is.)*

## Contributing

Found a bug or want to propose or build a new command? Open an [issue](https://github.com/devdavidejesus/btc-toolkit/issues) or a PR. Every contribution keeps the
core rules — stdlib only, tests with every change, claims verifiable on-chain. The process, the project layout and
how to run the tests are in [`CONTRIBUTING.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/CONTRIBUTING.md).

---

<div align="center">

Licensed under [MIT](https://github.com/devdavidejesus/btc-toolkit/blob/main/LICENSE) · Built by [@devdavidejesus](https://github.com/devdavidejesus)

*"Don't Trust, Verify."*

</div>
