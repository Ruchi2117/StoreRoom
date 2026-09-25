# V1.1 Indian retail dataset audit

Audit date: 2026-09-25. Status: **NO-GO for training or recognition implementation**.

This is a source/metadata audit, not an annotation-quality certification. No candidate archive was imported, no model was run, and no new product is supported. Public evidence does not yet establish a commercially usable, identity-resolved, store-disjoint Indian shelf cohort. This follows the brief's stop condition; V1.1 is not complete.

## 1. Candidate datasets

Search covered publisher repositories/papers, Kaggle, Hugging Face, and Roboflow Universe. Counts below are publisher claims, not locally verified usable counts. A missing value means unknown, not zero. Hosting a dataset or offering a YOLO export does not establish its provenance.

| Source | Published size / identities | Relevance and current disposition |
|---|---|---|
| [Grocer-Help, Zenodo](https://zenodo.org/records/10464054) | 7,371 images; class count not established from this record | Strong Indian lead; restricted access, pending inspection |
| [Grocer-Help, 2026 paper](https://www.nature.com/articles/s41598-026-42266-9) | 13,771 images, 349 brand-centric classes, 166,306 boxes, eight stores | Newer collection, not interchangeable with the older archive |
| [AgentSK47 Indian Grocery](https://universe.roboflow.com/agentsk47/indian-grocery-object-detection-mfsnx) | 403 images, ten labels, one version | Small candidate inspection cohort; not approved training data |
| [SKU110K](https://github.com/eg4000/SKU110K_CVPR19) | 11,743 images, generic product boxes | Dense detection reference; commercial-use restriction |
| [RPC](https://rpc-dataset.github.io/) | 83,739 images, 200 classes | Exemplar/checkout task; commercial-use restriction |
| [Humans in the Loop supermarket shelves](https://humansintheloop.org/resources/datasets/supermarket-shelves-dataset/) | 45 images, 11,743 boxes, product/price labels | Possible generic localization QA; no product identities |
| [BigBasket list, Kaggle](https://www.kaggle.com/datasets/surajjha101/bigbasket-entire-product-list-28k-datapoints) | Advertised approximately 28K records | Catalog lead, not a verified shelf detection dataset; page body inaccessible in this audit |
| [Open Food Facts, publisher HF card](https://huggingface.co/datasets/openfoodfacts/product-database) | Millions of catalog rows; changing snapshot | Potential barcode/catalog enrichment, not shelf ground truth |

## 2. Licenses and provenance

| Source | Observed terms | Decision / obligations |
|---|---|---|
| Grocer-Help Zenodo | API metadata: `license.id=cc-by-4.0`, `access_right=restricted` | Attribution, license link, indicate changes; request access and clarify online-image rights before ingestion. License declaration is not unrestricted download access. |
| Grocer-Help newer collection | Full release subject to institutional approval | Do not extend older archive terms to undistributed data. Obtain version-specific permission. |
| AgentSK47 | Uploader declares CC BY 4.0 | Attribution and change notice; image ownership/source history still unverified. |
| SKU110K | Authors restrict dataset to academic/non-commercial use | Exclude from startup training unless separate permission is obtained. |
| RPC | CC BY-NC-SA 4.0 | Exclude from startup training; noncommercial/share-alike terms apply. |
| Humans in the Loop | CC0 1.0 | Publisher permits commercial reuse; retain provenance even though attribution is not required by CC0. |
| BigBasket | Not verified from accessible primary metadata | Not approved; notebook licenses do not license underlying data. |
| Open Food Facts | Database ODbL; individual contents DbCL; images CC BY-SA, with additional rights caveat | Keep separate provenance and applicable attribution/share-alike obligations; do not treat repository software license as image license. |

Zenodo metadata can be checked without downloading images:

```powershell
$record = Invoke-RestMethod 'https://zenodo.org/api/records/10464054'
$record.metadata | ConvertTo-Json -Depth 8
```

Source snapshots/rights must be recorded again at acquisition. No outside contact, account submission, scraping, or raw-data redistribution occurred. The paper's second subset DOI, [IEEE DataPort](https://doi.org/10.21227/d4na-7e68), could not be fetched; access, contents and terms remain unverified.

Maintenance/provenance assessment: Grocer-Help has identifiable authors and a dated repository record but release reconciliation is unresolved. AgentSK47 has a single published version and no verified capture ledger. SKU110K and RPC have author-maintained project pages, which do not guarantee ongoing annotation correction. The CC0 set has an identified annotation organization but group metadata is unverified. Open Food Facts is continuously updated, so a pinned snapshot is mandatory. Kaggle source history and correction policy were not verified. None is assumed to provide a maintenance guarantee.

## 3. Indian product coverage

Grocer-Help is the most directly relevant collection, but brand-level labels do not establish SKU identity. AgentSK47 supplies named Indian-market candidates below. Neither has verified pack-size coverage here. SKU110K, RPC and the small CC0 shelf set do not establish an Indian identity cohort. Catalog entries cannot substitute for Indian shelf images.

## 4. Annotation formats and quality

Grocer-Help describes bounding-box annotation through Roboflow; its actual archive schema remains uninspected. AgentSK47's annotation-format description is an unfilled placeholder. SKU110K documents CSV box annotations; RPC provides product annotations, and the CC0 set product/price boxes, with export schemas uninspected here. No local conversion was performed. Open Food Facts provides tabular/text records rather than shelf boxes. No source has passed StoreRoom's box or identity QA.

Before acceptance, enumerate actual files and label dictionaries; check missing labels, corrupt images, bounds, zero-area boxes, duplicate annotations and inconsistent identities. Manually review crowded, small, occluded and rare-class examples. Document whether boxes cover visible extent or estimated full package extent. Never count a cropped fragment twice or infer hidden stock behind front-facing units.

## 5. Size, balance and release reconciliation

The older Zenodo record lists 2,460 close, 2,604 long and 2,307 online images, split 6,682/689. The newer paper includes 2,307 online images but reports a larger collection; its overall split and distance-based breakdown are inconsistent. Do not combine these releases or reuse their counts as verified local evidence.

For every candidate, usable images per identity, boxes per identity, independent groups per identity, minority-class coverage and rejected annotation totals are **unknown** until archive inspection. Large totals do not resolve those gaps. Approved Indian training products: **0**; proposed inspection candidates: **10**.

## 6. Scene diversity

The newer Grocer-Help paper describes close/distant views across eight stores. AgentSK47 claims lighting/viewpoint variation without verified store counts. The CC0 set is small and geographically unspecified for this purpose. RPC's checkout scenes do not represent shelf occlusion and repeated neighboring packages. Online product photos may help a training-only reference gallery but cannot establish shelf performance.

## 7. Leakage risks

Grocer-Help's store table puts the same stores into multiple splits, so its published split fails our store-disjoint requirement. This does not prove exact-image duplication; it does require a new grouping audit. For other candidates, absent capture metadata leaves store/sequence overlap unresolved.

For any acquired data, merge connected groups linked by store, scene, capture sequence, exact hash, or manually confirmed near-duplicate relationship. Split entire components. Repeated catalog photos also remain together. Unresolved provenance stays quarantined. Perceptual hashes suggest review candidates; they do not prove independence. Freeze evaluation manifests before training, and keep gallery exemplars out of held-out capture groups.

## 8. Recommended sources

First pursue a versioned Grocer-Help access/provenance package: exact release, rights for all subsets, identity dictionary, box schema and image-to-store/scene mapping. Inspect the ten-label Roboflow source as a smaller alternative only after source ownership and group metadata can be established. Consider the CC0 shelf set for generic localization QA. Open Food Facts is a later metadata aid, not the missing benchmark.

These are conditional recommendations, not approvals to train.

## 9. Rejected or deferred uses

- SKU110K/RPC: do not import into a commercial model under the observed noncommercial terms.
- Kaggle catalog rows and HF catalog records: do not present as box-annotated shelf data.
- Existing HoloSelecta: retain frozen historical baseline; do not expand its taxonomy or reuse its protected test set.
- Unattributed mirrors, generated shelves and scraped commerce images: no benchmark admission without appropriate provenance and rights; synthetic images never supply this independent benchmark.
- Ready-made weights: no adoption based solely on a repository license. Weight provenance, training-data restrictions, Indian coverage and unknown-product behavior require separate review.

## 10. Proposed cohort: ten inspection candidates, none yet selected

Do not pad to 50–100. The following IDs are proposed opaque catalog keys, not inserted records or model labels. Display strings come from the linked AgentSK47 card. All rows share: source AgentSK47 above; declared license CC BY 4.0; usable images **unknown**; independent scenes **unknown**; annotation export **unverified**; pack size **unknown**. Brand/variant metadata remains **unknown pending label-to-package verification**. Categories are proposed broad catalog groupings.

| Proposed ID | Candidate display name | Proposed category | Why inspect / limitation |
|---|---|---|---|
| PROD_IN_0001 | Bournvita | Beverage | Food coverage; identity breadth unresolved |
| PROD_IN_0002 | Mysore Sandal Soap | Personal care | Box packaging; size unresolved |
| PROD_IN_0003 | Nescafe Classic Coffee | Beverage | Coffee example; packaging forms unresolved |
| PROD_IN_0004 | Nivea Body Lotion | Personal care | Bottle example; variant ambiguous |
| PROD_IN_0005 | Nivea Soft Moisturising Cream | Personal care | Similar-brand discrimination |
| PROD_IN_0006 | Parachute Coconut Oil | Personal care | Repeated bottle instances |
| PROD_IN_0007 | Patanjali Dant Kanti | Personal care | Tube/box ambiguity |
| PROD_IN_0008 | Society Tea Powder Plain | Beverage | Grocery coverage; identity verification needed |
| PROD_IN_0009 | Tresemme Hairfall Defense Conditioner | Personal care | Deliberate near-neighbor challenge |
| PROD_IN_0010 | Tresemme Hairfall Defense Shampoo | Personal care | Deliberate near-neighbor challenge |

Reasons are inspection priorities, not claims about observed model difficulty. This list lacks snacks/biscuits/household breadth and cannot represent the final Indian assortment. Promote a row only after obtaining actual per-product counts, identities and independent coverage; retain fewer products if necessary.

## 11. Proposed architecture and reusable tools

Prefer generic instance detection followed by crop retrieval against a versioned product gallery. Adding verified references can add identities without changing detector class outputs; this is a design hypothesis, not measured performance. Compare against a closed-set detector on the same future cohort. OCR/barcode can resolve specific ambiguities later. See [design](../docs/V1_1_INDIAN_RETAIL_RECOGNITION.md).

Reuse the existing detector/runtime/evaluator patterns where compatible; do not copy another training framework wholesale. [PaddleClas](https://github.com/PaddlePaddle/PaddleClas) offers recognition/retrieval work worth inspecting, and [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) is an OCR candidate. Neither was installed or selected. Existing `zxing-cpp` can be investigated for visible barcodes without altering the field protocol. Pin code and inspect exact weight/data licenses before adoption. [Ultralytics licensing](https://www.ultralytics.com/license) offers AGPL and enterprise paths; the current dependency is not automatically a permissive commercial license.

## 12. Remaining gaps and next action

The single next experiment should be a **data-only feasibility preflight** on an authorized Grocer-Help release, before any model comparison. Obtain its exact class dictionary, ownership/online-image permissions, group manifest and representative annotation sample. Then measure usable identities, boxes, independent groups and duplicates. No request to authors was sent in this task.

If that release cannot support the task, plan a consented ten-product capture pilot with participating shops. A planning target is eight stores (four training, two validation, two final evaluation), multiple visits and phones, close/distant crowded shelves, unknown products and similar variants. These are collection targets, not acquired data or a guarantee of statistical power. Record every store/scene/sequence; retain whole stores together. Acquire front/back identity references separately with verified GTIN/size where available. Double-review identity ambiguities and a stratified box sample. Expand stores or reduce products when cross-store support is insufficient; never split repeated views to manufacture support.

Training gate: documented rights and access; verified package identities; usable boxes; adequate per-product independent coverage; resolved duplicate groups; frozen manifests/gallery membership; preregistered evaluation. Until all pass, implementation and model results remain deferred. No `V1_1_RESULTS.md` is created.
