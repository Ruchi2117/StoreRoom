"""Independent field cohort validation and immutable, hash-addressed snapshots."""
from datetime import date, datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path, PurePosixPath
import platform
from typing import Annotated, Literal
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator
from src.inference.config import ROOT, load_config
from src.inference.images import decode_image

KEYS = ('red_bull', 'knoppers', 'valser_classic', 'valser_still', 'capri_sun_multivitamin')
TAGS = Literal['crowded', 'small_products', 'partial_occlusion', 'visually_similar_products']
Identifier = Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')]
Count = Annotated[int, Field(strict=True, ge=0, le=100000)]
PROTOCOL = ROOT/'configs/field_validation_v07.json'
PACKAGES = ('ultralytics', 'torch', 'opencv-python', 'numpy', 'Pillow', 'pydantic')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def object_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path):
    # JSON duplicate keys are ambiguous; do not silently accept the last one.
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def private_location(path, kind='data'):
    path = Path(path).resolve()
    allowed = ROOT / ('data/field_v07' if kind == 'data' else 'outputs/field_v07')
    if path.is_relative_to(ROOT) and not path.is_relative_to(allowed):
        raise ValueError('Field data/results inside the repository must stay in ignored field_v07 directories')
    return path


def runtime():
    return {'python': platform.python_version(), 'packages': {name: version(name) for name in PACKAGES}}


def freeze_protocol(destination=PROTOCOL):
    config = load_config()
    if digest(config.checkpoint) != config.checkpoint_sha256:
        raise ValueError('Frozen checkpoint hash mismatch')
    sources = sorted({*ROOT.glob('src/inference/*.py'), *ROOT.glob('src/field_*.py'),
        ROOT/'src/counting.py', ROOT/'src/class_confidence_predictor.py', ROOT/'src/train_baseline.py',
        ROOT/'configs/inference_v01.json', ROOT/'configs/class_map.json', ROOT/'reports/image_manifest.json'})
    profile = read_json(ROOT/'configs/inference_v01.json')
    frozen = {'protocol_version': 'field-counts-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
        'model_id': config.model_id, 'checkpoint': config.checkpoint.relative_to(ROOT).as_posix(),
        'checkpoint_sha256': config.checkpoint_sha256, 'inference_config': profile,
        'inference_config_sha256': digest(ROOT/'configs/inference_v01.json'),
        'class_mapping': read_json(ROOT/'configs/class_map.json')['classes'], 'count_keys': list(KEYS),
        'files': {p.relative_to(ROOT).as_posix(): digest(p) for p in sources}, 'runtime': runtime(),
        'target_images': 30, 'target_scenes': 5,
        'identity_policy': 'existing source product classes, not generic brands or verified SKUs',
        'metric': 'absolute image-by-class error / (number of images * 5)',
        'evaluation_only': True}
    write_new(destination, frozen)
    return frozen


def verify_protocol():
    frozen = read_json(PROTOCOL)
    if frozen['protocol_version'] != 'field-counts-v1' or frozen['count_keys'] != list(KEYS):
        raise ValueError('Unsupported frozen field protocol')
    for name, expected in frozen['files'].items():
        if digest(ROOT/name) != expected:
            raise ValueError('Frozen protocol dependency changed: ' + name)
    if digest(ROOT/frozen['checkpoint']) != frozen['checkpoint_sha256']:
        raise ValueError('Frozen checkpoint changed')
    if runtime() != frozen['runtime']:
        raise ValueError('Runtime differs from frozen protocol; restore recorded versions, do not silently refreeze')
    return frozen


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Scene(Strict):
    scene_id: Identifier
    permission_obtained: Literal[True]
    independent_from_holoselecta: Literal[True]
    correlated_captures_grouped: Literal[True]


class FieldImage(Strict):
    image_id: Identifier
    path: str
    scene_id: Identifier
    captured_on: date
    privacy_reviewed: Literal[True]
    original_field_capture: Literal[True]
    tags: list[TAGS] = Field(default_factory=list)


class Collection(Strict):
    cohort_id: Identifier
    purpose: Literal['independent_field_validation']
    scenes: list[Scene] = Field(min_length=1)
    images: list[FieldImage] = Field(min_length=1)


class Revision(Strict):
    revision: Annotated[int, Field(strict=True, ge=1)]
    counts: dict[str, Count]
    annotator_id: Identifier
    recorded_at: datetime
    before_predictions: Annotated[bool, Field(strict=True)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    previous_revision_sha256: str | None = None

    @model_validator(mode='after')
    def valid_counts(self):
        if set(self.counts) != set(KEYS):
            raise ValueError('Provide exactly the five class count keys, including zeros')
        if self.recorded_at.tzinfo is None:
            raise ValueError('Annotation timestamps must include a timezone')
        return self


class GroundTruth(Strict):
    image_id: Identifier
    revisions: list[Revision] = Field(min_length=1)

    @model_validator(mode='after')
    def revision_chain(self):
        previous = None
        timestamp = None
        for index, revision in enumerate(self.revisions, 1):
            if revision.revision != index or revision.previous_revision_sha256 != previous:
                raise ValueError('Ground-truth revisions must form a consecutive append-only hash chain')
            if timestamp and revision.recorded_at < timestamp:
                raise ValueError('Ground-truth revision timestamps must not go backwards')
            previous = object_hash(revision.model_dump(mode='json'))
            timestamp = revision.recorded_at
        return self


def local_image(root, relative):
    part = PurePosixPath(relative)
    if (part.is_absolute() or part.as_posix() != relative or '\\' in relative or ':' in relative
            or '..' in part.parts or len(part.parts) != 2 or part.parts[0] != 'images'):
        raise ValueError('Images must use images/<filename> relative paths without traversal')
    path = root/relative
    if path.suffix.lower() not in {'.jpg', '.jpeg', '.png'} or not path.is_file():
        raise ValueError('Missing or unsupported image: ' + relative)
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Image escapes cohort root')
    return path


def image_fingerprint(path):
    decode_image(path)  # Same input limits/validation as the unchanged inference adapter.
    with Image.open(path) as image:
        rgb = image.convert('RGB')
        pixel = hashlib.sha256(str(rgb.size).encode('ascii') + rgb.tobytes()).hexdigest()
        small = list(rgb.convert('L').resize((9, 8), Image.Resampling.LANCZOS).get_flattened_data())
        dhash = 0
        for y in range(8):
            for x in range(8):
                dhash = (dhash << 1) | (small[y*9+x] > small[y*9+x+1])
        return {'sha256': digest(path), 'pixel_sha256': pixel, 'dhash': f'{dhash:016x}',
                'width': rgb.width, 'height': rgb.height}


def validate_inputs(root):
    root = private_location(root)
    collection = Collection.model_validate(read_json(root/'collection.json'))
    truth = [GroundTruth.model_validate(row) for row in read_json(root/'ground_truth.json')]
    ids = [i.image_id for i in collection.images]
    scenes = [s.scene_id for s in collection.scenes]
    truth_ids = [t.image_id for t in truth]
    paths = [i.path for i in collection.images]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths) or len(set(scenes)) != len(scenes) or len(set(truth_ids)) != len(truth_ids):
        raise ValueError('Duplicate image, scene, path or ground-truth ID')
    if set(ids) != set(truth_ids):
        raise ValueError('Missing or extra ground-truth records')
    if set(scenes) != {i.scene_id for i in collection.images}:
        raise ValueError('Missing/unused scene assignments')
    actual = {p.relative_to(root).as_posix() for p in (root/'images').rglob('*') if p.is_file()}
    if actual != set(paths):
        raise ValueError('Image directory membership differs from collection manifest')
    original = read_json(ROOT/'reports/image_manifest.json')
    known_hashes = {r['sha256'] for r in original}
    known_pixels = {r['pixel_sha256'] for r in original}
    seen_hashes, seen_pixels = set(), set()
    records = []
    truth_by_id = {t.image_id: t for t in truth}
    for item in sorted(collection.images, key=lambda i: i.image_id):
        fingerprint = image_fingerprint(local_image(root, item.path))
        if fingerprint['sha256'] in known_hashes or fingerprint['pixel_sha256'] in known_pixels:
            raise ValueError('HoloSelecta image is not independent field data: ' + item.image_id)
        if fingerprint['sha256'] in seen_hashes or fingerprint['pixel_sha256'] in seen_pixels:
            raise ValueError('Duplicate image bytes or decoded pixels: ' + item.image_id)
        seen_hashes.add(fingerprint['sha256'])
        seen_pixels.add(fingerprint['pixel_sha256'])
        records.append({**item.model_dump(mode='json'), **fingerprint,
            'ground_truth_reference': 'ground_truth.json#'+item.image_id,
            'ground_truth': truth_by_id[item.image_id].model_dump(mode='json')})
    near_pairs = []
    for index, first in enumerate(records):
        for second in records[index+1:]:
            distance = (int(first['dhash'],16)^int(second['dhash'],16)).bit_count()
            if distance <= 8:
                if first['scene_id'] != second['scene_id']:
                    raise ValueError('Near-duplicate candidates span scene groups: '+first['image_id']+', '+second['image_id']+'; review/group or exclude before freezing')
                near_pairs.append({'a':first['image_id'],'b':second['image_id'],'dhash_distance':distance})
    return {'cohort_id': collection.cohort_id, 'scenes': [s.model_dump(mode='json') for s in sorted(collection.scenes,key=lambda s:s.scene_id)],
        'images': records, 'near_duplicate_candidates': near_pairs,
        'source_hashes': {name: digest(root/name) for name in ('collection.json','ground_truth.json')}}


def freeze_cohort(root, destination):
    private_location(destination)
    protocol = verify_protocol()
    cohort = validate_inputs(root)
    cohort.update({'created_at': datetime.now(timezone.utc).isoformat(),
        'protocol_sha256': digest(PROTOCOL), 'protocol_version': protocol['protocol_version']})
    envelope = {'cohort': cohort, 'cohort_sha256': object_hash(cohort)}
    write_new(destination, envelope)
    return envelope


def load_frozen(root, manifest, expected_hash):
    verify_protocol()
    frozen = read_json(manifest)
    cohort = frozen['cohort']
    if expected_hash != object_hash(cohort) or frozen['cohort_sha256'] != expected_hash:
        raise ValueError('Frozen cohort hash mismatch')
    if cohort['protocol_sha256'] != digest(PROTOCOL):
        raise ValueError('Frozen protocol hash mismatch')
    current = validate_inputs(root)
    if current != {k:v for k,v in cohort.items() if k not in {'created_at','protocol_sha256','protocol_version'}}:
        raise ValueError('Frozen cohort/source files changed; preserve old records and create a new freeze')
    return cohort
