# StoreRoom v0.1: visible product detection and counting

Status: HoloSelecta data preflight completed, 2026-09-17. Original data downloaded and checksum-verified; five source product classes and machine-group splits selected. No model has been trained and no training stack is installed. See [reports/PREFLIGHT_REPORT.md](reports/PREFLIGHT_REPORT.md) for measured findings and [REUSE_AUDIT.md](REUSE_AUDIT.md) for the implementation decision.

## Problem

Given one RGB image of a shelf/display, locate each visible instance of five selected packaged products, assign its product class, and count accepted detections per class.

A class represents one specific product/variant/pack size when the source labels support that distinction. Brand-only totals can be derived later. The model must not guess pack size from apparent image size.

The actual preflight found that HoloSelecta does **not** reliably support exact pack-size SKU claims: regular Red Bull includes different can sizes under one label. The first public-data benchmark therefore uses source product classes: Red Bull regular, Knoppers, Valser Classic, Valser Still, and Capri-Sun Multivitamin. Stable `hs_*` IDs identify benchmark classes, not verified catalog SKUs; source GTINs remain metadata. Exact catalog identity is unresolved until later verification.

Counts describe visible items in this image. They do not describe hidden units, backroom stock, or total saleable inventory. Zero means no accepted detections, not proof of no stock. Each separately visible, identifiable physical package is one instance; a front-facing package may hide additional units that cannot be counted.

Dataset limitation: source annotations primarily count front packages, with some visible rear/occluded products unlabeled. HoloSelecta evaluation will explicitly measure agreement with **source-annotated front-package counts**, not claim exhaustive visible-item or inventory accuracy. The intended product behavior above needs later data with an explicit, consistently reviewed occlusion/counting policy.

## Dataset decision

Use a five-class subset of original HoloSelecta V1 for the first public-data experiment, subject to the class/scene audit below. Reuse Supervision's existing Pascal VOC import and YOLO export instead of writing a custom XML converter. Use the official Ultralytics trainer and `yolo11n.pt` transfer-learning checkpoint; no third-party retail application is required.

- Authors report 295 vending-machine images, 10,035 product instances and 109 product classes.
- Product-level bounding boxes and GTIN identifiers support localization, identification and counting in the same experiment.
- Source annotations use Pascal VOC XML: image dimensions plus product names and bounding-box coordinates. We will convert these to YOLO labels during preparation.
- Use the versioned Mendeley record below, which lists CC BY 4.0. Preserve attribution and record any transformations.
- Use the grocery object-detection portion; accompanying user-study records are unnecessary for this project.
- The reuse audit did not verify a suitable product-identity-preserving preconverted HoloSelecta release. Existing local conversion APIs remove the need for a custom converter; actual dataset compatibility still needs a small preflight.
- Dataset, code and weight licenses are separate. HoloSelecta lists CC BY 4.0 and Supervision uses MIT. Ultralytics offers AGPL-3.0/Enterprise licensing, including guidance for trained models; this recommendation assumes an AGPL-compliant portfolio project, not an automatically cleared proprietary deployment.

Sources:

- Dataset: https://data.mendeley.com/datasets/gz39ggf35n/1
- Author-maintained overview: https://github.com/tobiagru/ObjectDetectionGroceryProducts
- Dataset paper: https://doi.org/10.1016/j.dib.2020.106280

This is a small engineering benchmark, with vending-machine scenes from the Zurich area. Results will not establish performance on Indian kirana shelves or locally sold packaging. A later evaluation on consented local-shop images is necessary to establish that performance.

Alternatives considered:

- SKU-110K has dense retail shelves but only one generic object class in its detection annotations. It cannot directly supervise product identity: https://docs.ultralytics.com/datasets/detect/sku-110k/
- RPC has product identities but is a checkout dataset with isolated-product training images; its project page lists CC BY-NC-SA 4.0: https://rpc-dataset.github.io/

## Selecting the five classes

Do not invent a class list before reading the annotations. Audit per-class instance counts, distinct-image counts, scene diversity and label consistency. Select five well-represented, visually distinguishable SKUs with usable examples across separate scene groups. Keep source identifiers and create a stable mapping to YOLO class IDs 0 through 4.

Inspect representative images and boxes before fixing the subset. Repeated products in one image do not supply the diversity of the same number of independent scenes. Record any label corrections. If five classes cannot support meaningful separate evaluation groups, revise the dataset plan before training.

Retain all annotations for selected products in included images. Other products are background relative to this five-class task; they are not automatically a reliable unknown class. Keep some images containing no target products to measure false positives.

## Initial implementation boundary

One fine-tuned Ultralytics YOLO detection model will produce product classes and boxes. Counting code will aggregate accepted detections by class. OpenCV will load/inspect images and draw results. No separate classifier is required for the initial five-class experiment.

Input: one JPG or PNG. Outputs: an annotated image, per-instance boxes/classes/confidence scores, and JSON with all five product counts, including zeros, marked as visible-item counts. Use product IDs separately from display names. Example counts in documentation are illustrative until model inference exists.

Defer video, tracking, OCR, barcode scanning and general unknown-product recognition. A confidence threshold can reduce errors but cannot guarantee rejection of unfamiliar products.

Catalog enrichment, customer preference profiles and alternative-product recommendations are future milestones in [ROADMAP.md](ROADMAP.md). Preserve stable product IDs separately from model class IDs. The detector does not infer ingredients, allergen status, dietary suitability, selling price or confirmed local availability.

## Evaluation contract

- Use train, validation and test groups, aiming for approximately 70/15/15 where group sizes and class coverage allow.
- Keep photos of the same machine/scene/session and near duplicates in one split. Inspect filenames and images to establish groups; do not assume group metadata exists. Split before augmentation and keep all derivatives together.
- Train on training images. Choose thresholds and other settings on validation images. Reserve test images for the final evaluation of the frozen baseline.
- Report precision, recall, mAP50 and mAP50-95, including per-class results and test support.
- Report mean absolute counting error per class and the percentage of images where all five counts match the labels. Include zero-target images; compare against predicting zero for every class.
- Examine misses, duplicate boxes, class confusions and false detections on non-target products. Include unseen scenes with multiple instances of the same selected product.
- Report measured results without promising an accuracy before training. Separate public-dataset findings from any later local-shop findings.

Preflight selected 175 images in 33 sticker-supported machine groups: 123 train, 26 validation, 26 test. All five classes have multiple independent group proxies and multi-item examples in every split. See the preflight report for support, quarantines, and limitations. Next step: verify a compatible training runtime, install Supervision/Ultralytics only then, and test the existing VOC importer/YOLO exporter on these exact labels and coordinates before training.
