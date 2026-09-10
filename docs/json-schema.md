# JSON output reference

Every command accepts `--json` and prints **one JSON object** to stdout.
In batch mode (stdin `-` or `--file`), output is **JSON Lines**: one compact
object per line, in input order — pipe it straight into `jq`.

Errors are also JSON: `{"error": "<message>", "<input-key>": "<value>"}`,
with the exit code telling you why (see below).

## Stability policy

The JSON output is a contract:

- **Adding** a key is a minor version (`1.x`). Consumers must ignore unknown keys.
- **Renaming, removing, or changing the type/meaning** of a key is a **major**
  version. It will never happen silently in a patch or minor release.
- Amounts are integers in **satoshis** (`*_sats`) or fixed-point strings in BTC
  (`confirmed`, `total`, …) — never floats.
- `network` is `mainnet`, `testnet`, `signet`, or `custom` (when `--api-url` /
  `$BTC_TOOLKIT_API_URL` is in use).

## Exit codes

| Code | Meaning | JSON mode |
|---|---|---|
| `0` | Success | object printed |
| `1` | Network / API / runtime failure (incl. not found) | error object printed |
| `2` | Invalid user input (bad txid, address, height, flag) | error object printed |

In batch mode the exit code is the **worst** code across all items.

## Schemas by command

Examples below are real outputs from the test suite (synthetic data).

### `tx <txid> --json`

```json
{
  "network": "mainnet",
  "txid": "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab",
  "status": "confirmed",
  "block_height": 777954,
  "block_time": 1677156410,
  "block_time_utc": "2023-02-23 12:46:50 UTC",
  "version": 2,
  "locktime": 0,
  "size_bytes": 236,
  "weight": 617,
  "vsize": 155,
  "fee_sats": 500,
  "fee_rate_sat_vb": 3.23,
  "input_count": 1,
  "output_count": 2,
  "total_input_sats": 2500,
  "total_output_sats": 2000,
  "is_coinbase": false,
  "is_rbf": true
}
```

### `opreturn <txid> --json`

```json
{
  "txid": "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab",
  "network": "mainnet",
  "op_return_count": 1,
  "outputs": [
    {
      "txid": "f4ac7abcb689df30ec5e8d829733622f389ca91367c47b319bc582e653cd8cab",
      "vout_index": 0,
      "raw_hex": "00000000000000000000000000000000000000000000000000000000000000000000",
      "decoded_text": null,
      "size_bytes": 34
    }
  ]
}
```

### `address <address> --json`

```json
{
  "network": "mainnet",
  "address_type": "P2PKH",
  "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "confirmed": {
    "sats": 100,
    "btc": "0.00000100"
  },
  "unconfirmed": {
    "sats": 0,
    "btc": "0.00000000"
  },
  "total": {
    "sats": 100,
    "btc": "0.00000100"
  },
  "confirmed_tx_count": 1,
  "mempool_tx_count": 0,
  "funded_sats": 100,
  "spent_sats": 0
}
```

### `balance <address> --json`

```json
{
  "network": "mainnet",
  "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "confirmed": {
    "sats": 100,
    "btc": "0.00000100"
  },
  "unconfirmed": {
    "sats": 0,
    "btc": "0.00000000"
  },
  "total": {
    "sats": 100,
    "btc": "0.00000100"
  },
  "confirmed_tx_count": 1,
  "mempool_tx_count": 0,
  "funded_sats": 100,
  "spent_sats": 0
}
```

### `fees --json`

```json
{
  "network": "mainnet",
  "fees_sat_vb": {
    "fastest": 2,
    "half_hour": 2,
    "hour": 1,
    "economy": 1,
    "minimum": 1
  },
  "mempool": {
    "tx_count": 10,
    "vsize_vb": 4000,
    "vsize_vmb": 0.0,
    "total_fee_sats": 5000,
    "blocks_to_clear": 0.0
  }
}
```

### `block <height|hash|latest> --json`

```json
{
  "network": "mainnet",
  "hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "height": 0,
  "timestamp": 1231006505,
  "timestamp_utc": "2009-01-03 18:15:05 UTC",
  "tx_count": 1,
  "size_bytes": 285,
  "size_mb": 0.0,
  "weight": 1140,
  "version": 0,
  "merkle_root": "",
  "previousblockhash": null,
  "nonce": 2083236893,
  "bits": 0,
  "difficulty": 1,
  "mediantime": 0
}
```

### `utxo <address> --json`

```json
{
  "network": "mainnet",
  "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "utxo_count": 1,
  "confirmed_count": 1,
  "unconfirmed_count": 0,
  "total": {
    "sats": 5000,
    "btc": "0.00005000"
  },
  "utxos": [
    {
      "txid": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "vout": 0,
      "value_sats": 5000,
      "confirmed": true,
      "block_height": 1
    }
  ]
}
```
