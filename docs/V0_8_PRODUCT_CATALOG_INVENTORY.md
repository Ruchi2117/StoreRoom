# V0.8 — product catalog and inventory bridge

Confirmed scan counts now feed a small searchable catalog/inventory layer.
**Quantity is the latest explicitly reviewed visible-package count for a product**,
not total shop stock, hidden stock, sales-adjusted stock or guaranteed availability.
The frozen CV and v0.7 field-validation workflow are unchanged.

## Run and demonstrate

Use the existing environment and frozen checkpoint. No new dependencies.

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Shopkeeper: [scan and review](http://127.0.0.1:8000/).
Customer prototype: [find a product](http://127.0.0.1:8000/customer).
The product page loads all five catalog entries; search by name/brand, select a
product and view the demo shop's latest quantity, timestamp and freshness.
No inventory row means **not yet confirmed / unknown**, not zero stock.

Startup seeds five catalog identities and one **Demo Shop**, but no quantities.
To demonstrate the customer page without a scan, explicitly seed examples:

```powershell
.\.venv\Scripts\python.exe -m src.catalog_cli seed-demo
```

Optional `--database` and `--scans` override `STOREROOM_DB_PATH` and
`SCAN_STORAGE_DIR`, matching the existing configuration. The command is local,
uses the same writer lock and only fills missing inventory rows. Running it again
does not reset confirmed quantities or recreate duplicates. The default seed
values are Red Bull 5, Knoppers 3, Valser Classic 2, Valser Still 4, Capri-Sun 6.
They have no scan or confirmation timestamp and are visibly marked **Demo
quantities — examples only**. They are excluded from real availability filters.

After a real scan, reviewed products replace their demo rows and link to that scan.
Unreviewed products keep their previous state, including demo labels where relevant.
The shop itself remains a local demo identity; a real photo does not turn it into
a verified participating business or prove proximity to a customer.

## Architecture and identity

```text
Unchanged detector → original predictions/evidence
                              ↓ human review
Confirmed Scan + ScanItems + ScanDetections
              ↓ same SQLite transaction
Catalog product lookup → ShopInventory (latest confirmed visible quantity)
              ↓
Product search API → customer page → quantity + timestamp + freshness
```

A product identity exists independently of a shop's count. Stable IDs reuse the
existing model-to-source-product mapping:

| Class | Product ID | Brand | Known variant descriptor |
| --- | --- | --- | --- |
| Red Bull | hs_redbull_regular | Red Bull | null; source class regular, sizes mixed |
| Knoppers | hs_knoppers | Knoppers | Riegel |
| Valser Classic | hs_valser_classic | Valser | Classic |
| Valser Still | hs_valser_still | Valser | Still |
| Capri-Sun Multivitamin | hs_caprisun_multivitamin | Capri-Sun | Multivitamin |

Source: unchanged `configs/class_map.json`. These are **source product classes,
not verified retail SKUs**. Numeric class IDs are lookup keys within this model,
not permanent catalog identities. Package size, category and image reference are
null; no external photo/size, price, ingredients or other enrichment was invented.
`unit=visible_package` describes counted objects, not litres/grams or a verified
sale unit. Catalog responses expose `catalog_sku_verified=false` and provenance.

## Schema and additive migration

Existing Scan/ScanItem/ScanDetection columns and old observations stay intact.
SQLite `user_version` advances from 1 to **2**, adding:

- `products`: product_id PK, unique model class_id, name, unique normalized_name,
  brand/category/variant/package_size/unit/image_reference, metadata_source,
  created_at/updated_at.
- `shops`: shop_id PK, name, is_demo, created_at/updated_at. One fixed local identity
  `local_demo_shop`; no registration, location, tenants or authentication.
- `shop_inventory`: composite PK `(shop_id, product_id)`, quantity, last_confirmed_at,
  source_scan_id, updated_at, is_demo. Product/shop/scan FKs use RESTRICT.

Quantity must be a nonnegative SQLite integer within the existing safe-count
range. Non-demo rows require a real scan FK and last-confirmed timestamp. Explicit
demo rows require null scan/timestamp instead of fabricating a historical scan.
The composite key prevents duplicate stock rows. Catalog IDs/class mappings and
normalized names cannot be duplicated. Metadata seeding is idempotent.

Migration is transactional and additive. Existing v0.4/v0.5/v0.6 observations remain
readable. **Historical scans are not automatically backfilled into the demo shop's
inventory**: they had no explicit shop assignment, and startup must not pretend an
old observation is newly confirmed. Confirm a new scan or use labelled seed data.

## Confirmation semantics and failure handling

`POST /inventory/confirm` retains its existing request/response shape. Under the
existing writer lock it validates the original prediction, publishes images, adds
Scan/items/detections, resolves each reviewed item's source product ID, and writes
inventory in **the same SQLite transaction**. Quantity uses `confirmed_count`;
the original `predicted_count`, boxes and confidences stay unchanged.

New confirmation **replaces**, never adds to, a product's previous visible count.
Example: AI 7 → reviewed 5 stores inventory 5 and historical AI 7. A later review
of 2 replaces 5 with 2, not 7. Only explicitly reviewed classes update. Omitted
zero-prediction classes do not wipe prior records; explicitly reviewing zero does
record zero. Thus products may legitimately reference different latest scans.
Multiple shelves/photos are not summed or reconciled into a whole-shop total.

The scan's UTC confirmation timestamp becomes last_confirmed_at/updated_at.
Retrying the same prediction with identical review returns its historical scan
without refreshing or replaying inventory, so retrying an old scan cannot undo
a newer count. A changed retry remains a conflict as before.

If inventory writing fails, the transaction rolls back scan/items/detections and
inventory together, keeping the prior quantity and cleaning newly published photo
files where safe. Pending draft evidence remains available for retry. Existing
filesystem/SQLite crash limits from v0.5/v0.6 still apply.

## APIs

| Endpoint | Behavior |
| --- | --- |
| GET /products/search?q= | Catalog results, including products not yet observed |
| GET /inventory | Stored quantities with nested product metadata and shop identity |
| GET /inventory/{product_id} | Product + inventory list; unknown product returns 404 |
| GET /customer | Simple customer product/search page |

Inventory endpoints accept optional `product_id` (list endpoint), `shop_id`, and
`availability`. Unknown list filters return an empty array. Known product with no
inventory returns a product plus an empty array. Existing `/inventory/scans` and
evidence/history routes retain precedence and behavior.

Availability filters:

- `available`: non-demo, FRESH and quantity > 0; means recently confirmed positive,
  **not guaranteed current availability**.
- `unavailable`: non-demo, FRESH and quantity = 0; zero visible units were confirmed.
- `stale`: non-demo observation beyond the freshness window, or future timestamp.
- `demo`: explicitly seeded example quantities only.

Example requests:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/products/search?q=redbull'
Invoke-RestMethod 'http://127.0.0.1:8000/inventory?shop_id=local_demo_shop&availability=available'
Invoke-RestMethod 'http://127.0.0.1:8000/inventory/hs_redbull_regular'
```

Each row includes quantity, quantity_meaning, full product information, shop ID/name,
shop_is_demo, is_demo, source_scan_id, last_confirmed_at, updated_at, freshness,
freshness_seconds, age_seconds, recently_confirmed_positive and
`guaranteed_available=false`. Times are UTC ISO 8601. No raw evidence filesystem
paths are exposed through the new APIs.

## Search

Names are normalized using Unicode NFKC, casefolding, punctuation-to-space and
collapsed whitespace. Search matches normalized partial names/brands and a
space-free form (`redbull`, `Red--Bull`, full-width Latin letters). Exact normalized
or space-free product-name matches rank first; remaining results sort by normalized
name then stable ID. Empty or punctuation-only query lists all five products.
Queries are capped at 100 characters. There are no SQL wildcard semantics, embeddings,
LLMs, synonyms, fuzzy SKU identification or recommendations.

## Freshness and customer UI

Configure before starting the app:

```powershell
$env:INVENTORY_FRESHNESS_SECONDS = '3600'
```

Default: 3600 seconds. It must be a positive integer. Non-demo observations are
FRESH when `0 <= age <= threshold`; older/future-dated observations are STALE.
Seed rows have status DEMO with no claimed confirmation time. Freshness is computed
at read time, not written by a job. Stale data is never automatically deleted.

The page visibly distinguishes recent, stale and demo quantities and always shows
the actual last-confirmed time when available. It uses “check with the shop,” not
a promised purchasable offer. It offers manual refresh and refreshes the selected
product every 30 seconds while visible. Counts clear on a failed refresh instead
of masquerading as fresh. No live sales deduction/synchronization is implied.

## Deletion, reset and backup compatibility

No scan/product/shop deletion endpoint was added. Deleting a scan currently referenced
by inventory is rejected by its RESTRICT FK; a failed deletion transaction leaves
history and evidence intact. Historical observations remain read-only in the UI.
Do not manually edit/delete SQLite rows or photos. No destructive cascade from
Scan into ShopInventory was introduced. There is no inventory event ledger beyond
the preserved scan observations and current source pointer.

Full backup/restore remains the explicit replacement mechanism: current DB plus
photos are replaced by the validated snapshot, with rollback copies retained. A
restore may intentionally restore an older inventory view; it never pretends to
keep newer sales/counts or merge histories.

Archive format remains **1**; schema version is now recorded dynamically. V0.8
accepts prior schema-1 backups and new schema-2 backups. Schema-2 backups include
all six tables and validate non-demo quantities against reviewed source ScanItems.
After restoring schema 1, normal app startup runs the additive migration, seeds
metadata, and leaves inventory unpopulated. V0.6 cannot read newer schema-2 backups;
restore those with v0.8. The old backup reports/guides are historical; these
compatibility rules supersede their schema-1-only statement.

## Verification and limitations

Run `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
Catalog/inventory tests cover identity and duplicate prevention, search, timestamps,
freshness/configuration, quantities versus predictions, replacement/retry semantics,
omitted versus explicit zero, rollback, FK/deletion policy, APIs, browser UI, demo
labels and both backup schema versions. See [results](../reports/V0_8_RESULTS.md).

Still local SQLite and a single demo shop; no authentication, verified shop location,
prices, reservations, payments, delivery, automated deductions, model optimization
or new infrastructure. The five-class model remains provisional, and field
generalization remains unverified. Pack sizes/retail SKUs remain unverified.

Next milestone: a supervised single-shop pilot to measure correction effort,
staleness and differences between visible counts and observed shop availability.
Independent-scene collection/validation remains necessary before wider model claims.
No pilot or model tuning is performed in v0.8.
