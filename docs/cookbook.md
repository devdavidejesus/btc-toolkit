# `--json` cookbook

Copy-paste recipes for `btc-toolkit ... --json` and [`jq`](https://jqlang.org/). Every key used below is
documented in [`docs/json-schema.md`](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md).

Commands that take a txid, address or block read one item per line from stdin (`-`) or `--file` and print
JSON Lines, one object per input, in input order. A failed item prints an error object
(`{"error": ..., "txid": ...}`) with no data keys, so the recipes use `// empty` and `[]?` to skip it instead
of stopping `jq`.

Each sample output below is real: it was run against mainnet on 2026-11-09 with btc-toolkit 1.8.2 and jq 1.7.
The input files hold these lines:

- `txids.txt`: `a1075db55d416d3ca199f55b6084e2115b9345e16c5cf302fc80e9d5fbf5d48d` (the 10,000 BTC pizza
  transaction) and `f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16` (block 170, the first
  transfer between two people)
- `optxids.txt`: `8bae12b5f4c088d940733dcd1455efc6a3a69cf9340e17a981286d3778615684` (an OP_RETURN text),
  the pizza transaction (no OP_RETURN), and a txid of 64 zeros (not found)
- `addresses.txt`: `1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa` (the genesis address) and
  `17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ` (the pizza buyer's address)

Balances, UTXOs and fees change with the chain, so your numbers for those recipes will differ.

## Fee rate of many transactions

What did each transaction pay per virtual byte?

```bash
cat txids.txt | btc-toolkit tx - --json | jq -r '.fee_rate_sat_vb // empty'
```

```text
4191.36
0.0
```

## Height, fee and short txid as a table

Which block confirmed each transaction, and what fee did it pay in satoshis?

```bash
cat txids.txt | btc-toolkit tx - --json | jq -r '[.txid[0:12], .block_height, .fee_sats] | @tsv'
```

```text
a1075db55d41	57043	99000000
f4184fc59640	170	0
```

## Sum of an address's UTXOs above 10,000 sats

How much of an address's balance is in outputs worth spending? The JSON lists every UTXO (`--limit` only
affects the text output, while `--confirmed-only` still applies). `[]?` keeps an error object from stopping
`jq` with `Cannot iterate over null`.

```bash
btc-toolkit utxo 17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ --json | jq '[.utxos[]? | select(.value_sats > 10000) | .value_sats] | add'
```

```text
2224616
```

## Every OP_RETURN text in a list of transactions

What text did these transactions write into the chain? `?` skips the error line a failed txid produces, and
`// empty` skips outputs whose data is not text.

```bash
btc-toolkit opreturn --file optxids.txt --json | jq -r '.outputs[]?.decoded_text // empty'
```

```text
charley loves heidi
```

## Confirmed balance of several addresses

What does each address hold, in BTC? The `btc` field is a fixed-point string, so nothing is lost to floats.

```bash
btc-toolkit balance --file addresses.txt --json | jq -r 'select(.error | not) | [.address, .confirmed.btc] | @tsv'
```

```text
1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa	57.70904748
17SkEw2md5avVNyYgj6RiXuQKNwkXaxFyQ	0.02306968
```

## One line about a block

When was a block mined, and how many transactions does it hold?

```bash
btc-toolkit block 840000 --json | jq -r '"\(.height) \(.timestamp_utc) \(.tx_count) txs"'
```

```text
840000 2024-04-20 00:09:27 UTC 3050 txs
```

## Fee rate to confirm within half an hour

What fee rate should a transaction sent now use?

```bash
btc-toolkit fees --json | jq '.fees_sat_vb.half_hour'
```

```text
3
```

## Which items in a batch failed

Which lines of the input file did not work, and why? The exit code of a batch is the worst one
([exit codes](https://github.com/devdavidejesus/btc-toolkit/blob/main/docs/json-schema.md#exit-codes)); this
names the items.

```bash
btc-toolkit opreturn --file optxids.txt --json | jq -r 'select(.error) | "\(.txid): \(.error)"'
```

```text
0000000000000000000000000000000000000000000000000000000000000000: Transaction not found: 0000000000000000000000000000000000000000000000000000000000000000
```
