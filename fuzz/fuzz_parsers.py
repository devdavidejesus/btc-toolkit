"""
Coverage-guided fuzzing (Atheris) of every function that parses data btc-toolkit
does not control: scripts returned by the API, and user input.

Properties checked:
- the OP_RETURN script parsers never raise;
- decode_op_return, fed arbitrary API data, only raises MempoolAPIError
  (a clean, exit-code-1 error) — never a crash, never a misleading ValueError;
- input validators only raise ValueError (exit code 2).

Run:  pip install atheris && python fuzz/fuzz_parsers.py -max_total_time=60
"""

import sys
from contextlib import suppress
from unittest.mock import patch

import atheris

with atheris.instrument_imports():
    from btc_toolkit import address, balance, block, opreturn
    from btc_toolkit.api import MempoolAPIError

TXID = "0" * 64


def _text(fdp: atheris.FuzzedDataProvider) -> str:
    # Mix raw unicode with hex-looking strings so both paths get exercised.
    if fdp.ConsumeBool():
        return fdp.ConsumeBytes(fdp.ConsumeIntInRange(0, 120)).hex()
    return fdp.ConsumeUnicodeNoSurrogates(fdp.ConsumeIntInRange(0, 200))


def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    target = fdp.ConsumeIntInRange(0, 5)
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
    else:
        block._is_height(s)
        block._is_block_hash(s)


def main() -> None:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
