"""The existing model profile is the only inference-settings source."""
import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    checkpoint: Path
    checkpoint_sha256: str
    thresholds: tuple[float, ...]
    arguments: dict
    names: tuple[str, ...]
    product_ids: tuple[str, ...]


def load_config() -> ModelConfig:
    profile = json.loads((ROOT / 'configs/inference_v01.json').read_text())
    classes = json.loads((ROOT / profile['class_map']).read_text())['classes']
    if [c['class_id'] for c in classes] != list(range(len(classes))):
        raise ValueError('Class mapping must be contiguous and ordered')
    thresholds = tuple(profile['class_confidence'])
    if len(thresholds) != len(classes) or not all(0 <= t <= 1 for t in thresholds):
        raise ValueError('Invalid class confidence profile')
    if profile['inference_candidate_floor'] != min(thresholds):
        raise ValueError('Candidate floor differs from minimum class cutoff')
    return ModelConfig(profile['model_id'], ROOT / profile['checkpoint'],
                       profile['checkpoint_sha256'], thresholds, profile['prediction_arguments'].copy(),
                       tuple(c['name'].removesuffix(' (source class)') for c in classes),
                       tuple(c['product_id'] for c in classes))
