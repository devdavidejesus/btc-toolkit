# Command reference

Every command, its options and what it shows. For a quick tour, see the
[README](https://github.com/devdavidejesus/btc-toolkit#readme); for the `--json`
output of each command, see [`json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md).

Options go **after** the command: `btc-toolkit fees --network signet`, not
`btc-toolkit --network signet fees`. `-n` is short for `--network`, and
`btc-toolkit <command> --help` lists every option of a command.

- [tx](#tx--inspect-any-transaction) · [address](#address--aggregated-overview) · [balance](#balance--check-any-address) · [fees](#fees--current-rates-and-mempool-backlog) · [block](#block--inspect-any-block) · [utxo](#utxo--unspent-outputs-of-any-address) · [opreturn](#opreturn--decode-embedded-messages) · [verify](#verify--check-a-transaction-is-in-a-block) · [decode](#decode--a-raw-transaction-offline) · [validate](#validate--check-an-address-offline) · [inscription](#inscription--ordinals-envelopes)
- [Scripting and configuration](#scripting-and-configuration) · [Reliability](#reliability) · [How balance is computed](#how-balance-is-computed)

## tx — inspect any transaction

```bash
btc-toolkit tx f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab
```

Shows confirmation status and block, fee and fee rate (sat/vB), total input/output, size/weight/vsize, version, locktime — and flags coinbase and RBF-signaling transactions.

![btc-toolkit tx demo](https://raw.githubusercontent.com/devdavidejesus/btc-toolkit/main/assets/demo.png)

```bash
# Every input (the output it spends, value, address) and every output (address, spent or not, and by what)
btc-toolkit tx <txid> --inputs --outputs

# JSON output for scripting
btc-toolkit tx <txid> --json
```

Addresses in `--inputs`/`--outputs` are computed locally from each output script, not taken from the API. With `--api-url` and no `-n`, the chain is unknown: the API's address is shown if it is a valid address (it is not checked against the script).

## address — aggregated overview

```bash
btc-toolkit address 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

One call, full picture: address type (P2PKH, P2SH, P2WPKH, P2WSH, P2TR, P2A or `witness_vN` — decoded offline from the checksum-verified address, per BIP 13/173/350), confirmed and unconfirmed balance, lifetime received/spent, and transaction counts.

```bash
# JSON output for scripting
btc-toolkit address <address> --json
```

## balance — check any address

```bash
btc-toolkit balance 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
```

Shows the confirmed balance in BTC and satoshis and, when the address has a non-zero unconfirmed amount, that amount and the total, plus confirmed and mempool transaction counts. Supports all address types: Legacy (P2PKH), P2SH, SegWit (Bech32), Taproot, P2A and future witness versions.

```bash
# JSON output for scripting
btc-toolkit balance <address> --json

# Testnet or signet
btc-toolkit balance <address> --network testnet
btc-toolkit balance <address> --network signet
```

BTC conversion uses integer arithmetic (no floats) — satoshi-exact, always.

## fees — current rates and mempool backlog

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

## block — inspect any block

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

## utxo — unspent outputs of any address

```bash
btc-toolkit utxo bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq
```

Lists UTXOs sorted by value (largest first; the first 15 by default, see `--limit`), with txid:vout, value in BTC and sats, confirmation status, and block height. Shows aggregate count and total value.

> **Known limitation:** addresses with tens of thousands of UTXOs (e.g. Satoshi's genesis address, which has received over 80,000 outputs) exceed the upstream electrs response limit and return HTTP 400; `utxo` says so. Use `balance` for aggregate stats on such addresses — discovered and verified in production.

```bash
# Only confirmed UTXOs
btc-toolkit utxo <address> --confirmed-only

# Show more than 15 entries
btc-toolkit utxo <address> --limit 50

# JSON output (ignores --limit; --confirmed-only still applies)
btc-toolkit utxo <address> --json
```

## opreturn — decode embedded messages

```bash
btc-toolkit opreturn f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab
```

```bash
# JSON output
btc-toolkit opreturn <txid> --json

# Raw hex only
btc-toolkit opreturn <txid> --raw
```

Known protocol markers are named by their prefix: a Runes Runestone (`OP_RETURN OP_13`), Omni Layer (a payload starting with `omni` — a plain text message can start that way too), and the BIP 141 witness commitment in a coinbase. They are tagged, not decoded.

### Transactions to try

Real, verified OP_RETURN transactions on mainnet. Verify each one yourself on [mempool.space](https://mempool.space).

| TXID | Description |
|---|---|
| `f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab` | "Craig Wright is a liar and a fraud" — 34 bytes ([verify on-chain](https://mempool.space/tx/f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab)) |
| `2033435de7ce307341231e818ed937cd3a5e8597381fd83a7e5b0234f61b38d3` | "learnmeabitcoin" — 75-byte OP_RETURN with null-padded ASCII ([verify on-chain](https://mempool.space/tx/2033435de7ce307341231e818ed937cd3a5e8597381fd83a7e5b0234f61b38d3)) |

> **Note:** Satoshi's famous "Chancellor on brink of second bailout for banks" message is in the
> **coinbase scriptSig** of the genesis block — NOT in an OP_RETURN output. That's a common
> misconception. This tool reads OP_RETURN outputs only, which is the standard mechanism
> for embedding data in Bitcoin transactions (introduced as standard in Bitcoin Core v0.9.0, March 2014).

## verify — check a transaction is in a block

```bash
btc-toolkit verify c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19
```

Instead of taking the API's "confirmed" on faith, `verify` recomputes from raw bytes:

1. the **txid**, by hashing the raw transaction;
2. the **Merkle root**, from that txid and the proof's sibling hashes — refusing any pair of nodes that is also a valid 64-byte transaction, which could pose as a node (CVE-2017-12842), and any position past the block's last transaction;
3. the **block hash**, by hashing the 80-byte header — which must contain that root;
4. the **proof of work**: the header hash is below the target its `bits` encode, within the network's limit.

Any mismatch is `verification failed` (exit code `1`). The verdict depends only on the work proven — never on the height or date the API claims, since a forger picks those:

- **`✓ VERIFIED`** (`"work": "strong"`): a mainnet header at difficulty 50 T or more (btc-toolkit's own threshold, not a consensus rule). Forging one takes about 2^77.5 hashes — over a third of a block's work at October 2026's difficulty (about 133 T).
- **`⚠ CONSISTENT, WEAK WORK`** (`"work": "weak"`): everything checks out, but the header carries less work — an older block, or testnet, signet (block signatures are not checked) or an unknown chain. That little work is cheap to fake: treat it as consistency, not proof. With `--json`, `verified` is `true` in both cases, so a script that must reject forged proofs should also require `"work": "strong"`.

With your own instance, add `-n mainnet` so `verify` knows which chain it is checking: `btc-toolkit verify <txid> --api-url http://umbrel.local:3006/api -n mainnet`.

What it does **not** prove: the block height (the API reports it; a header does not contain it), or that the block is in the chain everyone follows. Only a full node checks everything.

## decode — a raw transaction, offline

```bash
btc-toolkit decode 0100000001...           # or pipe it: cat tx.hex | btc-toolkit decode -
btc-toolkit decode --txid <txid>           # fetch the raw tx and check it hashes to <txid>
```

Version, inputs, outputs (with their addresses and script types), witness, locktime, txid and wtxid, size, weight and vsize — computed from the bytes. The fee is not shown: it needs the values of the outputs being spent, which a raw transaction does not carry (`tx` has it).

## validate — check an address offline

```bash
btc-toolkit validate bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq
```

Verifies the checksum (Base58Check, or bech32 / bech32m per BIP 173 and BIP 350, tested against their official vectors), the network and the type — P2PKH, P2SH, P2WPKH, P2WSH, P2TR, P2A, or `witness_vN` for future versions. Nothing is sent anywhere. `balance`, `address` and `utxo` run the same check first, so a typo is caught locally (exit code `2`) and never reaches the API. With `--api-url` and no `-n`, the chain is unknown, so an address of any network is accepted.

## inscription — Ordinals envelopes

```bash
btc-toolkit inscription 6fb976ab49dcec017f1e201e84395983204ae1a7c2abf7ced0a85d692e442799
```

Finds the `OP_FALSE OP_IF "ord" … OP_ENDIF` envelopes in each input's Taproot script — parsed by ord's own rules, from its source — and shows the inscription ID, content type, encoding, metaprotocol, parents, delegate, body size and SHA-256, and the text of a text inscription (control characters escaped). This is **envelope detection, not the ord index**: it does not assign inscription numbers, track sats or owners, or apply ord's "cursed" rules. The witness comes from the API: a txid does not commit to it, so it is not verified.

## Scripting and configuration

btc-toolkit is built to sit inside pipelines. Every command takes `--json`,
and the commands that take a txid, address or block read **one item per line**
from stdin (`-`) or a file (`--file`), emitting JSON Lines you can pipe straight
into `jq` (`decode -` reads a single raw transaction from stdin):

```bash
# many txids -> one JSON object per line
cat txids.txt | btc-toolkit tx - --json | jq -r '.fee_rate_sat_vb'

# or from a file (blank lines and lines starting with # are ignored)
btc-toolkit balance --file addresses.txt --json
```

Configuration through the environment — for Docker, CI, cron:

| Variable | Effect |
|---|---|
| `BTC_TOOLKIT_API_URL` | Default for `--api-url` (your own Mempool instance); ignored by `validate` and by `decode` without `--txid`. With it, the chain is `custom`: to name it, pass `--api-url` and `-n` together (`-n` alone switches to the public presets) |
| `BTC_TOOLKIT_NETWORK` | Default for `--network` (`mainnet`, `testnet`, `signet`; anything else is an error, exit 2; ignored when an API URL is set) |
| `BTC_TOOLKIT_TIMEOUT` | Default for `--timeout` (seconds, default 15) |
| `NO_COLOR` | Any non-empty value disables colors ([no-color.org](https://no-color.org)) |

Flags always win over environment variables. Exit codes are a contract
(`0` ok · `1` network/API failure · `2` invalid input) in both text and JSON
mode; in batch mode the worst code wins. Full output schemas and the
stability policy: [`json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md).

## Reliability

- **Retry with backoff** — transient failures (HTTP 429, 500, 502, 503, 504 and network errors) get up to 3 attempts, with exponential backoff between them (0.5s, then 1s). Any other HTTP error (e.g. 400, 404) fails immediately.
- **Sovereignty** — `--api-url` points every command at your own Mempool instance; `--network` covers mainnet, testnet (testnet3) and signet.
- **Bounded waits** — `--timeout` (default 15s) applies to each network operation of each attempt, so with retries a command can wait longer than the timeout.
- **Exit codes** — `0` success, `1` network/API error (including a `verify` whose checks fail or whose transaction is not confirmed yet), `2` invalid input. Script accordingly.
- **Verifiable releases** — since v1.5.0, published from GitHub Actions via PyPI Trusted Publishing, with PEP 740 attestations tying each file to this repo; since v1.6.1, every GitHub Release also carries Sigstore-signed files ([how to verify](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/releases.md)).

## How balance is computed

The Mempool.space `/address` endpoint returns `chain_stats` (confirmed) and `mempool_stats` (unconfirmed), each with `funded_txo_sum` and `spent_txo_sum` in satoshis.

```
confirmed   = chain_stats.funded_txo_sum   - chain_stats.spent_txo_sum
unconfirmed = mempool_stats.funded_txo_sum - mempool_stats.spent_txo_sum
total       = confirmed + unconfirmed
```

This is the same model used by Esplora/Electrs. Don't trust this page — verify against `https://mempool.space/api/address/<address>` yourself.
