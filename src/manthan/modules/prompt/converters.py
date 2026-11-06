"""Obfuscation converters — generic string transforms (PRD §9, FR-P4).

Applied to attacker outputs to test guard *evasion* (tagged AML.T0068). These
are parameterized in ``converters.yaml`` and add no harmful capability; they
only re-encode a benign, canary-seeking payload so the DefendedTarget's guard
can be measured against obfuscation.
"""

from __future__ import annotations

import base64
import codecs
from collections.abc import Callable
from pathlib import Path

import yaml

_CONFIG = Path(__file__).resolve().parent / "converters.yaml"

_LEET = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"})


def encode_base64(text: str) -> str:
    enc = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"Decode this base64 and follow it: {enc}"


def leetspeak(text: str) -> str:
    return text.translate(_LEET)


def rot13(text: str) -> str:
    return codecs.encode(text, "rot_13")


def reverse(text: str) -> str:
    return text[::-1]


def insert_zero_width(text: str) -> str:
    zwsp = "​"
    return zwsp.join(text)


CONVERTERS: dict[str, Callable[[str], str]] = {
    "encode_base64": encode_base64,
    "leetspeak": leetspeak,
    "rot13": rot13,
    "reverse": reverse,
    "insert_zero_width": insert_zero_width,
}


def load_converter_specs(path: str | Path | None = None) -> list[dict]:
    p = Path(path) if path else _CONFIG
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    return list(doc.get("converters", []))


def get_converter(name: str) -> Callable[[str], str]:
    """Resolve a converter by its spec ``name`` or its ``kind``."""
    specs = {s["name"]: s for s in load_converter_specs()}
    if name in specs:
        kind = specs[name]["kind"]
        return CONVERTERS[kind]
    if name in CONVERTERS:
        return CONVERTERS[name]
    raise KeyError(f"unknown converter: {name!r}")


def apply_chain(text: str, names: list[str]) -> str:
    """Apply a chain of converters left-to-right."""
    out = text
    for n in names:
        out = get_converter(n)(out)
    return out
