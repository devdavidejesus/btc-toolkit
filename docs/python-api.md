# Using btc-toolkit as a Python library

Everything the CLI does is available as plain, typed functions. The package
ships a `py.typed` marker and is checked with `mypy --strict` in CI, so your
type checker sees real types — not `Any`.

```bash
pip install btc-toolkit
```

```python
from btc_toolkit.tx import get_tx
from btc_toolkit.opreturn import decode_op_return

tx = get_tx("c103de95817b43f2df635ec6f35ff126ca26a7c6d20570c4b01866b2b3e69a19")
print(tx.fee, round(tx.fee_rate, 2), tx.block_height)   # 269 1.0 965818  (fee_rate is exact: 269/268)

for out in decode_op_return(tx.txid):
    print(out.size, out.decoded_text)             # 37  we are whitehats. contact us on chain
```

Every function takes an optional `network` (`"mainnet"`, `"testnet"`, `"signet"`).
All amounts are **integer satoshis**.

## Functions

| Function | Returns |
|---|---|
| `btc_toolkit.opreturn.decode_op_return(txid, network="mainnet")` | `list[OPReturnData]` |
| `btc_toolkit.tx.get_tx(txid, network="mainnet")` | `TxInfo` |
| `btc_toolkit.balance.get_balance(address, network="mainnet")` | `AddressBalance` |
| `btc_toolkit.address.get_address_overview(address, network="mainnet")` | `AddressOverview` |
| `btc_toolkit.address.detect_address_type(address, network="mainnet")` | `str` (offline: `P2PKH`, `P2SH`, `P2WPKH`, `P2WSH`, `P2TR`) |
| `btc_toolkit.utxo.get_utxos(address, network="mainnet", confirmed_only=False)` | `UtxoSet` |
| `btc_toolkit.fees.get_fees(network="mainnet")` | `FeeEstimate` |
| `btc_toolkit.block.get_block(ref, network="mainnet")` | `BlockInfo` — `ref` is a height, a hash, or `"latest"` |
| `btc_toolkit.block.get_tip_height(network="mainnet")` | `int` |

## Result types

Dataclasses. Fields first; derived values are read-only properties.

| Type | Fields | Properties |
|---|---|---|
| `OPReturnData` | `txid`, `vout_index`, `raw_hex`, `decoded_text`, `raw_bytes`, `size` | |
| `TxInfo` | `txid`, `version`, `locktime`, `size`, `weight`, `fee`, `confirmed`, `block_height`, `block_time`, `input_count`, `output_count`, `total_input`, `total_output`, `is_coinbase`, `is_rbf` | `vsize`, `fee_rate`, `block_time_utc` |
| `AddressBalance` | `address`, `confirmed_sats`, `unconfirmed_sats`, `confirmed_tx_count`, `mempool_tx_count`, `funded_sats`, `spent_sats` | `total_sats` |
| `AddressOverview` | `balance` (an `AddressBalance`), `address_type` | |
| `UtxoSet` | `address`, `utxos` (list of `Utxo`) | `total_sats`, `confirmed_count`, `unconfirmed_count` |
| `Utxo` | `txid`, `vout`, `value`, `confirmed`, `block_height` | |
| `FeeEstimate` | `fastest`, `half_hour`, `hour`, `economy`, `minimum` (sat/vB), `mempool_tx_count`, `mempool_vsize`, `mempool_total_fee` | `mempool_vsize_mb`, `blocks_to_clear` |
| `BlockInfo` | `hash`, `height`, `timestamp`, `tx_count`, `size`, `weight`, `version`, `merkle_root`, `previousblockhash`, `nonce`, `bits`, `difficulty`, `mediantime` | `timestamp_utc`, `size_mb` |

Note the Python attribute names are not always the `--json` keys: `TxInfo.fee`
is `fee_sats` in JSON. The JSON contract is documented separately in
[`json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md).

## Errors

```text
ValueError                        invalid input (bad txid, address, height) — raised before any request
MempoolAPIError                   network or API failure, including an unexpected response shape
└── NotFoundError
    ├── TransactionNotFoundError  (btc_toolkit.opreturn)
    ├── AddressNotFoundError      (btc_toolkit.balance)
    └── BlockNotFoundError        (btc_toolkit.block)
```

`MempoolAPIError` and `NotFoundError` live in `btc_toolkit.api`.

## Configuration

```python
from btc_toolkit.api import set_api_base, set_timeout

set_api_base("http://umbrel.local:3006/api")   # your own Mempool instance
set_timeout(5)                                  # seconds per request
```

These are process-wide settings. `set_api_base(None)` / `set_timeout(None)` restore the defaults.
