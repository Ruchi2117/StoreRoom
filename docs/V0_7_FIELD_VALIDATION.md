# V0.7 — independent field validation

This workflow measures the **unchanged provisional system on new field scenes**.
It does not train, tune, choose thresholds or reuse the protected test set. There
is currently no collected field cohort; the empty local starter is not evidence.

## Collection and privacy protocol

Seek permission from the responsible shop/site owner before capture. Explain that
photos are for a local research evaluation of visible product counts, not customer
identification, sales tracking or surveillance. Store only a yes/no permission
attestation in the cohort. Keep any necessary detailed consent record separately
with restricted access; do not commit names, contacts, signatures or private addresses.

Frame products/shelves, not people. Do not intentionally capture faces, phone
numbers, receipts, payment details, private documents or sensitive locations.
Review each photo before adding it. If accidental private content appears, exclude
the photo or irreversibly redact it locally **before annotation and freeze**; check
the exported pixels and remove identifying EXIF/GPS metadata. If redaction hides a
target or makes counts uncertain, exclude/recollect rather than guess. Privacy
review flags are human attestations, not an automated PII detector.

Collect genuinely new photos with field provenance. Do not use HoloSelecta images,
training/validation/test photos, crops, augmentations, public dataset substitutes,
or generated images. Target at least **30 images and 5 independent scene/store
groups**. Fewer are permitted and prominently reported as a small pilot. Never
duplicate images to reach a quota. Include difficult and empty-target scenes based
on a capture plan made before predictions, not selectively chosen model successes.

Use opaque IDs (`scene_01`, `field_001`, `annotator_a`), not shop/customer names.
Same store, machine, shelf configuration, return visit, capture sequence or other
correlated group stays together. Use conservative larger groups when uncertain;
do not count several angles as independent stores. Review provenance/grouping
manually before freezing. Exact file and decoded-pixel hashes exclude known
HoloSelecta copies. They cannot establish that a resized/cropped/recompressed photo
is independent: the collector's provenance review remains essential.

dHash distance ≤ 8 flags near-duplicate candidates. Candidates within a scene are
recorded; cross-group candidates block freeze for review. dHash is a heuristic,
not proof. For a false-positive grouping warning, conservatively group/exclude the
candidate rather than quietly bypassing this frozen v1 rule. Do not modify the
rule after observing performance. Repeated views can remain within a group but
are correlated; image count does not equal independent sample count.

## Storage and setup

The default ignored root is `data/field_v07/cohort_001/`:

```text
collection.json
ground_truth.json
images/<opaque filename>.jpg (or .png / .jpeg)
frozen.json                  # created after real data/labels are ready
```

No dependencies were added. Use the existing environment/checkpoint. An empty
starter has already been created locally; on a fresh checkout run:

```powershell
.\.venv\Scripts\python.exe -m src.field_cli init
```

Existing directories/files are not overwritten. Add reviewed photos directly in
`images/`. Same input constraints as the API: valid JPEG/PNG, at most 20 MiB and
25 million pixels. A too-large capture should be recollected with suitable camera
settings; document any necessary pre-freeze preparation without changing model
preprocessing. No secrets or identifying metadata belong in these JSON records.

Within this repository, input/label/freeze paths must stay under ignored
`data/field_v07/` and output paths under ignored `outputs/field_v07/`. Paths outside
the repository are allowed for private local storage, but keep them out of other
Git repositories. Do not upload photos or generated visual reports to GitHub.

## Human counts before predictions

Count visibly identifiable **instances**, not inferred depth/hidden stock. Count a
partially visible package only if enough identifying packaging remains and it can
be distinguished as a separate unit. Exclude ambiguous packages; record uncertainty
in the local annotation revision's reason. Do not guess a class merely from shelf
position, brand colors or model output. There is no total-store stock claim.

Use the existing source-class identities in `configs/class_map.json`:

| Key | ID | Inclusion guidance |
| --- | ---: | --- |
| red_bull | 0 | Regular Red Bull source class; do not count light/sugar-free as regular. Source labels mix sizes; no new size classifier. |
| knoppers | 1 | Knoppers Riegel source product; not all generic Knoppers-branded packages. |
| valser_classic | 2 | Valser Classic source product; distinguish Still. |
| valser_still | 3 | Valser Still source product; distinguish Classic. |
| capri_sun_multivitamin | 4 | Multivitamin source product; do not include arbitrary Capri-Sun flavors. |

Review the source labels/product identifiers in the class map before collection;
these are not verified catalog SKUs or generic brand categories. If those products
are absent locally, report that coverage gap. Do not relabel an Indian substitute
as one of these five products to obtain a field result.

An annotator should count without seeing StoreRoom predictions. Ideally have a
second human adjudicate ambiguity while still blinded. Set `before_predictions`
truthfully. The evaluator reports how many records have any post-prediction
revision; those are not presented as fully independent blind ground truth.

## Input example (schema only, not real collected evidence)

After collecting a real image with permission, populate `collection.json` like:

```json
{
  "cohort_id": "cohort_001",
  "purpose": "independent_field_validation",
  "scenes": [{
    "scene_id": "scene_01",
    "permission_obtained": true,
    "independent_from_holoselecta": true,
    "correlated_captures_grouped": true
  }],
  "images": [{
    "image_id": "field_001",
    "path": "images/field_001.jpg",
    "scene_id": "scene_01",
    "captured_on": "2026-09-19",
    "privacy_reviewed": true,
    "original_field_capture": true,
    "tags": ["crowded", "small_products"]
  }]
}
```

Use the actual capture date/IDs. `original_field_capture` attests real independent
field origin, allowing the documented privacy sanitization above. Optional tags
are `crowded`, `small_products`, `partial_occlusion`, `visually_similar_products`.
Annotate conditions before model output; they are not proven causes of errors.

`ground_truth.json` is an array with exactly one record per image:

```json
[{
  "image_id": "field_001",
  "revisions": [{
    "revision": 1,
    "counts": {
      "red_bull": 4,
      "knoppers": 2,
      "valser_classic": 1,
      "valser_still": 0,
      "capri_sun_multivitamin": 3
    },
    "annotator_id": "annotator_a",
    "recorded_at": "2026-09-19T10:00:00Z",
    "before_predictions": true,
    "reason": "Initial blind count; only identifiable separate packages counted",
    "previous_revision_sha256": null
  }]
```

These example counts are illustrative. Enter your actual human counts. All five
keys are mandatory, including zeros; counts must be nonnegative integers ≤100000.
Unknown fields, duplicate IDs/JSON keys, missing/extra labels and ambiguous paths
are rejected. IDs use letters, numbers, underscore or hyphen (maximum 64 characters).

## Corrections preserve history

Do not edit a previous revision in place. Preserve the old cohort directory,
frozen JSON/hash and result directory. Make a separately named local revision of
the cohort; it is **the same scenes with corrected labels, not new independent data**.
Append a revision to the relevant image's `revisions` array with incremented
`revision`, full five counts, a new timezone-aware timestamp, annotator ID, reason,
truthful `before_predictions`, and the hash of the previous normalized revision.

Compute that reference in Python using the workflow's exact canonical form:

```python
from src.field_cohort import Revision, object_hash
previous = Revision.model_validate(previous_revision_dict).model_dump(mode="json")
previous_revision_sha256 = object_hash(previous)
```

The consecutive revision/hash chain is validated. Editing earlier counts breaks
the chain. The frozen manifest embeds every revision and the source-file hashes;
changing a source file invalidates that freeze. Create a new manifest filename
and retain both hashes/results, explicitly labelling any post-prediction correction.
Local checksums are an audit aid, not a tamper-proof signature against someone
with access to rewrite all records.

## Freeze and evaluate

After human review:

```powershell
.\.venv\Scripts\python.exe -m src.field_cli validate
.\.venv\Scripts\python.exe -m src.field_cli freeze --manifest data/field_v07/cohort_001/frozen.json
```

Expected: validation count, then `Frozen cohort SHA-256: <64 hex characters>`.
Retain the printed hash in the collection log. Freeze verifies all images/labels,
group membership, file/pixel duplicates, known HoloSelecta hashes and the frozen
model/protocol. It embeds source hashes, complete labels, image hashes/dimensions,
safe metadata, scene attestations, near-duplicate candidates and protocol hash.

```powershell
.\.venv\Scripts\python.exe -m src.field_cli evaluate --manifest data/field_v07/cohort_001/frozen.json --cohort-sha256 <printed-hash> --output outputs/field_v07/cohort_001_run_001
```

Add `--root data/field_v07/<other-cohort>` to each command for another collection.
`<printed-hash>` is a placeholder. Do not run evaluation until real images and
blind labels exist. Empty cohorts fail; no synthetic fallback is generated.

Only the unchanged `Detector` can be chosen by the CLI. No threshold, resolution,
NMS, model or training flags exist. Each frozen image goes through one prediction;
selected visuals render saved detections without a second inference call. Image
bytes are rechecked before inference, and all inputs/membership are checked again
after predictions and rendering. Changes abort. Existing output directories are
never overwritten. `INCOMPLETE` marks failed partial runs; only `COMPLETE` marks
a finished run. Correct a failure, preserve its record, and use a new output path.

Outputs: `metrics.json`, `predictions.json`, copied `frozen_cohort.json`, `REPORT.md`,
and a small `visuals/` selection. Generated JPEGs have no copied EXIF; their content
still depends on the required pre-freeze privacy review. Keep everything local.

## Frozen implementation and reproducibility

`configs/field_validation_v07.json` records the protocol version/date, model ID,
checkpoint SHA-256, complete current inference profile and hash, source class map,
implementation/reference file hashes and software versions. The developer's
one-time `freeze-protocol` bootstrap refuses to overwrite an existing manifest;
it is not part of collection/evaluation and must not be used to bypass drift.

Profile: AUGMENTATION_001, CPU, 320px, NMS IoU 0.50, Red Bull 0.15/others 0.25,
original best class gated before NMS, same decoding/preprocessing/counting code.
Verification fails on checkpoint/config/source/runtime drift. Restore the recorded
environment instead of silently accepting a different configuration. Missing
dependencies/artifacts are errors, not invitations to download/train substitutes.

Outputs record model/config/protocol/cohort hashes, runtime versions/platform,
evaluation timestamp and static test-definition count. That count is not a claim
that evaluation ran tests. Run the complete suite separately:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Iteration order, count aggregation and representative selection/tie-breaking are
deterministic. Tests check identical metric results using a deterministic fake
detector; they do not prove real-model cross-hardware bitwise equivalence. The
unchanged CPU backend is retained; timestamps differ between runs by design.

## Metrics and limits of error analysis

Overall MAE = sum of absolute image/class count errors divided by `images × 5`,
using the existing `src.counting.counting_metrics`. Exact five-class accuracy is
the fraction of images where **all five** counts match. Over/under-count totals
sum positive/negative class errors separately, so wrong classes cannot cancel.
Per class: truth/predicted totals, summed absolute error, MAE and exact image
accuracy. Per scene: the same summaries; small or unsupported classes stay visible.

Automatic categories: under-count, over-count, complete class miss, prediction
for a class with zero human count. Simultaneous class over/under-counts produce
**possible confusion, needs visual review**, not established object-level confusion.
Errors on crowding/small/occluded/similar-product tagged photos are condition
associations, not causal diagnoses. No box truth means no precision/recall/mAP or
verified duplicate-detection labels. Correct counts can conceal compensating
false positives/misses. Zero target support cannot demonstrate product recall.

Representative examples are selected deterministically before manual discussion:
up to three exact successes (higher item counts first), largest under-counts,
largest over-counts, complete misses and potential confusion cases. Missing
categories show no qualifying examples; the workflow does not fabricate failures.

The HoloSelecta validation cohort and the field cohort are different populations
and should not be treated as directly equivalent benchmarks. Never combine their
scores. Meeting 30/5 is an initial coverage target, not a statistical proof of
generalization or production readiness. Interpret group diversity, class support,
blinding and collection bias alongside headline values.

Next milestone: collect and independently annotate the first real field cohort,
then execute this frozen protocol. No field results are available yet.
