"""The shipped config applies leetspeak before base64 (base64 first makes leetspeak a no-op)."""

from pathlib import Path

import yaml

CFG = Path(__file__).resolve().parents[2] / "configs" / "manthan.yaml"


def test_leetspeak_comes_before_base64():
    order = yaml.safe_load(CFG.read_text())["prompt"]["converters"]
    assert order.index("leetspeak") < order.index("base64")
