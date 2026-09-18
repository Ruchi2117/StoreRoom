# StoreRoom reuse-first audit

Audit date: 2026-09-16. Task: identify and count visible instances of five known products in a single shelf/display image.

Follow-up: the implemented data preflight is now documented in [reports/PREFLIGHT_REPORT.md](reports/PREFLIGHT_REPORT.md). It found missing image files, conflicting identifiers, mixed sizes, and repeat machine visits. The inspection-only statements below describe the original audit date; the later report contains actual downloaded-data findings. Training and Supervision conversion remain unperformed.

Recommendation: original HoloSelecta V1 + Roboflow Supervision's local Pascal VOC importer/YOLO exporter + the official Ultralytics training pipeline + COCO-pretrained `yolo11n.pt`. Write only the dataset-selection/split policy, preparation checks, inventory-output logic and counting evaluation. This replaces the proposed custom XML converter.

Future catalog, preference-based alternatives and marketplace work is recorded in [ROADMAP.md](ROADMAP.md). It does not expand this audit's implementation scope.

This is an inspection-based recommendation, not a measured model comparison. Repository code/configs, published metadata, model cards and selected archive contents were inspected. No third-party project was executed, dependencies installed, full dataset downloaded or model trained. HoloSelecta's actual five-class distribution, scene groups and importer compatibility remain the next implementation checkpoint.

## Datasets and distribution platforms

Sizes below refer to images unless explicitly stated otherwise. A platform's displayed license is distinguished from the original source license. Unknown means not verified, not absent.

| Resource | Type | Dataset size | Product-level labels? | Bounding boxes? | YOLO-ready? | License / provenance | Code available? | Use for v0.1? |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| [HoloSelecta V1](https://data.mendeley.com/datasets/gz39ggf35n/1) | Original dataset | 295; authors report 10,035 instances / 109 classes | Yes, with GTIN identities | Yes, VOC XML | Via existing Supervision conversion | Original record: CC BY 4.0 | General-purpose importer/exporter available; author repo is a dataset index | **Selected**, subject to five-class and scene audit |
| [RPC: author-linked Kaggle distribution](https://www.kaggle.com/datasets/diyer22/retail-product-checkout-dataset) | Original research dataset distribution | 83,739 / 200 classes, per original project | Yes | Yes | Original COCO-style annotations need export | [Original authors](https://rpc-dataset.github.io/): CC BY-NC-SA 4.0 | [Official evaluation tools](https://github.com/DIYer22/retail_product_checkout_tools) | Research comparison; not selected for startup path |
| [RPC on Hugging Face](https://huggingface.co/datasets/benjamintli/retail-product-checkout) | Dataset mirror / loader | 53,739 train + 6,000 validation + 24,000 test | Yes | Yes, `objects.bbox` | Parquet, not a ready YOLO directory | Card body preserves original NC-SA 4.0; metadata says NC-SA 2.0: mismatch | HF `datasets` compatible Parquet | Convenient RPC loader, same task/license limitations |
| [RPC on Roboflow](https://universe.roboflow.com/samrat-sahoo/groceries-6pfog) | Dataset mirror + hosted model | 83,699 displayed / 200 classes | Yes | Yes | Export available | Page says CC BY 4.0, conflicting with original NC-SA 4.0 | Export/API examples | Reject as a commercial shortcut; a mirror does not establish new rights |
| [SKU-110K](https://github.com/eg4000/SKU110K_CVPR19) | Original detection dataset | 11,743 in current [Ultralytics config](https://docs.ultralytics.com/datasets/detect/sku-110k/) | **No: one generic object class** | Yes | Official Ultralytics download/conversion exists | Authors restrict to academic/non-commercial use | Yes | Cannot supervise our product identities |
| [Roboflow Grocery v2](https://universe.roboflow.com/grocery-hy0vy/grocery-gf8x4) | Dataset + hosted model | 12,779 / 10 named products | Named products; size specificity unverified | Detection annotations advertised | Export available; downloaded files not checked | Listed CC BY 4.0; original collection/provenance undocumented | Export/API examples | Secondary lead only; real shelf scenes, duplicates and class support unverified |
| [Roboflow Grocery Products](https://universe.roboflow.com/objectdetection-l5dsv/grocery-products-g8jyk) | Dataset + hosted model | 623 / 118 classes | Many product/size labels, mixed with generic labels | Detection annotations advertised | Export available | Listed CC BY 4.0; source collection undocumented | Export/API examples | Not selected: duplicate-looking labels and unclear independent scene coverage |
| [Retail Coolers](https://universe.roboflow.com/roboflow-universe-projects/retail-coolers) | Dataset + hosted model | 216 source images; versions may be larger | **No: product / empty** | Yes | Export available | Listed CC BY 4.0 | Export/API examples | Useful for a different stock-gap task |
| [Grocer-Help public archive](https://zenodo.org/records/10464054) | Indian retail research dataset | Record says 7,371; inspected archive has 7,440 image stems across splits | Mixed brands, product families and product labels | Mixed box/polygon rows in sampled files | YOLO-style, but **not clean detection input as-is** | Zenodo API: CC BY 4.0; includes online-sourced images | Archive has YAML and annotations; no baseline adopted | Promising later Indian-domain dataset; more cleanup than HoloSelecta |
| [Kaggle Grocery Shelves / Unidata](https://www.kaggle.com/datasets/unidpro/grocery-shelves) | Commercial dataset preview | Full collection advertised as 5,000+; preview is smaller, count not verified | Precise SKU granularity unverified | XML annotations advertised | No | Preview: CC BY-NC-ND 4.0; full data sold separately | No verified preparation baseline | Not selected |
| [Kaggle Shelf Void Detection](https://www.kaggle.com/datasets/aminefaris/retail-shelf-void-detection-dataset) | Detection dataset | 536 / one void class | No | Yes | Yes, per card | Description says CC BY; license field says CC BY-NC-SA 4.0 | YOLO YAML | Wrong target; unresolved license mismatch |
| [Kaggle Blinkit prices](https://www.kaggle.com/datasets/tomtillo/blinkit-grocery-list-price-city-date) | Indian catalog/price table | Approximately 75,000 records, not shelf images | Catalog names only | No | No | Uploader lists CC0; source rights not independently established | Data-analysis resource | No detector training value |

RPC's original training split consists of isolated products, with multi-object checkout scenes in validation/test. A convenient mirror does not remove this domain gap. A HF loader also does not automatically provide the directories, class filtering and group split needed by Ultralytics.

For the Roboflow ten-product candidate, class names include `cereal_cheerios_honeynut`, `drink_greentea_itoen` and `pasta_lasagne_barilla`. Having ten names is promising, but the project publishes no collection description. Class names also occur in Unity synthetic-data examples; that is a provenance question, not proof this particular collection is synthetic. No full visual or duplicate audit was performed. Do not accept the displayed model score as a score on independent shelf scenes.

I did not verify a clearly sourced, product-identity-preserving HoloSelecta-to-YOLO release on GitHub, Kaggle, Hugging Face or Roboflow. That is a search result, not a claim that none exists. The HoloSelecta name search on the HF datasets API returned no matching entry. One actual [HoloSelecta conversion in ParallelDots' benchmark](https://github.com/ParallelDots/generic-sku-detection-benchmark) is for **generic product detection**, and its added annotations are research-only. It is not our five-product training dataset.

## The seven requested GitHub projects

Maintenance dates are GitHub API `pushed_at` values observed during this audit. They are signals, not guarantees that the code works or that the author has abandoned it. Sizes of underlying datasets are not sizes of a repository's actual usable training set.

| Repository | What inspected code actually provides | Labels / model fit | License evidence | Last push | Decision |
| --- | --- | --- | --- | --- | --- |
| [thisishardik/product-detection-in-retail](https://github.com/thisishardik/product-detection-in-retail) | YOLOv5 code, Colab notebook, YAML, detect/train scripts and Flask example | Root `data.yaml`: `nc: 1`, `names: [object]`; notebook downloads a Roboflow shelf-auditing version | GPL-3.0; dataset rights are separate | 2023-03-13 | Old training reference; use upstream Ultralytics instead |
| [K4R-IAI/retail-shelf-product-detection](https://github.com/K4R-IAI/retail-shelf-product-detection) | SKU CSV-to-YOLO preparation, training and evaluation, DVC configuration | Single `object` class | BSD-3-Clause code; SKU data has separate restrictions | 2023-05-10 | Do not adopt: wrong labels and a preparation bug |
| [KirbysGit/shelfVision](https://github.com/KirbysGit/shelfVision) | Custom PyTorch ResNet50/FPN detector, subset helper, evaluation and YOLO comparison | SKU-110K generic detection | No reuse license found in inspected tree | 2025-04-22 | Learning reference; not a small licensed YOLO base |
| [Engg-Abhinav/SmartShelf-AI](https://github.com/Engg-Abhinav/SmartShelf-AI) | Flask endpoints; SKU-trained DETR, CLIP/color/texture features, PCA and HDBSCAN grouping | Anonymous visual groups, not named SKU identities | No reuse license found in inspected tree | 2025-02-24 | API/grouping reference only; unnecessary machinery for v0.1 |
| [riashah1204/Retail-Shelf-Object-Detection-with-YOLOv8](https://github.com/riashah1204/Retail-Shelf-Object-Detection-with-YOLOv8) | Training notebook and short Gradio/counting app | Notebook YAML declares only `0: box`; `app.py` expects `app/best.pt`, absent from inspected tree | No reuse license found | 2026-03-30 | Useful counting concept; not a ready five-product project |
| [jebisha-17/Retail-Shelf-Inventory-Monitoring](https://github.com/jebisha-17/Retail-Shelf-Inventory-Monitoring) | Small OpenCV demo scripts | `jebi.py` supplies product names and box coordinates manually; no learned product detector verified | No reuse license found | 2025-05-19 | Does not provide the ML pipeline |
| [EmadElkabas/retail-shelf-stock-detection](https://github.com/EmadElkabas/retail-shelf-stock-detection) | Notebook comparing YOLOv8/RT-DETR, threshold analysis, SAHI and a checkpoint | Empty-slot class `missing`; README reports 2,418 images | README claims MIT; no LICENSE file found; data and weights need separate review | 2026-07-12 | Error-analysis reference; wrong prediction target |

Concrete source checks:

- [Hardik's class configuration](https://github.com/thisishardik/product-detection-in-retail/blob/master/data.yaml) establishes generic detection despite the inventory description.
- [K4R preparation](https://github.com/K4R-IAI/retail-shelf-product-detection/blob/master/src/prepare.py) discards the return from `cv2.imread` in both test and validation loops, then resizes the previous `image` variable. This can pair the wrong image with labels. The README also describes a dependency workaround.
- [SmartShelf model settings](https://github.com/Engg-Abhinav/SmartShelf-AI/blob/main/app/utils/constants.py) point to the SKU-110K DETR checkpoint. [Grouping code](https://github.com/Engg-Abhinav/SmartShelf-AI/blob/main/app/services/grouping_services.py) outputs cluster IDs; grouping similar packages does not name the products.
- [Ria's app](https://github.com/riashah1204/Retail-Shelf-Object-Detection-with-YOLOv8/blob/main/app/app.py) uses Python `Counter` for counts. Its final `demo.launch` lacks a call, so the published script needs repair even before assessing the model.
- [Jebisha's product display](https://github.com/jebisha-17/Retail-Shelf-Inventory-Monitoring/blob/main/jebi.py) uses a literal box dictionary.
- Emad's README references requirements and a Streamlit entry point not present in the inspected tree. Its published metrics concern empty slots and were not independently reproduced.

Public visibility is not sufficient permission to copy unlicensed code. These projects were inspected as references; no code from them was copied into StoreRoom.

## Infrastructure worth reusing

| Resource | What it replaces | License | Maintenance observed | Decision |
| --- | --- | --- | --- | --- |
| [roboflow/supervision](https://github.com/roboflow/supervision) | XML parsing, box conversion, YOLO label export and annotation utilities | [MIT](https://github.com/roboflow/supervision/blob/develop/LICENSE.md) | Push 2026-09-15; PyPI 0.30.3 observed | Use locally; no Roboflow account required for these APIs |
| [ultralytics/ultralytics](https://github.com/ultralytics/ultralytics) | Detection architecture, transfer learning, training loop, augmentation, checkpoints, prediction and mAP | AGPL-3.0 or Enterprise | Push 2026-09-16; PyPI 8.4.153 observed | Use official released package; pin a verified environment during setup |
| [Official Ultralytics notebook](https://github.com/ultralytics/ultralytics/blob/main/examples/tutorial.ipynb) | Basic training/validation/prediction examples | Upstream Ultralytics licensing | Maintained with upstream repository | Read/adapt the small relevant cells; no need to clone a retail application |

The [documented conversion API](https://supervision.roboflow.com/latest/how_to/process_datasets/) is `DetectionDataset.from_pascal_voc(...)` followed by `as_yolo(...)`. That eliminates a handcrafted converter. It does **not** select our five products, establish independent scenes or verify annotation correctness. We must check the chosen released version against real HoloSelecta XML before bulk export. Keep one global class mapping across all splits; independently inferred mappings could disagree when a split lacks a class.

Package versions above are observations, not a tested dependency lock. No package was installed during the audit. Python 3.14 is available on this machine; runtime/PyTorch compatibility and GPU support will be checked during environment setup.

## Pretrained models and Hugging Face resources

| Resource | Existing outputs / training data | Local artifact / loader | License and limits | Decision |
| --- | --- | --- | --- | --- |
| [Official YOLO11n](https://docs.ultralytics.com/models/yolo11/) | COCO generic categories; does not know our five SKU identities | `yolo11n.pt` through Ultralytics | AGPL-3.0 / Enterprise | **Initial transfer-learning checkpoint**; fine-tune on five products |
| [Official YOLO11s](https://docs.ultralytics.com/models/yolo11/) | Same general starting vocabulary, larger model | `yolo11s.pt` | Same licensing | Later comparison only if the nano baseline justifies it |
| [chistopat/sku110k-yolo11-object-detector](https://huggingface.co/chistopat/sku110k-yolo11-object-detector) | One class, `object`; SKU-110K fine-tuning | `weights/sku110k-yolo11-n640.pt` and s640, plus ONNX/checksums | Card says `other`, preserves upstream SKU restrictions | Research localization reference; not our startup checkpoint or product recognizer |
| [is36e/detr-resnet-50-sku110k](https://huggingface.co/is36e/detr-resnet-50-sku110k) | SKU object detection, 400 queries; not named products | Transformers loader; old `isalia99/...` link redirects here | Card says Apache-2.0, but source dataset is academic/non-commercial | Additional research baseline only; no commercial clearance established |
| [foduucom/product-detection-in-shelf-yolov8](https://huggingface.co/foduucom/product-detection-in-shelf-yolov8) | Card lists empty shelves and generic products; no SKU vocabulary verified | `best.pt`, config, old ultralyticsplus example | No license in inspected card/repository; training provenance unclear | Skip |
| [benjamintli/retail-product-checkout](https://huggingface.co/datasets/benjamintli/retail-product-checkout) | RPC images, category IDs and boxes | Parquet/config compatible with `datasets.load_dataset`; streaming supported by the library | Original RPC NC-SA terms remain; card metadata mismatch noted above | Best verified HF loader in this shortlist, but not selected data |

Hugging Face RPC loading was verified from the published Parquet schema/configuration, not executed locally. It still requires export for the YOLO filesystem format. No inspected checkpoint was established to recognize our eventual five HoloSelecta products out of the box. A model card's permissive badge alone does not settle rights associated with its training data, base code or weights.

The ready APIs/UI inspected mostly serve generic detection, gaps or clustering. An API would wrap the same predictions; it does not resolve missing product identity. Defer APIs and UI as specified in the project scope.

## Grocer-Help archive findings

This was the strongest new Indian-domain lead. The [2026 paper](https://www.nature.com/articles/s41598-026-42266-9) describes 13,771 images and 349 brand-oriented classes, but explicitly says only a subset is public. Do not equate that full research collection with the downloadable archive.

The [Zenodo V1 record](https://zenodo.org/records/10464054) lists a 4,202,584,064-byte ZIP and describes 7,371 images. Its [API metadata](https://zenodo.org/api/records/10464054) identifies CC BY 4.0. Using bounded HTTP Range requests, I inspected the ZIP directory, YAML and three label files without downloading the full archive:

- Actual image stems: 6,751 train + 689 valid = 7,440. Label stems: 6,741 train + 689 valid = 7,430.
- YAML declares `nc: 647`, not the paper's 349. Labels mix brands and generic categories and include `Maggi`/`MAggi`, `CocaCola`/`Cocacola`, and `ToothPaste`/`Toothpaste`.
- The sampled `0_train.txt` and `1_train.txt` contain both five-value detection rows and longer polygon-style rows. Detection preparation must explicitly normalize these; it is not a clean box-only export.
- Train has 11 image stems without same-split labels and one label stem without an image. Validation has one mismatch in each direction; `5208_train`/`5209_train` are among the cross-split inconsistencies. Missing labels cannot safely be assumed to mean background.
- A precomputed `labels.cache` is included; future preparation should regenerate caches after cleaning.

The observations are captured in [REUSE_AUDIT_EVIDENCE.json](REUSE_AUDIT_EVIDENCE.json). This is a useful future curation project, but it would add exactly the label-cleanup and split-debugging work we are trying to minimize initially. Online-image provenance also needs review before choosing such images for a commercial model.

## Commercial-use decision

Treat dataset, code, base weights, derived weights and hosted service terms as separate checks.

- HoloSelecta's original record lists CC BY 4.0. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) permits commercial adaptation with attribution, a license link and indication of changes. It does not make unrelated rights or model licenses disappear.
- Supervision is MIT: retain its notices when redistributing applicable code.
- Ultralytics is not permissive MIT/Apache infrastructure. Its [licensing guidance](https://www.ultralytics.com/license) covers code and trained/fine-tuned models and offers AGPL-3.0 or Enterprise terms. Use the AGPL-compliant portfolio route for this recommendation. A proprietary product needs an appropriate licensing arrangement or a separately reviewed alternative stack. AGPL is not simply a non-commercial license; commercial activity and closed-source licensing are different questions. Do not assume ONNX export removes obligations.
- Do not adopt RPC, SKU-110K or models trained on restricted data as a commercially cleared foundation based on a mirror's badge. Resolve the source restrictions first.
- No-license projects and conflicting license metadata are references, not approved code/data dependencies.

This audit establishes an engineering shortlist and flags unresolved rights; it is not a legal determination of a future application's obligations.

## Exactly what to use next

1. **Data:** HoloSelecta V1, DOI `10.17632/gz39ggf35n.1`, from [the original record](https://data.mendeley.com/datasets/gz39ggf35n/1). Obtain the grocery object-detection image/XML portion; the user-study and nutritional records are unnecessary. Preserve attribution, original filenames and a download checksum. Public metadata was accessible, but an automated file-list endpoint returned HTTP 403 during this audit; verify the actual archive/layout when downloading. This is not a claim of a tested downloader.
2. **Conversion:** the released `supervision` Python package, using the existing VOC import and YOLO export APIs locally. No HoloSelecta-specific converter fork.
3. **Training and inference:** the released `ultralytics` package and its official tutorial/documentation. No retail repository needs to be cloned into our runtime.
4. **Starting weights:** official `yolo11n.pt`, the detection checkpoint, not a classification or segmentation checkpoint. Fine-tuning is required; this is not a pretrained Maggi/Pepsi model.
5. **Existing supporting libraries:** Python, OpenCV, PyTorch as required by Ultralytics, and NumPy/Python collections for aggregation. Resolve compatible versions during setup rather than copying old Colab requirements.

## Exactly what we still write

| Our artifact | Purpose | Standard infrastructure reused |
| --- | --- | --- |
| `prepare_data.py` | Inspect class counts; choose five identities; preserve GTIN-to-class mapping; group scenes; filter labels; export splits; verify pairs/coordinates/count preservation | Supervision parses/imports/exports; Python handles the small policy layer |
| `class_map.json`, `splits.json`, generated `data.yaml` | Stable names and IDs 0-4, reproducible image assignments and correct paths | JSON/YAML libraries and YOLO's existing dataset interface |
| Short experiment notebook or command record | Record chosen weights, seed and training settings and call the upstream trainer | Ultralytics supplies training, augmentation, checkpoints and detection validation |
| `predict_count.py` | Run inference; retain boxes/classes/confidence; include all five counts including zeros; emit visible-item JSON and annotated image | Ultralytics Results API; Python Counter or NumPy bincount; existing plotting/OpenCV |
| `evaluate_counts.py` | Compare predicted and annotated counts; report per-class MAE, exact-all-five accuracy, false positives on negatives and error examples | Ultralytics supplies detection mAP/precision/recall; counting is our task-specific measurement |
| Dataset/experiment notes | Record source/license, corrected labels, split policy, results and limits | Plain Markdown |

Do not implement a custom optimizer, trainer, detector, XML parser, mAP evaluator, video tracker or backend service for this milestone.

The next checkpoint is a small data preflight: pair a few HoloSelecta images/XMLs, run the existing importer/exporter, draw exported boxes, and confirm identities/counts survive conversion. Then choose five classes using distinct-scene coverage, group duplicates and sessions before splitting, and keep validation/test separate. Target-only filtering must retain every selected-product box in an included image; include negative images as well. Raw image counts are not evidence of independent scenes.

If five classes cannot support distinct scene groups, report that result and revisit the shortlist before training. The goal is a credible first benchmark, not a high score produced by duplicate scenes or incomplete labels.
