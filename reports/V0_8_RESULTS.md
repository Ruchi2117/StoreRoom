# V0.8 results — product catalog and inventory bridge

Completed 2026-09-19. A confirmed shopkeeper scan now updates searchable, timestamped
visible quantities for a local demo shop while preserving the original AI prediction.
The customer prototype is available at `/customer` on the existing local backend.

## Delivered flow

```text
Shelf upload → unchanged detector → review/correction → confirmation
     → catalog identity lookup → latest reviewed shop quantity
     → customer product search → demo shop + quantity + timestamp + freshness
```

No model training, new inference configuration, field-validation changes, sales
deduction, synchronization, authentication, orders, payments or infrastructure.
This is a five-class product prototype, not verified live retail availability.

## Catalog, inventory and database

Schema version **2** adds `products`, `shops` and `shop_inventory` to the existing
three scan tables. Migration is additive and transactional; prior scan/evidence
columns and observations remain intact. Startup seeds five stable existing source
product IDs and one `local_demo_shop`, without inventing stock quantities.

Products contain name, normalized name, reliable brand/source variant descriptors,
nullable category/package size/image reference, visible-package unit, provenance
and creation/update timestamps. The existing source-class IDs are reused rather
than generated afresh. Pack size, verified SKU identity and other unsupported
metadata remain unknown; `catalog_sku_verified=false` is explicit.

ShopInventory uses `(shop_id, product_id)` as its unique primary key. Quantity is
a nonnegative integer; real observations require a valid source scan FK and
confirmation timestamp. Product/shop/scan references restrict deletion. Explicit
demo examples instead have null scan/timestamp and `is_demo=true`; no fake scan or
AI evidence is created to support the demo.

**Only shopkeeper-confirmed counts become inventory quantities.** AI 7 / reviewed 5
stores inventory 5 and retains historical AI 7. Subsequent observations replace
the previous quantity, never add to it. Only reviewed products update; omitted
classes remain unchanged and explicit zero means zero visible units confirmed.
Different products can therefore reference different latest scans.

Scan rows, original items/detections and inventory updates share one DB transaction
under the existing writer lock. Failed inventory updates roll back the new scan
and keep the previous quantities; photo cleanup follows the existing evidence
policy. Retrying an older successful confirmation returns its original scan without
replaying inventory over a newer observation.

No existing historical scan is automatically assigned/backfilled to the new demo
shop. Old history is preserved without pretending it is newly confirmed inventory.
There is no scan deletion API or destructive inventory cascade. The full restore
operation remains an explicit whole-snapshot replacement with retained rollback data.

## APIs, search and page

| Endpoint | Behavior |
| --- | --- |
| GET /products/search?q= | Exact, normalized, partial and brand/name matching |
| GET /inventory | Filterable inventory rows with nested product info |
| GET /inventory/{product_id} | Product and shop quantity records; unknown product 404 |
| GET /customer | Customer search/select/count page |

Inventory accepts product (list endpoint), shop and availability filters. `available`
means a recently confirmed positive non-demo visible count; it does not guarantee
stock now. `unavailable` means a recently confirmed zero; `stale` and `demo` have
separate filters. Known-but-unobserved product returns an empty inventory list, not
a fabricated zero. Existing scan/history/evidence endpoints remain functional.

Search normalizes Unicode/case/punctuation/spacing; `redbull`, `Red Bull` and
`Red--Bull` match the same product. Exact name matches rank first, then normalized
name/stable ID. Empty/punctuation-only search lists all five entries. No embeddings,
LLM, synonym service or external search engine was added.

The customer page supports searching, product selection, shop quantity, visible
last-confirmed time, manual refresh and a 30-second refresh for the selected product
while visible. It distinguishes DEMO / FRESH / STALE, warns that a count is not
guaranteed current stock and makes no nearby/geographic claim. Failed refreshes
clear old displayed counts. Desktop and mobile views were visually inspected.

Freshness defaults to one hour via `INVENTORY_FRESHNESS_SECONDS`; positive integers
only. Non-demo ages from zero through the configured threshold are FRESH; older or
future-dated timestamps are STALE. Nothing is automatically deleted. Seeded data
is always DEMO rather than pretending to have been confirmed recently.

## Deterministic opt-in demo

`python -m src.catalog_cli seed-demo` inserts missing example quantities only:
Red Bull 5, Knoppers 3, Valser Classic 2, Valser Still 4, Capri-Sun 6. Repeating it
does not duplicate rows or overwrite real confirmations. The page labels examples
“Demo quantities — examples only” and “Not confirmed — seeded demonstration data.”
Default user history was not seeded by the smoke test; its state was isolated.

## Backup/restore compatibility

Archive format stays **1**. New backups record schema **2** and include all six
tables in the checksummed SQLite snapshot plus referenced photos. Validation checks
non-demo inventory quantities against reviewed source scan items. Prior schema-1
archives remain readable; restore first preserves their old DB, then app startup
adds the catalog/shop/inventory tables. No invented backfill is performed.

A restored v0.8 snapshot recovers catalog IDs/metadata, shop, current inventory,
source scan pointers, timestamps and complete historical evidence. Backup writer
coordination and offline-only restore behavior are retained. V0.6 cannot consume
newer schema-2 snapshots; use v0.8 for those. Historical backup reports were not edited.

## Tests

**136 tests passed in 146.973 seconds: 121 previous/adapted + 15 new.**

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

[Full test output](v0_8_tests.log). `pip check` passed.

New tests cover idempotent catalog/shop seeding, stable IDs/null metadata,
duplicate product/shop/inventory prevention, deterministic search, confirmed versus
predicted counts, timestamps, replacement versus addition, old retries, omission
versus explicit zero, freshness boundaries/future times/configuration, demo
distinction, negative/fractional quantities and invalid scan FKs, restricted scan
deletion, rollback on inventory write failure, API filters/route compatibility,
mobile customer UI and both schema-1/schema-2 backup round trips.

One existing table-set assertion now requires all six tables instead of three.
No existing test was deleted or weakened; frozen v0.7 code, tests and fixtures are
unchanged. New tests use synthetic predictions; no test-set inference is involved.

## Real browser smoke

The real backend and Chromium were run with an isolated ignored database/storage
root. Input: ordinary validation image
`data/yolo_v01/images/val/IMG_20181218_170247.jpg`, used only for workflow checks.
One frozen-model prediction was performed; no accuracy measurement or tuning.
See [smoke record](v0_8_smoke.json).

| Check | Observed result |
| --- | --- |
| Customer page initially | Five products; Red Bull seed visibly labelled demo |
| Real upload/inference | Red Bull predicted 4 |
| Human correction/confirmation | Red Bull confirmed 3 |
| Customer search | Red Bull quantity 3, source linked to confirmed scan |
| Original AI history | Red Bull remains 4, same original detections/boxes/confidences |
| Other product state | Reviewed Valser records updated; two untouched seed rows retained demo labels |
| Timestamp / freshness | Actual confirmation time visible; FRESH shown with one-hour window |
| Live backup | Format 1 / schema 2, one scan, two photos, all inventory/catalog tables included |
| Stop/reset/restore/restart | Stored inventory/product data, source links, history and photo bytes preserved |
| Stale behavior | Restart with one-second inventory freshness threshold correctly displayed STALE |
| Historical scan after restore | Original/annotation images decode; correction still marked |
| Browser page errors | None |
| Responsive checks | No horizontal overflow; desktop/mobile screenshots inspected |

Only the **inventory freshness setting** changed for the stale-display check.
The model, thresholds, NMS, resolution and inference implementation never changed.
The model result remains a product smoke observation, not independent field data.
Screenshots, archives, photos and DBs remain ignored locally.

## Files and preservation

- New `src/catalog.py`, `src/catalog_cli.py`: tables, seed policy, search/inventory
  service, transactional bridge and opt-in demo command.
- Updated `src/storage.py`, `src/migrations.py`, `src/api.py`: additive migration,
  atomic confirmation integration and new routes.
- Updated `src/backup.py`: schema-1/2 validation and complete-state compatibility.
- New `src/web/customer.html`, `customer.css`, `customer.js`; existing scan page
  gains only a link to browse products.
- New `tests/test_catalog_inventory.py`; existing scan-history table-set assertion
  updated to the new schema.
- README, roadmap, [v0.8 guide](../docs/V0_8_PRODUCT_CATALOG_INVENTORY.md), this report
  and small test/smoke/preservation records.

[Integrity verification](v0_8_integrity.json) covers all 921 protected artifacts,
frozen dataset hashes, unchanged checkpoint/configuration and byte-identical v0.7
workflow/manifest/fixtures. Previous experiment reports, metrics and manifests are
unchanged. No retraining, field-data use or protected test-set evaluation occurred.
No private/generated photos, model weights, user DBs or secrets are committed.

## Limits and next milestone

One local demo shop, five source classes, unverified SKU/pack metadata, visible
counts only. No stock aggregation across shelves, sales deduction, live guarantee,
auth/tenants, location lookup, pricing, orders, payments, delivery or cloud services.
Model generalization remains unverified; the v0.7 real field cohort is still pending.

Next milestone: **a supervised single-shop pilot measuring correction effort,
staleness and differences between visible counts and observed shop availability**.
Collect independent evidence before broader model/availability claims. No pilot or
new model experiment was run as part of v0.8.

One meaningful `add product catalog and inventory bridge` commit follows validation.
The final task response records the commit hash, GitHub push and clean-tree status.
