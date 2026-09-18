# Next milestone: reusable product-detection inference pipeline/API

Status: implementation handoff only. No service, route, model inference or new
experiment was built/run during v0.1 closure. The model profile is
[`configs/inference_v01.json`](../configs/inference_v01.json); it is an explicit
handoff artifact, not an API configuration that is already in use.

## Reuse the existing boundaries

| Responsibility | Existing tested source | Next module responsibility |
| --- | --- | --- |
| Best-class score gate before stock NMS | `src/class_confidence_predictor.py` | Reuse `ClassConfidencePredictor` with the profile cutoffs; retain strict `>` and no runner-up relabeling |
| Post-NMS counts and zero-count classes | `src/counting.py` | Reuse `count_classes` for all five IDs |
| Class identity metadata | `configs/class_map.json` | Return source IDs/names without upgrading them to verified SKUs |
| Evaluation | `src/nms_experiment.py` | Keep offline; inference on user images must not load labels, splits or evaluate test data |
| Box rendering | `src/preview_yolo.py` | Adapt drawing into a caller-selected output path; do not overwrite experiment visuals |
| Current experiment orchestration | `src/evaluate_augmentation.py` | Reference only; do not wrap its validation loop as an API endpoint |

The current predictor imports runtime path settings through `src/train_baseline.py`.
It does not invoke training on import, but that coupling should be isolated into
runtime configuration when the reusable component is implemented. Do not edit the
frozen experiment source now; its hashes are evidence.

## Minimal implementation plan

1. Add a small `src/inference/` package when implementation is authorized. Resolve
   the profile's relative checkpoint path from the repository root, verify its hash,
   and fail clearly if the local weights are missing. Never silently download or
   substitute a model. Load it once per inference-component instance.
2. Accept one decoded image or validated image path. Preserve original dimensions
   and use the existing 320px rectangular preprocessing. Decode failures should be
   explicit errors; no implicit test-set reads or folder-wide inference.
3. Produce class scores, apply each original best-class cutoff, then stock
   class-aware NMS at 0.50. The 0.15 candidate floor does not authorize other
   classes below 0.25. Do not move class filtering after NMS.
4. Return original-image pixel boxes (`xyxy`), class/source product IDs, confidence,
   and all five visible-item counts, including zeros. Add model ID/hash and applied
   settings so a result is traceable. Do not return medical, price or stock claims.
5. Optionally render an annotated image to a caller-specified disposable output
   directory, separate from `reports/visuals` and frozen artifacts.
6. After the module is tested, add a thin FastAPI upload adapter. Keep image decoding,
   inference, result serialization and error handling in the module, not in routes.
   No frontend, databases, Docker or deployment systems are needed at this point.

Proposed result fields (contract sketch, not a generated prediction):
`model_id`, `checkpoint_sha256`, `image_width`, `image_height`, `detections`,
`products` (five count rows), `count_meaning="visible_items"`, `identity_level`,
`applied_settings`, and optional `annotated_image_path`.

## Acceptance checks for that future task

- Invalid image and missing/hash-mismatched checkpoint fail clearly.
- A no-detection result includes all five zero counts.
- Synthetic fixtures verify pre-NMS thresholds, unchanged winning class, strict
  boundaries, coordinate serialization and count consistency.
- A specifically authorized validation parity check must match the recorded model
  policy. Do not use the frozen test set or run that check during this handoff.
- Rendering cannot overwrite research artifacts; metadata documents the provisional
  model and unresolved generalization/Valser limitations.

See [reproducibility](REPRODUCIBILITY.md) for local asset requirements and
[v0.1 results](../reports/V0_1_RESULTS.md) for the evidence behind this profile.
