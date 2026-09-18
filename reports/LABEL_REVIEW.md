# HoloSelecta source-label review

Reviewed on 2026-09-16 against the extracted, checksum-verified source archive. This report describes the source before image exclusions, label corrections, or class selection. It does not establish independent scenes or authorize a training split.

## What the source actually contains

Independent XML inspection confirms 295 annotation files, 10,036 annotated objects and 115 distinct literal class labels. There are 277 paired images with 9,486 annotated objects; all 115 labels occur in the paired subset. These are observed archive counts, not the published dataset totals. See `dataset_summary.json`, `image_manifest.json` and `class_counts.csv` for the reproducible audit output.

The labels combine human-written product descriptions, size-like fields and, sometimes, a numeric identifier. Preserve the complete literal label and the identifier as a string. Leading zeros matter. A checksum-valid identifier only passes a formatting check: no external product catalog, GS1 assignment, exact variant or package volume has been verified in this review.

## GTIN extraction and source defects

The strict extractor accepts a terminal underscore-delimited numeric suffix of 8–14 digits; the separate validator permits GTIN lengths 8, 12, 13 and 14 and checks the check digit.

| Source-label category | Distinct labels |
|---|---:|
| Numeric suffix extracted | 69 |
| Of those, checksum valid | 64 |
| Of those, checksum invalid | 5 |
| No barcode suffix supplied | 44 |
| Malformed seven-digit suffix | 1 |
| Numeric suffix followed by `#` | 1 |
| Total literal labels | 115 |

The 69 extracted suffixes contain **59 distinct nonempty identifiers**. A set that also includes the missing-value marker `None` has 60 members; that does not mean 60 products have verified identities. The 46 labels without an extracted identifier account for 414 objects across all XML files and 363 objects in paired images.

Examples of genuinely missing identifier fields include `berger_schoggitoertli____` in `DSC01658.xml` and `tiki_himbeerbrause_dose_33_1_` in `DSC01644.xml`. Their final size or quantity fields must not be interpreted as GTINs.

Two malformed suffixes need explicit source review:

- `coke_light_flasche_50__5449238`, for example in `IMG_20190306_172403.xml`, has seven digits. Do not invent a missing digit or infer the intended product identifier.
- `redbull_light__33__90162800#` occurs in `IMG_20181218_172859.xml`. Removing `#` produces checksum-valid `90162800`, which also occurs as the suffix of `redbull_light__33__90162800`. This is a plausible correction candidate, not a correction applied by the audit. Record and review any normalization before merging labels.

The five extracted identifier strings that fail checksum validation are:

| Literal source label | Extracted identifier | Example XML |
|---|---|---|
| `volvic_pinapple__50__305764335648` | `305764335648` | `DSC01638.xml` |
| `7days_croissantschoko_packung_80_1_0000000000003` | `0000000000003` | `DSC01644.xml` |
| `stimorol_spearmint_riegel_14_1_0000000000005` | `0000000000005` | `IMG_20181218_170243.xml` |
| `skittles_sour_riegel_51_1_0000000000004` | `0000000000004` | `IMG_20181218_170243.xml` |
| `tiki_himbeer_brause__50__00000000009342` | `00000000009342` | `IMG_20181218_170247.xml` |

The mostly-zero strings look like local placeholder identifiers. That is an inference; their provenance has not been established. They must not be presented as verified commercial product IDs.

## Conflicting labels sharing an identifier

Eight extracted identifiers occur under multiple literal labels. Some could be aliases, while others describe different sizes, packaging or variants. A shared identifier is not sufficient evidence to merge them.

| Identifier | Conflicting source descriptions |
|---|---|
| `7610046000259` | Kagi / Kagi special edition |
| `5000159461122` | Snickers / Snickers white (`weiß`) |
| `5449000235947` | Fuse lemon with `50` / lemon can with `33` |
| `5449000236623` | Fuse peach with `50` / peach can with `33` |
| `7610057001078` | Ramseier apple juice with `50` / Tetra Pak with `33` |
| `54491472` | Coke with `50` / can with `33` / bottle with `50` |
| `7613100037253` | Comella chocolate drink with `33` / bottle with `50` |
| `7610235000442` | Henniez blue / green / red |

The size-like numbers above are copied from source descriptions, not confirmed physical package measurements. The complete conflicting labels are retained in `dataset_summary.json` under `gtin_label_collisions`.

## What an annotation count means here

Visual review shows that many annotations describe the front-facing products in vending-machine lanes. Portions of additional packages behind the front item remain visible without separate boxes. Consequently these annotation counts cannot be treated as exhaustive counts of every visible physical item, or as total inventory.

Two reviewed examples make the distinction concrete:

- `IMG_20190125_133951.jpg` has **37**, not seven, annotations. The front products visually match that total: five on the first row and eight on each of the next four rows. Rear packages are also partly visible. This check supports the front-facing interpretation; it is not a certification of every SKU assignment.
- `IMG_20190206_170217.jpg` also has **37** annotations. A further partially obscured carton appears at upper-left slot 10 beneath the REC sticker. The annotated Comella box starts at slot 11. Treat the slot-10 object as a potential missing annotation requiring review before claiming complete visible-object counting ground truth. Its precise identity has not been confirmed.

The XML `difficult`/`truncated` flags do not by themselves establish completeness. The counting policy must define treatment of rear products, occlusion and reflections, then verify annotations against that policy.

## Initial candidate comparison

These were the initial candidates; the final selection in `configs/class_map.json` replaces M&M's with Valser Still. All entries below have checksum-valid identifiers unique to one literal label in this source. These counts describe raw paired images before exclusions.

| Literal source label | Paired images | Annotated objects |
|---|---:|---:|
| `redbull___33__90162909` | 233 | 849 |
| `knoppers_riegel____4035800488808` | 210 | 358 |
| `valser_classic__50__76404160` | 207 | 295 |
| `mnms_gelb__45__40111445` | 194 | 195 |
| `caprisun_multivitamin__20__4000177605004` | 176 | 344 |

Representative images such as `20190103_103704.jpg` and `IMG_20190502_171332.jpg` show useful packaging diversity: a slim can, wrapped bar, green bottle, yellow confectionery bag and blue/silver pouch. They also expose reflection and occlusion challenges. This supports investigating those classes; it does not verify package sizes or guarantee clean annotations throughout the dataset.

M&M's has particularly weak counting diversity: 193 paired images contain one annotated instance and only one contains two. Across all 277 paired images, the other 83 contain no M&M's annotations. Recognition performance for this class must not be presented as evidence that the model counts large piles of the product accurately.

`zweifel_paprika__90__7610095013002` is a reserve candidate with 164 paired images and 173 objects. Its orange packaging is distinctive, but its raw counting support is also mostly one instance: 155 images contain one and nine contain two.

Red Bull Light and Valser Still provide useful visually similar non-target examples when evaluating the corresponding candidates. High image counts and multiple capture dates do not prove independent-scene coverage. Final eligibility, exclusions and scene-separated support belong to the separate scene audit.

## Final fifth-class decision and size limitation

After scene quarantine, M&M's has 123 positive images, all with count one. The final
selection uses `valser_still__50__7610335002575`: 117 positive images, 165 instances,
32 machine groups, and 19 multi-item images across seven groups. Valser Still is
therefore a **target** in the final map; measure confusion with Valser Classic.
Red Bull Light remains a non-target.

Zweifel Paprika retained only five multi-item images across three groups. C+Swiss
had excellent count support, but selecting it would remove every whole-image
negative in the supported subset. It also has an incomplete-label alias
`c+swiss_dosenabisicetea__33_` in `IMG_20190206_170222.jpg`; treating that alias as
background would be incorrect if C+Swiss were selected. No source correction was made.

The source label `redbull___33__90162909` is not a reliable exact-size SKU: the
review of `IMG_20181218_165652.jpg` found 250 ml and 355 ml regular cans under it.
Other representative crop labels visibly show 250 ml despite the source `33`
token. Keep the source identifier for traceability, but do not assert a verified
GTIN-to-size relationship. The final `hs_*` IDs denote benchmark product classes.
