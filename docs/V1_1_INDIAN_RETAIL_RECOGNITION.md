# Indian retail recognition foundation — proposed design

Status: **design only, 2026-09-25**. The [dataset audit](../reports/V1_1_DATASET_AUDIT.md) did not pass the training gate. No new detector, catalog records, migrations or API behavior are implemented. The running five-class application remains the baseline.

## Problem and boundaries

Estimate visible product instances in real Indian shop shelves, identify only what evidence supports, and send predictions for shopkeeper review. Visible counts cannot establish hidden stock. Recognition must not silently invent pack sizes, availability, ingredients or SKU identity.

## Identity and taxonomy

Use immutable internal IDs for brand, product family, variant and sellable pack/SKU. Display names and aliases can change without changing identity. Store GTINs as verified strings, preserving leading zeros; GTINs are external identifiers, not model class indices. Separate packaging appearance/version from product identity.

For example, a family can have several variants and each variant several pack sizes. Unknown variant/size stays null. Recognizing a family does not identify a sellable pack. A reviewer must resolve a SKU before new SKU inventory/order publication; no automatic conversion of a family count into a size-specific count.

The current `src/catalog.py` already has stable `product_id` values, but also restricts `class_id` to 0–4; `src/review.py` validates the same fixed mapping. Preserve those identities and historical evidence. A later explicit migration/adapter is required, rather than appending new labels to the existing configuration.

## Architecture choice

| Approach | Benefits | Costs and risks | Decision |
|---|---|---|---|
| A: many-class detector | Simple inference, direct labels | New identities generally require retraining; closed-set mistakes and class imbalance | Future controlled comparator on identical data |
| B: generic detector + crop identifier | Decouples location from identity; gallery entries can grow independently | Missed/poor crops limit recognition; retrieval needs hard negatives and rejection calibration | Preferred foundation, pending evidence |
| C: visual + OCR/barcode | Can resolve text/pack/identity ambiguity | Blur, reflections, occlusion, invisible barcode, regional text; extra latency and conflicts | Add only for a demonstrated failure pattern |

A gallery update is not a guarantee of good recognition: new lookalikes may require encoder improvement and rejection recalibration on development data. Evaluate CPU latency as well as accuracy. No LLM, new infrastructure service, or detector family is selected by this document.

Proposed reusable boundaries:

- `ProductCatalog`: immutable IDs, hierarchical metadata, aliases, source evidence and versioned references.
- `ProductDetector`: image to instance boxes and detector scores; no inventory writes.
- `ProductIdentifier`: crop plus optional evidence to candidates or rejection.
- `RecognitionResult`: stable interface with instance identity, product identity level, uncertainty and provenance.
- `UnknownProduct`: reviewable unresolved instance; never an arbitrary known-class assignment.

Reuse licensed maintained components after data approval; do not write a converter/trainer when a verified library already supports the actual source format. The current five-class detector is not a generic product detector just because its boxes can be cropped.

## Pipeline and proposed result contract

Detect visible instances, retain pixel-coordinate boxes, crop from the original image, retrieve against training-only references, apply a frozen rejection rule, then request human review. Count instances, not gallery matches. Overlap alone cannot justify merging adjacent identical packages.

Illustrative schema only; it is not an implemented API or measured prediction:

```json
{
  "schema_version": "recognition-v2-proposed",
  "instance_id": "instance-0001",
  "product_id": null,
  "variant_id": null,
  "sku_id": null,
  "identity_level": "unknown",
  "status": "UNKNOWN",
  "confidence": null,
  "detector_score": null,
  "identity_score": null,
  "bbox": [12, 24, 96, 180],
  "bbox_format": "xyxy_pixels",
  "source": "vision",
  "review_required": true,
  "model_version": null,
  "gallery_version": null
}
```

Production validation would require finite bounded boxes within image dimensions, unique instance IDs, valid catalog references and actual model/gallery versions. Similarity scores must not be mislabeled as calibrated probabilities. Keep detector score separate from identity confidence. Preserve raw prediction and reviewer correction as distinct evidence.

`UNKNOWN` means insufficient identity evidence. `UNSUPPORTED` means an identity is established but outside the supported catalog/cohort. Low similarity alone establishes only UNKNOWN. Conflicting barcode/visual evidence is review-required, not an automatic override. Rejection thresholds and candidate margins must be set on development data containing real unknowns, frozen before independent evaluation.

## Barcode and OCR

A visible valid barcode with a verified catalog match may resolve a pack; checksum validity alone does not verify the catalog entry. OCR can narrow candidates by brand/variant/size text. Tiny text, regional spellings, curved packs, occlusion and reflections prevent either signal being universal. Unseen barcodes and contradictory text stay unresolved. No ingredient or medical inference from packaging appearance.

Use the installed barcode library as a future bounded experiment; do not alter its existing scene-sticker grouping workflow. OCR adds value only if reviewed errors show readable discriminating text. Model/weight/data licenses need separate verification even when library code is reusable.

## Data and evaluation protocol

Acquire only sources cleared by the audit. Keep a versioned image manifest with SHA-256, source/version, source image ID, license/rights evidence, store, scene, capture sequence, duplicate component, dimensions, annotation hash, product/variant/SKU labels, ambiguity flags and split. A separate reference-gallery manifest records the same provenance. No unresolved group enters independent evaluation.

Join correlated groups before splitting; keep stores and sequences together even across source archives. Verify component disjointness, class support and gallery membership. Freeze both manifest hashes and evaluation rules before tuning. Isolated product references supplement training; the evaluation cohort must contain real shelves, crowded scenes, similar variants, small products and unknown objects. Do not use generated shelves as benchmark data.

| Layer | Required measurement |
|---|---|
| Localization | Precision/recall at frozen operating point; mAP50/mAP50–95 from score sweep, with IoU/matching rules recorded |
| Identification | Top-1/top-5 on verified known identities; category/variant/size breakdown; distinguish GT-crop from detected-crop results |
| Unknown handling | Rejection rate, known-item false rejection, unknown false acceptance, accepted-prediction accuracy/coverage |
| End-to-end counts | Per-product MAE; macro mean across image/product pairs; exact full-cohort count-vector accuracy; over/under totals |
| Robustness | Every metric by store/group and category; crowded/small/occluded strata; sample counts and group-level uncertainty |
| Operations | CPU latency, memory, unresolved instances and human correction burden |

Use one-to-one box matching and fixed rules so multiple predictions cannot claim the same target. Unknown detections do not disappear from localization/false-positive accounting; report identity/count omissions separately. Include zero-target images and an always-zero count baseline. Top-5 is conditional on at least five eligible identities. Report detection misses as end-to-end failures, not only accuracy among successful crops.

Both future systems use identical independent images. The historical model can be compared on shared identities, explicitly reporting its coverage; it cannot fairly be scored as a 50-product identifier. Generic localization comparisons must disclose that the historical detector was trained for five identities. Leave the protected HoloSelecta test set untouched. New independent data is not a reusable tuning set; later configuration changes require a fresh frozen evaluation cohort.

## Human review and compatibility

Introduce any future pipeline alongside the old one with explicit model/schema versions. A legacy adapter maps frozen class IDs to existing product IDs without rewriting old evidence. A new review path must permit unknown instances, family-level corrections and explicit SKU resolution. Confirmed observations alone may update inventory. Keep order reservations, alternatives, scan history and the V0.7 protocol unchanged; validate migration behavior in a separate implementation phase.

Before rollout, test stable IDs, model mapping, unknown/conflict outcomes, rejection boundaries, schema validation, repeated neighboring products, manifest hashes, rights metadata, group leakage, gallery leakage, legacy inference and all existing review/order tests. No new behavior exists now, so no implementation tests or successful metrics are claimed.

## Expansion and current limitation

Start with the smaller cohort justified by verified data. Add a product through identity verification, licensed references, similarity/unknown checks and development evaluation; version the gallery and retain rollback. Expand to 50, 500 and beyond only when independent store coverage and latency justify it. A single catalog photo or a longer label list does not establish support.

The immediate dependency is an authorized, inspectable Indian shelf collection with reliable identities and group metadata. Until that exists, the ten candidate names in the audit are research leads only. V1.1 remains incomplete, with the original five supported classes unchanged.

## Audit validation

The existing suite can use isolated storage while the demo app is running. From the repository root in a fresh PowerShell session:

```powershell
$env:STOREROOM_DB_PATH = 'outputs/v11_test_runtime/storeroom.db'
$env:SCAN_STORAGE_DIR = 'outputs/v11_test_runtime/scans'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

These variables apply to that shell and its child processes; use a separate shell for the live app. The initial run against default storage encountered the running app's lock in one startup test. This is an environment collision, not evidence of a recognition regression. The audit verification record documents the isolated rerun and byte/hash preservation checks. No model evaluation or training command is part of these checks.
