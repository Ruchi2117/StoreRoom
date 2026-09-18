# Reproducibility and artifact policy

The repository versions source, tests, exact configurations, split/group metadata,
annotation inventories, small metric snapshots and experiment logs. Historical
reports are evidence and are not rewritten to match later choices.

## Recorded inputs

| Input | Record |
| --- | --- |
| HoloSelecta V1 / CC BY 4.0 | `data/README.md`, `reports/download_manifest.json` |
| Original archive SHA-256 | `4492e5f544a035cf4884626187ebf39ab5e703f71a3ff05733b6c11baf926afb` |
| Export manifest SHA-256 | `878424031a9ab66bb64a89ac4dfbb5bebc889d67ef5e295d5e3ee494edae5513` |
| Split and class mapping | `configs/splits.json`, `configs/class_map.json` |
| Original pretrained YOLO11n hash | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| BASELINE_002 checkpoint hash | `7e048d48a3b80cf5cab1aafb30dfb63f7f20c94e12b26ded8aac35de5ecd0cbd` |
| AUGMENTATION_001 checkpoint hash | `099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4` |
| Full trainer inputs / runtime / duration | `configs/augmentation_001.yaml`, `reports/augmentation_001_training.json` |
| Inference settings / model hashes | `reports/augmentation_001_setup.json` |
| Raw validation predictions and metrics | `reports/augmentation_001_a.json`, `reports/augmentation_001_b.json` |
| Evaluator | `src/nms_experiment.py`, `src/counting.py` |
| Class-specific pre-NMS gate | `src/class_confidence_predictor.py` |

Training is CPU, seed 42, deterministic, 30 epochs, batch 4, 320px, AdamW lr0=0.001;
all other learning-rate/warm-up/augmentation settings are in the recorded YAML.
Best-checkpoint selection uses stock training-validation fitness. The final counting
comparison uses the same fixed class-specific inference policy for both checkpoints.
Do not confuse training-internal conf=0.001 / NMS=0.70 metrics with the final
Red Bull=0.15, others=0.25 / NMS=0.50 fixed-cutoff metrics.

## Runtime restoration (not an instruction to rerun an experiment)

Recorded runtime: Windows, CPython 3.14.4, PyTorch 2.14.0+cpu,
Torchvision 0.29.0+cpu, Ultralytics 8.4.154, Supervision 0.30.3.
`requirements-lock.txt` records the full environment. To install the recorded
runtime in a separate environment, use the existing requirement files in order:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-cpu.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-runtime.txt
```

No dependencies were changed during the v0.1 closure. Availability of those historical
wheels on another platform is not guaranteed; do not silently upgrade for a comparison.

## Local-only artifacts and fresh-clone limitations

Datasets/archives, `.venv`, caches, model binaries, `runs/` and rendered comparison
images are intentionally ignored. They were **not deleted**. A Git clone alone is
not the artifact-complete research checkout and cannot pass the full artifact suite.
The frozen model binary is not obtainable by cloning this repository; restore the
locally preserved checkpoint with its SHA-256 above. There is no configured artifact
registry or fabricated download URL. The source dataset download URLs are recorded
in `reports/download_manifest.json`; attribution remains in `data/README.md`.

To restore the full research checkout, copy the preserved `data/`, `runs/` and
`reports/visuals/` artifacts, then verify against
`reports/independent_validation_001_preservation.json` and the dataset manifest.
That snapshot covers 921 files, including both checkpoints and all raw images/XMLs.
It is an inventory of required historical evidence, not a promise that every listed
artifact is distributed in Git. Existing tests deliberately fail for missing assets.

Some historical records and frozen dataset YAML contain the original absolute
Windows workspace path. Exact replay currently assumes the original path layout.
For a relocated reproduction, retain original manifests and document path overrides
in a separate run/configuration; do not edit frozen evidence in place or claim its
hashes still match. Guards refuse to overwrite completed experiments. The next
product module should resolve repository-relative model paths without rewriting
research scripts. These portability limitations remain explicit.

The recorded training entry point is `src/train_augmentation.py`; the matched
validation entry point is `src/evaluate_augmentation.py`. They demonstrate exact
arguments and evaluation order, but are **not** commands to rerun during closure.
No test evaluation, threshold tuning or training is required to verify the current
artifact-complete checkout:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -c "from src.independent_validation_001_audit import verify_protected; print(verify_protected())"
```

Expected: 36 passing tests and 921 protected files verified, with frozen exported
dataset hashes also verified. Unit tests may run synthetic tensor/NMS fixtures;
they do not load a trained model for new image inference.

## Git policy

- Keep source, tests, configs, compact JSON/CSV metrics and curated experiment logs.
- Keep dataset bytes, weights, generated image previews and disposable outputs local.
- Ignore environment secrets, private keys, caches, temporary files and archives.
- `.gitattributes` disables automatic newline conversion to preserve manifest hashes,
  including on Windows systems with `core.autocrlf=true`. Existing whitespace in
  frozen logs/source is preserved rather than reformatted.
- Prior reports include the one frozen BASELINE_001 test result. It is historical
  evidence, never a target for tuning or a reason to re-evaluate the test set.
