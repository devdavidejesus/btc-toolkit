"""
Coverage-guided fuzzing (Atheris) of every function that parses data btc-toolkit
does not control: API responses, scripts inside them, and user input.

Properties checked:
- the OP_RETURN script parsers never raise;
- every API parser (decode_op_return, get_tx, get_balance, get_utxos,
  get_fees, get_block), fed arbitrary JSON, only raises MempoolAPIError
  (a clean, exit-code-1 error) — never a crash, never a misleading ValueError;
- input validators only raise ValueError (exit code 2).

Run from the repository root:
    pip install atheris && PYTHONPATH=. python fuzz/fuzz_parsers.py -max_total_time=60
"""

import sys
from contextlib import suppress
from unittest.mock import patch

import atheris

with atheris.instrument_imports():
    from btc_toolkit import address, balance, block, fees, opreturn, tx, utxo
    from btc_toolkit.api import MempoolAPIError

TXID = "0" * 64
ADDR = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"

# Real field names, so the fuzzer reaches the type checks behind them.
KEYS = ["vin", "vout", "status", "prevout", "value", "sequence", "is_coinbase", "confirmed", "block_height",
        "block_time", "txid", "version", "locktime", "size", "weight", "fee", "scriptpubkey", "scriptpubkey_asm",
        "scriptpubkey_type", "chain_stats", "mempool_stats", "funded_txo_sum", "spent_txo_sum", "tx_count",
        "address", "fastestFee", "halfHourFee", "hourFee", "economyFee", "minimumFee", "count", "vsize",
        "total_fee", "id", "height", "timestamp", "merkle_root", "previousblockhash", "nonce", "bits",
        "difficulty", "mediantime"]


def _json(fdp: atheris.FuzzedDataProvider, depth: int = 0) -> object:
    """An arbitrary JSON value, biased towards objects with real field names."""
    kind = fdp.ConsumeIntInRange(0, 8 if depth < 4 else 5)
    if kind == 0:
        return None
    if kind == 1:
        return fdp.ConsumeBool()
    if kind == 2:  # 64-bit, or far beyond (10**400 overflows float math)
        return fdp.ConsumeInt(8) if fdp.ConsumeBool() else 10 ** fdp.ConsumeIntInRange(18, 400)
    if kind == 3:
        return fdp.ConsumeRegularFloat() if fdp.ConsumeBool() else fdp.ConsumeFloat()
    if kind in (4, 5):
        return _text(fdp)
    if kind == 6:
        return [_json(fdp, depth + 1) for _ in range(fdp.ConsumeIntInRange(0, 3))]
    return {fdp.PickValueInList(KEYS) if fdp.ConsumeBool() else _text(fdp): _json(fdp, depth + 1)
            for _ in range(fdp.ConsumeIntInRange(0, 6))}


def _text(fdp: atheris.FuzzedDataProvider) -> str:
    # Mix raw unicode with hex-looking strings so both paths get exercised.
    if fdp.ConsumeBool():
        return fdp.ConsumeBytes(fdp.ConsumeIntInRange(0, 120)).hex()
    return fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 200))


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    target = fdp.ConsumeIntInRange(0, 6)
    s = _text(fdp)

    if target == 0:  # parsers of API data: must never raise
        opreturn._parse_scriptpubkey_asm(s)
        opreturn._extract_pushdata(s)
        opreturn._decode_hex_to_text(s)
    elif target == 1:  # full OP_RETURN decode over arbitrary API output
        prefix = "OP_RETURN " if fdp.ConsumeBool() else ""
        vout = {"scriptpubkey_type": "op_return",
                "scriptpubkey_asm": prefix + _text(fdp),
                "scriptpubkey": ("6a" if fdp.ConsumeBool() else "") + s}
        with patch.object(opreturn, "fetch_transaction", return_value={"vout": [vout]}), \
                suppress(MempoolAPIError):
            opreturn.decode_op_return(TXID)
    elif target == 2:  # user input validators: only ValueError is allowed
        with suppress(ValueError):
            opreturn._validate_txid(s)
    elif target == 3:
        with suppress(ValueError):
            balance._validate_address(s)
    elif target == 4:
        with suppress(ValueError):
            address.detect_address_type(s)
    elif target == 5:
        block._is_height(s)
        block._is_block_hash(s)
    else:  # every API parser over arbitrary JSON: only MempoolAPIError is allowed
        data, text = _json(fdp), _text(fdp)
        which = fdp.ConsumeIntInRange(0, 6)
        with patch.object(opreturn, "get_json", return_value=data), \
                patch.object(balance, "get_json", return_value=data), \
                patch.object(utxo, "get_json", return_value=data), \
                patch.object(fees, "get_json", return_value=data), \
                patch.object(block, "get_json", return_value=data), \
                patch.object(block, "get_text", return_value=text), \
                suppress(MempoolAPIError):
            result = [lambda: opreturn.decode_op_return(TXID), lambda: tx.get_tx(TXID),
                      lambda: balance.get_balance(ADDR), lambda: utxo.get_utxos(ADDR), fees.get_fees,
                      lambda: block.get_block("latest"), lambda: block.get_block(TXID)][which]()
            # What the CLI does next: derived values (fee rate, sizes, UTC times) and the JSON form.
            for item in result if isinstance(result, list) else [result]:
                item.to_dict()


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
