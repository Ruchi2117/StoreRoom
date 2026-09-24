# V0.9 — explicit product alternatives

StoreRoom now connects catalog relationships to reviewed visible counts on `/customer`.
This is a five-product, single-demo-shop discovery prototype. It does not establish
product equivalence, dietary safety, live stock, prices or nearby shop availability.
No new dependency, model, training, inference configuration or evaluation is involved.

## Run and demonstrate

Use the existing environment and backend:

```powershell
.\.venv\Scripts\python.exe -m src.catalog_cli seed-alternatives-demo
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/customer`, search **Valser**, select Classic or Still.
When the selection has no recent positive count, the other variant appears, with
**Demo catalog relationship** and an explanation that equivalence is unverified.
Inventory remains unknown until a count exists. Optionally run the separate
`src.catalog_cli seed-demo` command for conspicuously labelled example quantities.
Both commands accept `--database` and `--scans`; use the same paths as the server.
Neither command replaces existing records. The relationships are opt-in, not seeded
by startup or migration. No private database or photographs are shipped.

With a fresh positive reviewed count, the page shows that product's shop observations.
Otherwise it shows related products and preference controls. Refresh is manual or
every 30 seconds while the page is visible; old alternative results clear immediately
on refresh, and late responses cannot overwrite a newer selection. A failed lookup
shows an error rather than retaining apparently current alternatives.

## Data structure and provenance

The existing stable product IDs and model class mapping are unchanged. Existing
brand/variant values come from the frozen source-class identity; pack sizes and
categories remain unknown. No inferred ingredients, dietary claims or prices were added.

Schema **3** adds two tables, keeping historical scan and product columns intact:

| Table | Fields and meaning |
| --- | --- |
| `product_metadata` | One optional row per product: validated `facts` JSON, nonempty evidence `source`, `updated_at`. Without sourced, structurally valid facts, all additional attributes return null. |
| `product_alternatives` | Directed `(source_id, target_id)` primary key, `related_variant` or `substitute`, nonnegative integer `priority`, explicit `reason`, `is_demo`, `created_at`. Product foreign keys; self-links and duplicate pairs are rejected. |

`Facts` supports nullable `dietary_tags` (vegan/vegetarian), `allergen_tags`,
`ingredients`, `free_from_allergens`, `free_from_ingredients`, and `subcategory`.
Free-from lists represent **explicit sourced declarations**, never inferred absence
from an ingredient list. Empty lists do not prove absence. Metadata source and date
are returned alongside the facts. Search and inventory product objects include this
optional metadata too. The page shows source when present.

No verified ingredient/dietary data is available for these five source classes, so
the application seeds none. Tests use clearly synthetic declarations in disposable
databases. Before importing real metadata, verify exact SKU/variant/formulation,
record the evidence source and review date, and validate with `Facts.model_validate`.
There is no public metadata editor or external catalog scraper in this milestone.
The existing five-class identity constraint remains; wider SKU coverage requires a
separate catalog/model mapping change, not fabricated classes in this feature.

## Matching and ranking

1. Consider only outgoing explicit relationships. Sharing a brand or category never
   creates a suggestion automatically.
2. Evaluate each selected restriction: **match**, **conflict**, or **unknown**.
   Both conflict and unknown exclude the candidate.
3. Rank surviving candidates with a fresh positive reviewed count first, then
   ascending relationship priority, then stable product ID. No numerical similarity
   score or independent category inference is used.
4. Return relationship reasons, preference checks, metadata, and inventory evidence.

`same_category` requires two known equal category strings. `same_variant` requires
two known equal variant strings; the demo Valser pair fails this deliberately stricter
filter. Dietary filters require an explicit selected tag. Ingredient/allergen avoidance
requires an explicit matching free-from declaration; a positive conflicting declaration
wins if both are present. Matching uses normalized exact terms, not substring or synonym
inference. An unresolved term remains unknown. Composite ingredient strings, synonyms,
trace warnings and medical restrictions are not automatically interpreted. Do not import
an ambiguous warning as a free-from declaration.

Without restrictions the result says **preference compatibility not assessed**.
With passed restrictions it says **matches selected catalog declarations**, never
medical suitability or allergy safety. This is catalog filtering, not medical advice
or a complete ingredient-risk assessment. Unknown required facts produce no suggestion.

## Inventory semantics

All inventory comes from the unchanged V0.8 reviewed-count bridge. Alternatives use
one UTC timestamp per request for freshness checks and the same configured freshness
window (default 3,600 seconds).

| API state | Meaning |
| --- | --- |
| `RECENT_POSITIVE` | At least one fresh, positive, non-seeded observation; check with the shop |
| `RECENT_ZERO` | Fresh zero count, no fresh positive count |
| `STALE` | Recorded observations exist but are outside the freshness window |
| `DEMO` | Only seeded example quantities exist; no confirmed observation |
| `UNKNOWN` | No inventory record |

Non-positive states remain visible as related catalog products with their actual
status; they are not presented as purchasable alternatives. Each shop row includes
quantity, timestamp, demo status and `guaranteed_available: false`. The only seeded
shop is **Demo Shop**, visibly labelled even for reviewed fixture observations.
Hidden packages, sales since the photo and other shelves are unknown.

## API and request-level preferences

Existing search and inventory endpoints remain compatible.

```text
GET /products/search?q=valser
GET /products/hs_valser_classic/alternatives
POST /products/hs_valser_classic/alternatives
```

GET uses no restrictions. POST accepts a JSON body, avoiding preferences in URLs:

```json
{
  "diet": null,
  "avoid_allergens": [],
  "avoid_ingredients": [],
  "same_category": false,
  "same_variant": false
}
```

`diet` accepts null, `vegan` or `vegetarian`. Lists accept at most 20 terms, each
1–80 characters; empty normalized terms, extra fields and wrong types return 422.
Unknown products return 404. Responses contain `alternatives`, `excluded` checks,
`source_availability`, and the ordering rule. Responses use `Cache-Control: no-store`.
The service never writes preferences to its database; the page uses no local/session
storage or cookies. Form state lasts until reload. Do not enable request-body logging
when deploying behind another server.

## Demo limitations and next step

Only Valser Classic ↔ Valser Still is seeded, as a **demo related-variant** pair.
The relationship says they share a brand and have different names, not that they have
identical contents or use. Red Bull, Knoppers and Capri-Sun return no alternatives.
No Red Bull → Knoppers suggestion or fabricated sixth product is introduced.
Category filters and dietary filters currently exclude the demo pair because their
required evidence is missing. This is intentional, not a broken recommendation engine.

The next milestone is a **basic order-request flow**: customer requests a product and
quantity; the shopkeeper confirms current availability before accepting. Keep it local
and supervised initially. Further recommendation intelligence, payments and delivery
are outside V0.9; field evidence is still required for model generalization claims.

## Migration, backup and verification

Startup atomically creates the two new tables and advances `user_version` to 3.
No previous scan, quantity, product identity or frozen field artifact is rewritten.
Backup format remains 1; schema versions 1, 2 and 3 are validated using their respective
table sets. Restored schema-1/2 databases migrate on normal startup. Schema-3 archives
include relationships and metadata automatically. Older application versions cannot
read schema 3: retain an older snapshot if planning an application downgrade.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The suite covers explicit graph constraints, unknown/conflicting metadata, ranking,
freshness states, request validation, schema-1/2 restore migration, schema-3 round trips,
existing scan/evidence workflows, and Chromium customer interactions. Browser fixtures
are synthetic; they do not measure model accuracy or field performance.
