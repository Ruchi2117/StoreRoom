"""Enforce the single-change comparison and preserve the previous experiment."""
import json
from src.convert_smoke import ROOT, digest


def verify_preservation():
    hashes = json.loads((ROOT / "reports/baseline_002_preservation.json").read_text())
    for path, expected in hashes.items():
        if digest(ROOT / path) != expected:
            raise ValueError(f"Frozen BASELINE_001 artifact changed: {path}")
    return len(hashes)


def verify_configuration():
    import yaml
    old = yaml.safe_load((ROOT / "configs/baseline_001.yaml").read_text())
    new = yaml.safe_load((ROOT / "configs/baseline_002.yaml").read_text())
    changes = {k: [old.get(k), new.get(k)] for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    if changes != {"epochs": [10, 30]}:
        raise ValueError(f"Uncontrolled configuration changes: {changes}")
    return changes
