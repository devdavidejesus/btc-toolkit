"""
Bitcoin address and script encodings, offline.

- Bech32 (BIP 173) and bech32m (BIP 350) for SegWit and Taproot addresses
- Base58Check for legacy P2PKH and P2SH addresses
- Script type detection and the address a scriptPubKey pays to

Everything here is pure computation: no network, standard library only.
"""

from dataclasses import dataclass
import hashlib
from typing import Any

# ── hashing ─────────────────────────────────────────────────────────────


def sha256d(data: bytes) -> bytes:
    """Double SHA-256, the hash behind txids, block hashes and checksums."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


# ── bech32 / bech32m (BIP 173, BIP 350) ─────────────────────────────────

_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CONST = 1
_BECH32M_CONST = 0x2BC830A3


def _polymod(values: list[int]) -> int:
    gen = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
    chk = 1
    for v in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ v
        for i in range(5):
            chk ^= gen[i] if (top >> i) & 1 else 0
    return chk


def _hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_decode(text: str) -> tuple[str, list[int], int]:
    """Split a bech32/bech32m string into (hrp, data without checksum, checksum constant)."""
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in text):
        raise ValueError("bech32 string has a character outside printable ASCII")
    if text.lower() != text and text.upper() != text:
        raise ValueError("bech32 string mixes upper and lower case")
    text = text.lower()
    if len(text) > 90:
        raise ValueError("bech32 string is longer than 90 characters")
    pos = text.rfind("1")
    if pos < 1 or pos + 7 > len(text):
        raise ValueError("bech32 string has no valid separator or is too short")
    hrp, rest = text[:pos], text[pos + 1:]
    if any(ch not in _CHARSET for ch in rest):
        raise ValueError("bech32 data part has a character outside the bech32 alphabet")
    data = [_CHARSET.find(ch) for ch in rest]
    const = _polymod(_hrp_expand(hrp) + data)
    if const not in (_BECH32_CONST, _BECH32M_CONST):
        raise ValueError("bech32 checksum does not match (typo?)")
    return hrp, data[:-6], const


def _convertbits(data: list[int], frombits: int, tobits: int, pad: bool) -> list[int]:
    acc = bits = 0
    out = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or value >> frombits:
            raise ValueError("invalid value in bit conversion")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if pad:
        if bits:
            out.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("invalid padding in bech32 data")
    return out


def decode_segwit(hrp: str, address: str) -> tuple[int, bytes]:
    """Decode a SegWit/Taproot address for `hrp`; return (witness version, program). Raises ValueError."""
    got_hrp, data, const = _bech32_decode(address)
    if got_hrp != hrp:
        raise ValueError(f"address prefix is {got_hrp!r}, expected {hrp!r}")
    if not data:
        raise ValueError("bech32 address has no witness version")
    version = data[0]
    if version > 16:
        raise ValueError("witness version above 16")
    program = bytes(_convertbits(data[1:], 5, 8, False))
    if not 2 <= len(program) <= 40:
        raise ValueError("witness program must be 2 to 40 bytes")
    if version == 0 and len(program) not in (20, 32):
        raise ValueError("a version 0 witness program must be 20 or 32 bytes")
    if version == 0 and const != _BECH32_CONST:
        raise ValueError("a version 0 address must use bech32, not bech32m")
    if version != 0 and const != _BECH32M_CONST:
        raise ValueError("a version 1+ address must use bech32m, not bech32")
    return version, program


def encode_segwit(hrp: str, version: int, program: bytes) -> str:
    """Encode a witness program as a bech32 (v0) or bech32m (v1+) address."""
    const = _BECH32_CONST if version == 0 else _BECH32M_CONST
    data = [version] + _convertbits(list(program), 8, 5, True)
    polymod = _polymod(_hrp_expand(hrp) + data + [0] * 6) ^ const
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_CHARSET[d] for d in data + checksum)


# ── Base58Check ─────────────────────────────────────────────────────────

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58check_decode(text: str) -> bytes:
    """Decode Base58Check and verify its 4-byte checksum; return the payload. Raises ValueError."""
    if not text or any(ch not in _B58 for ch in text):
        raise ValueError("base58 string has a character outside the base58 alphabet")
    if len(text) > 100:
        raise ValueError("base58 string is too long")
    n = 0
    for ch in text:
        n = n * 58 + _B58.index(ch)
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    raw = b"\x00" * (len(text) - len(text.lstrip("1"))) + body
    if len(raw) < 5:
        raise ValueError("base58 string is too short")
    payload, checksum = raw[:-4], raw[-4:]
    if sha256d(payload)[:4] != checksum:
        raise ValueError("base58 checksum does not match (typo?)")
    return payload


def b58check_encode(payload: bytes) -> str:
    raw = payload + sha256d(payload)[:4]
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = _B58[rem] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + out


# ── networks and addresses ──────────────────────────────────────────────

# chain -> (bech32 hrp, P2PKH version byte, P2SH version byte). Testnet and signet share their encodings.
_CHAINS = {
    "mainnet": ("bc", 0x00, 0x05),
    "testnet": ("tb", 0x6F, 0xC4),
    "regtest": ("bcrt", 0x6F, 0xC4),
}
# Which address chains a --network accepts. 'custom' (--api-url) is an unknown chain: any.
_ACCEPTS = {
    "mainnet": ("mainnet",),
    "testnet": ("testnet",),
    "signet": ("testnet",),
    "custom": ("mainnet", "testnet", "regtest"),
}
_CHAIN_LABEL = {"mainnet": "mainnet", "testnet": "testnet/signet", "regtest": "regtest"}

# The one standard witness v1 program that is not a Taproot key: Pay-to-Anchor (Bitcoin Core 28).
_P2A_PROGRAM = bytes.fromhex("4e73")


def witness_type(version: int, program: bytes) -> str:
    if version == 0:
        return "P2WPKH" if len(program) == 20 else "P2WSH"
    if version == 1 and len(program) == 32:
        return "P2TR"
    if version == 1 and program == _P2A_PROGRAM:
        return "P2A"
    return f"witness_v{version}"


@dataclass
class ParsedAddress:
    """A checksum-verified address."""

    address: str  # normalized: bech32 lowercased, base58 unchanged
    chain: str  # 'mainnet', 'testnet' (also signet) or 'regtest'
    address_type: str  # P2PKH, P2SH, P2WPKH, P2WSH, P2TR, P2A or witness_vN
    witness_version: int | None
    program: bytes  # the witness program, or the 20-byte hash of a legacy address

    def to_dict(self) -> dict[str, Any]:
        return {
            "address": self.address,
            "chain": _CHAIN_LABEL[self.chain],
            "address_type": self.address_type,
            "witness_version": self.witness_version,
            "program_hex": self.program.hex(),
        }


def parse_address(address: str, network: str = "custom") -> ParsedAddress:
    """
    Fully validate a Bitcoin address offline — checksum included — for `network`.

    `network` is 'mainnet', 'testnet', 'signet', or 'custom' (any chain).
    Raises ValueError with the reason on any problem.
    """
    a = address.strip()
    if network not in _ACCEPTS:
        raise ValueError(f"unknown network: {network}")
    lower = a.lower()
    # Longest prefix first: "bcrt1" also starts with "bc".
    for chain in sorted(_CHAINS, key=lambda c: -len(_CHAINS[c][0])):
        hrp = _CHAINS[chain][0]
        if lower.startswith(hrp + "1"):
            version, program = decode_segwit(hrp, a)
            parsed = ParsedAddress(lower, chain, witness_type(version, program), version, program)
            break
    else:
        payload = b58check_decode(a)
        if len(payload) != 21:
            raise ValueError("a base58 address must carry 21 bytes (version + 20-byte hash)")
        version_byte = payload[0]
        for chain, (_, p2pkh, p2sh) in _CHAINS.items():
            if version_byte in (p2pkh, p2sh):
                kind = "P2PKH" if version_byte == p2pkh else "P2SH"
                parsed = ParsedAddress(a, chain, kind, None, payload[1:])
                break
        else:
            raise ValueError(f"unknown base58 address version byte 0x{version_byte:02x}")
    if parsed.chain not in _ACCEPTS[network]:
        raise ValueError(f"this is a {_CHAIN_LABEL[parsed.chain]} address, not a {network} one")
    return parsed


# ── scripts ─────────────────────────────────────────────────────────────

def script_type(script: bytes) -> str:
    """Name the standard pattern of a scriptPubKey, or 'nonstandard'."""
    n = len(script)
    if n == 25 and script[:3] == b"\x76\xa9\x14" and script[23:] == b"\x88\xac":
        return "P2PKH"
    if n == 23 and script[:2] == b"\xa9\x14" and script[22] == 0x87:
        return "P2SH"
    if 4 <= n <= 42 and (script[0] == 0 or 0x51 <= script[0] <= 0x60) and script[1] == n - 2:
        version = 0 if script[0] == 0 else script[0] - 0x50
        program = script[2:]
        if version == 0 and len(program) not in (20, 32):
            return "nonstandard"
        return witness_type(version, program)
    if n and script[0] == 0x6A:
        return "OP_RETURN"
    if (n == 35 and script[0] == 33 or n == 67 and script[0] == 65) and script[-1] == 0xAC:
        return "P2PK"
    if n >= 37 and 0x51 <= script[0] <= 0x60 and script[-1] == 0xAE and 0x51 <= script[-2] <= 0x60:
        return "multisig"
    return "nonstandard"


def script_address(script: bytes, network: str) -> str | None:
    """The address a scriptPubKey pays to on `network`, or None (no address form, or unknown chain)."""
    chain = {"mainnet": "mainnet", "testnet": "testnet", "signet": "testnet"}.get(network)
    if chain is None:
        return None
    hrp, p2pkh, p2sh = _CHAINS[chain]
    kind = script_type(script)
    if kind == "P2PKH":
        return b58check_encode(bytes([p2pkh]) + script[3:23])
    if kind == "P2SH":
        return b58check_encode(bytes([p2sh]) + script[2:22])
    if kind in ("P2WPKH", "P2WSH", "P2TR", "P2A") or kind.startswith("witness_v"):
        version = 0 if script[0] == 0 else script[0] - 0x50
        return encode_segwit(hrp, version, script[2:])
    return None
