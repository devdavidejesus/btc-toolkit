# JSON output reference

Every command accepts `--json` and prints **one JSON object** to stdout.
In batch mode (stdin `-` or `--file`), output is **JSON Lines**: one compact
object per line, in input order — pipe it straight into `jq`.

Errors are also JSON: `{"error": "<message>"}` plus the input under its own key —
`txid` (`tx`, `opreturn`, `inscription`, `verify`, and `decode --txid`), `address`
(`address`, `balance`, `utxo`, `validate`) or `ref` (`block`); `fees` and an offline
`decode` take no such input, so they have only `error`. The exit code tells you why
(see below).

## Stability policy

The JSON output is a contract:

- **Adding** a key is a minor version (`1.x`). Consumers must ignore unknown keys.
- **Renaming, removing, or changing the type/meaning** of a key is a **major**
  version. It will never happen silently in a patch or minor release.
- Amounts are never floats: integers in **satoshis** (`*_sats` keys, and the `sats`
  field of `confirmed` / `unconfirmed` / `total`) or fixed-point BTC strings (their
  `btc` field). Rates and sizes (`fee_rate_sat_vb`, `fees_sat_vb.*`, `vsize_vmb`,
  `size_mb`, `blocks_to_clear`, `difficulty`, `work_log2`) are JSON numbers and may
  be fractional.
- `network` is `mainnet`, `testnet`, `signet`, or `custom` — an API URL whose chain
  is unknown (`--api-url` without `-n`, or `$BTC_TOOLKIT_API_URL`). With `--api-url`
  and `-n` together, it is the network given; `-n` alone ignores
  `$BTC_TOOLKIT_API_URL` and uses the public preset.

## Exit codes

| Code | Meaning | JSON mode |
|---|---|---|
| `0` | Success | object printed |
| `1` | Network / API / runtime failure (incl. not found) | error object printed |
| `2` | Invalid input caught locally (malformed txid or block reference, an address that fails its checksum or belongs to another network, a raw transaction that does not decode) | error object printed |

Addresses are fully validated offline since 1.8.0 (Base58Check, bech32, bech32m),
so a typo exits `2` before any request is sent. A `verify` whose checks fail exits
`1`, with `"verified": false`: the API's data does not prove what it claims. So
does a transaction that is not confirmed yet.

In batch mode the exit code is the **worst** code across all items.

Errors in the command line itself, found before any item is processed — an
unknown command, flag or flag value, an invalid `--timeout`, `$BTC_TOOLKIT_TIMEOUT` or `$BTC_TOOLKIT_NETWORK`, a
malformed `--api-url` or `$BTC_TOOLKIT_API_URL`, an unreadable `--file`, or no items to process — are printed as plain text on
stderr, also with exit code `2`.

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

With `--inputs` and/or `--outputs`, an `inputs` and/or `outputs` array is added.
Addresses are computed locally from each output script (on a custom API, the
API's address is used only if it is a valid address). `spent` comes from the
`/tx/:txid/outspends` endpoint; a self-hosted Mempool without a spender index
reports `"spent": true` with `spending_txid` and `spending_vin` as `null`.

```json
{
  "inputs": [
    {
      "index": 0,
      "prev_txid": "cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd",
      "prev_vout": 1,
      "value_sats": 3000,
      "address": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
      "script_type": "P2WPKH",
      "sequence": 4294967293,
      "is_coinbase": false
    }
  ],
  "outputs": [
    {
      "index": 0,
      "value_sats": 2000,
      "address": "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
      "script_type": "P2WPKH",
      "spent": true,
      "spending_txid": "efefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefef",
      "spending_vin": 0
    },
    {
      "index": 1,
      "value_sats": 500,
      "address": null,
      "script_type": "OP_RETURN",
      "spent": false,
      "spending_txid": null,
      "spending_vin": null
    }
  ]
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
      "size_bytes": 34,
      "protocol": null
    }
  ]
}
```

An OP_RETURN output that carries no data — a bare `OP_RETURN`, `OP_RETURN OP_0`, a
Runestone marker with nothing after it — is listed with `"raw_hex": ""`,
`"decoded_text": null` and `"size_bytes": 0`.

`protocol` names a known marker by its prefix: `"runes"` (a Runestone,
`OP_RETURN OP_13`), `"omni"` (a payload starting with the ASCII bytes `omni` —
which a text message can also start with), `"witness_commitment"` (the BIP 141
`aa21a9ed` header in a coinbase transaction), or `null`. It only tags; it decodes
nothing.

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

### `validate <address> --json`

Offline: nothing is sent. `chain` is `mainnet`, `testnet/signet` (they share
address formats) or `regtest`; `program_hex` is the witness program, or the
20-byte hash of a legacy address (`witness_version` is then `null`). An invalid
address prints `{"error": ..., "address": ..., "valid": false}` and exits `2`.

```json
{
  "network": "mainnet",
  "valid": true,
  "address": "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
  "chain": "mainnet",
  "address_type": "P2WPKH",
  "witness_version": 0,
  "program_hex": "e8df018c7e326cc253faac7e46cdc51e68542c42"
}
```

### `decode <rawtx> --json` · `decode --txid <txid> --json`

Offline for a raw transaction. With `--txid`, the raw transaction is fetched and
its txid recomputed; a mismatch is an error (exit `1`). The fee is not included:
it needs the values of the outputs being spent, which a raw transaction does not
carry (`tx` has it).

```json
{
  "network": "mainnet",
  "txid": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
  "wtxid": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
  "version": 1,
  "locktime": 0,
  "segwit": false,
  "size_bytes": 204,
  "base_size_bytes": 204,
  "weight": 816,
  "vsize": 204,
  "input_count": 1,
  "output_count": 1,
  "total_output_sats": 5000000000,
  "is_rbf": false,
  "inputs": [
    {
      "index": 0,
      "prev_txid": "0000000000000000000000000000000000000000000000000000000000000000",
      "prev_vout": 4294967295,
      "script_sig_hex": "04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73",
      "sequence": 4294967295,
      "witness": [],
      "is_coinbase": true
    }
  ],
  "outputs": [
    {
      "index": 0,
      "value_sats": 5000000000,
      "address": null,
      "script_type": "P2PK",
      "script_pubkey_hex": "4104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac"
    }
  ]
}
```

### `verify <txid> --json`

```json
{
  "network": "mainnet",
  "txid": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
  "verified": true,
  "work": "weak",
  "block_hash": "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
  "block_height": 0,
  "block_time": 1231006505,
  "block_time_utc": "2009-01-03 18:15:05 UTC",
  "merkle_root": "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b",
  "position": 0,
  "branch_length": 0,
  "bits": 486604799,
  "difficulty": 1.0,
  "work_log2": 32.0,
  "checks": [
    {
      "check": "raw transaction hashes to the txid",
      "passed": true,
      "detail": "sha256d -> 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
    },
    {
      "check": "header hashes to the block hash",
      "passed": true,
      "detail": "sha256d -> 000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
    },
    {
      "check": "Merkle branch leads to the header's root",
      "passed": true,
      "detail": "0 hashes from position 0 -> 4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
    },
    {
      "check": "proof of work",
      "passed": true,
      "detail": "hash below target; difficulty 1, about 2^32.0 hashes"
    }
  ]
}
```

`work` is `"strong"` for a mainnet header at difficulty 50 T or more, and `"weak"`
otherwise (an older block, testnet, signet, or an unknown chain): the checks pass,
but that little work is cheap to fake. `difficulty` and `bits` are the header's own
(`bits` is a number, as in `block`); `work_log2` is the log2 of the expected number
of hashes to produce a header that hard. `block_height` is the API's: a header does
not contain its height. `position` is the proof's; when the transaction is the last
of an odd-sized level, the next position verifies too (the tree duplicates it), so
only inclusion is proven, not the exact index.

### `inscription <txid> --json`

Envelope detection, not the ord index: no inscription numbers, sats or owners.
Envelopes are parsed by ord's rules (an envelope without `OP_ENDIF` is ignored,
and takes no number). `body_text` is set only for an uncompressed `text/*` or
`application/json` body that is valid UTF-8.

```json
{
  "network": "mainnet",
  "txid": "abababababababababababababababababababababababababababababababab",
  "inscription_count": 1,
  "inscriptions": [
    {
      "inscription_id": "ababababababababababababababababababababababababababababababababi0",
      "input_index": 0,
      "content_type": "text/plain;charset=utf-8",
      "content_encoding": null,
      "metaprotocol": null,
      "pointer": null,
      "parents": [],
      "delegate": null,
      "metadata_bytes": 0,
      "body_bytes": 14,
      "body_sha256": "d8125d715a1f87012093af8dfd389e1d96d9c68ab58bf024a7a8d9e73056724b",
      "body_text": "Hello, Bitcoin"
    }
  ]
}
```
