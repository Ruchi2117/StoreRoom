# V0.7 — independent field validation results and readiness

## 1. Executive summary

**Workflow implemented and tested; real-world evaluation pending data collection.**
There are **0 available independent field images and 0 field scene groups**. No
cohort was fabricated, substituted from HoloSelecta or evaluated with the real model.
No field accuracy/generalization claim is justified. The local starter contains
empty collection/ground-truth arrays, not example observations.

The full suite passed **121 tests**, including 18 new field-workflow tests. Synthetic
temporary test images and a fake detector verify software behavior only; they are
not field evidence. No previous tests or fixtures were changed.

## 2. Objective

Measure how the current frozen provisional system counts visibly identifiable
instances of its five source product classes on genuinely new shelf scenes. This
is evaluation only: no retraining, fine-tuning, augmentation, threshold adjustment,
resolution change, NMS change or model selection based on field results.

## 3. Frozen model and configuration

| Setting | Frozen value |
| --- | --- |
| Model | AUGMENTATION_001 / storeroom-holoselecta-five-v0.1-augmentation-001 |
| Checkpoint | runs/augmentation_001/weights/best.pt |
| Checkpoint SHA-256 | 099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4 |
| Device / resolution | CPU / 320px |
| Class-aware NMS IoU | 0.50 |
| Red Bull confidence | 0.15 |
| Other four class confidences | 0.25 |
| Preprocessing/inference | Unchanged src.inference.Detector and original pre-NMS best-class gate |
| Protocol version | field-counts-v1 |
| Protocol created | 2026-09-19T13:47:08.998138+00:00 |
| Inference config SHA-256 | 718e69212b0bba986ee0b8ddf60eb347600f339916ac26662b4e7b6325c24ad9 |
| Field protocol SHA-256 | 4d59789dbc368ac7a9b73f58556108c567a8a87eedbbd40b2bf685029953083d |

The new [frozen protocol manifest](../configs/field_validation_v07.json) records
the existing complete profile, class mapping, implementation/reference hashes and
runtime versions. Existing `configs/inference_v01.json`, class map and checkpoints
are unchanged. Runtime/source/config drift stops evaluation rather than silently
changing the experiment. There are no tuning flags in the field CLI.

## 4. Field cohort composition

| Item | Current status |
| --- | --- |
| Available consented independent images | 0 |
| Available independent scene groups | 0 |
| Target initial coverage | At least 30 images / 5 groups |
| Ground-truth records | None |
| Frozen real cohort / cohort hash | Not created; pending collection and annotation |
| Real field predictions / evaluation timestamp | None; evaluation not run |
| Class support and scene diversity | Not yet assessable |

The inspected local data contains HoloSelecta exports/raw data and prior product
smoke artifacts. None qualifies as an independently collected cohort. A new ignored
`data/field_v07/cohort_001/` starter contains no photos. Existing validation/test
images, crops and augmentations cannot fill this gap.

## 5. Collection and privacy protocol

The [collection guide](../docs/V0_7_FIELD_VALIDATION.md) requires permission from the
responsible site owner, a stated counting-evaluation purpose, shelf/product framing
and pre-freeze privacy review. Do not collect people, contacts, receipts, payment
details, private documents or sensitive locations. Exclude accidental personal data
or redact irreversibly before annotation/freeze, removing identifying metadata.
Recollect if privacy processing makes target counts ambiguous.

Use opaque image/scene/annotator IDs. Keep necessary consent details separately,
privately; the cohort stores only permission/provenance/grouping attestations and
safe metadata. Photos, labels, consent records and generated visual reports are
local/ignored. Generated representative images do not copy EXIF metadata.

## 6. Ground-truth protocol

Human counts should be established before viewing predictions, including explicit
zeros for all five classes. Count only distinct visibly identifiable packages.
Partial packages count only when identity and individual-instance separation are
clear; never infer hidden stock or guess ambiguous variants. Class inclusion follows
the existing source map: regular Red Bull, Knoppers Riegel, Valser Classic, Valser
Still and Capri-Sun Multivitamin. Generic brand matches are insufficient.

Per-image annotations have append-only revision histories with timestamps, opaque
annotator IDs, reasons, a `before_predictions` flag and previous-revision hashes.
The freeze embeds full histories and input-file hashes. Corrections require retaining
the original freeze/result and creating a separately labelled cohort revision.
Post-prediction revisions are counted and disclosed, not passed off as blinded truth.

## 7. Evaluation methodology and implementation

`src/field_cohort.py` implements strict schemas, safe local paths, protocol checks,
image validation/checksums, exact/pixel duplicate rejection, HoloSelecta hash
exclusion, group validation, near-duplicate checks and cohort freeze enforcement.
An externally retained cohort hash is required by evaluation. Image membership,
ground truth and hashes are revalidated before and after predictions/rendering.

`src/field_evaluation.py` calls the unchanged detector once per image, saves the
original predictions, renders selected detections without rerunning the model,
and produces local JSON/Markdown results. Existing output directories are never
overwritten. Aborted runs retain an INCOMPLETE marker instead of completed results.

`src/field_metrics.py` reuses the existing counting metric implementation. MAE
averages absolute errors over image × class cells. Exact accuracy requires all
five counts to match for an image. Over/under-counts sum class errors separately;
they do not cancel across classes. Per-class and per-scene tables preserve context.

`src/field_cli.py` supplies init/validate/freeze/evaluate commands. No API/frontend
changes, database changes, dependencies or model/configuration changes were needed.
README and `.gitignore` document the milestone and private local directories.

## 8. Overall results

| Metric | Field result |
| --- | --- |
| Ground-truth items | Pending labels; not reported as zero observed targets |
| Predicted items | Not evaluated |
| Counting MAE | Not evaluated |
| Exact five-class count accuracy | Not evaluated |
| Total over-count / under-count | Not evaluated |

No detection precision, recall or mAP is generated without bounding-box truth.

## 9. Per-class results

| Class | Truth total | Predicted total | Absolute error | MAE | Exact image accuracy |
| --- | --- | --- | --- | --- | --- |
| Red Bull | Pending | Pending | Pending | Pending | Pending |
| Knoppers | Pending | Pending | Pending | Pending | Pending |
| Valser Classic | Pending | Pending | Pending | Pending | Pending |
| Valser Still | Pending | Pending | Pending | Pending | Pending |
| Capri-Sun Multivitamin | Pending | Pending | Pending | Pending | Pending |

No product has established field support. The unresolved Valser identity/over-count
weaknesses from earlier validation remain unresolved; this milestone provides no
new evidence that they improved or generalized.

## 10. Per-scene results

Pending real scene groups. The workflow emits an image count, target/prediction
totals, MAE, exact accuracy, over/under-counts and per-class summary for each scene.
Same machine/store/shelf/correlated sequence stays in one group. Scene independence
is collector-attested; no automatic hash algorithm proves it.

## 11. Error analysis

No real field errors or representative photos exist yet. Implemented automatic
categories are over-count, under-count, completely missed class and prediction of
a class with zero ground truth. Simultaneous over/under-counts are **possible
confusion candidates requiring visual review**, not proven class confusion.
Preannotated crowding/small-product/occlusion/visual-similarity tags identify
conditions associated with errors, not their causes.

The workflow selects up to three examples per category: exact successes with more
items, largest under-counts, largest over-counts, complete misses and potential
confusion. Ties use image ID. Missing categories remain empty. Rendered boxes are
saved predictions, not ground-truth matches. Count labels cannot verify duplicate
detections, object-level false positives, or why a package was missed.

## 12. Comparison with HoloSelecta

Historical [AUGMENTATION_001 validation](AUGMENTATION_001_RESULTS.md) reports counting
MAE **0.423077** and exact counts **11/26** on the existing 26-image validation split.
These existing values were read, not recalculated. Both Valser classes previously
regressed on counting MAE. There is no field score to compare yet.

**The HoloSelecta validation cohort and the field cohort are different populations
and should not be treated as directly equivalent benchmarks.** Do not pool their
scores or infer production readiness from a future single-cohort result.

## 13. Limitations

The real cohort is absent. Hash screening detects known exact/file/pixel copies,
not all transformed/cropped derivatives; independence and consent need trustworthy
collection review. dHash can produce false-positive/negative similarity warnings.
Multiple views within a group remain correlated. Source classes may be unavailable
in the intended deployment geography; zero support cannot measure that class's recall.
Even 30 images / 5 groups is an initial coverage target, not a statistical guarantee.

The model remains provisional; counts represent visible items only. Hidden stock,
catalog SKUs, general retail recognition and production readiness remain unsupported.
Privacy flags are not automated PII detection. Local hashes are not signatures
against an operator who rewrites every file. GPU/cross-hardware bitwise model
repeatability is not claimed.

## 14. Reproducibility and verification

See [exact input schemas and commands](../docs/V0_7_FIELD_VALIDATION.md): collect
permitted new photos → independently count → validate → freeze → evaluate using
the printed cohort hash → inspect local results. Do not run evaluation on the
empty starter. Missing data/runtime artifacts cause an error, not a fallback.

Frozen runtime: Python **3.14.4**, Ultralytics **8.4.154**, PyTorch **2.14.0+cpu**,
OpenCV **5.0.0.93**, NumPy **2.5.2**, Pillow **12.3.0**, Pydantic **2.13.5**.
Future outputs record model/config/cohort/protocol hashes, runtime/platform,
evaluation timestamp and static test count. Actual suite execution is separate.

**121 tests passed in 123.971 seconds: 103 previous tests unchanged + 18 new.**
See [full suite output](v0_7_tests.log). `pip check` passed. New tests cover schemas,
checksums, duplicates, near-duplicate grouping, missing files/labels, unsafe/malformed
input, privacy/provenance gates, HoloSelecta hash rejection, membership/label/pixel
changes after freeze, revision histories, exact overall/per-class/per-scene metrics,
deterministic ordering, repeated fake-detector evaluation, metadata-free visuals and
mid-run mutation failure. Fake-detector tests do not load the real model or use
HoloSelecta test images.

[Preservation verification](v0_7_integrity.json) checks all 921 protected artifacts,
frozen dataset hashes, and existing tracked files against `96ee105` (apart from
README/.gitignore additions). Prior sources, tests/fixtures, checkpoints, reports,
metrics and manifests remain byte-identical. No training, real field inference or
protected test-set evaluation occurred. No field photos/private data are committed.

## 15. Conclusion

The software workflow is ready for collection, but **zero images and zero scene
groups cannot support any interpretation of real-world generalization**. V0.7
establishes the collection/freeze/evaluation machinery, not a measured field baseline.
Do not claim field performance, production readiness or improved Valser behavior.

## 16. Recommended next milestone

**Collect and independently annotate the first consented field cohort, then run
this frozen protocol.** Aim for 30 images and 5 independent groups with honest
class coverage; report smaller/limited coverage when necessary. Do not tune the
model using those results during this milestone.

One meaningful implementation commit is created after validation; the final task
response records its hash, GitHub push and clean working-tree status.
