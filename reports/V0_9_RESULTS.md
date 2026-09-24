# V0.9 — Product alternatives and customer discovery

Completed 2026-09-24 against V0.8 commit `ec7a3dd`.

## Delivered behavior

`/customer` shows shop observations for a fresh positive count. With no recent
positive count it loads explicit related products, ordered by fresh positive
observations, relationship priority, and stable product ID. Every suggestion has a
reason, demo label where applicable, actual inventory state and timestamps.
Stale, zero, unknown and demonstration quantities remain distinguishable.

The implementation deliberately narrows the proposed design:

- Two opt-in demo relationships: Valser Classic ↔ Valser Still, labelled related
  variants with unverified equivalence. No invented alternatives for the other three.
- Separate optional sourced metadata and relationship tables preserve historical
  scan/product columns. Unknown attributes remain null; no ingredients or dietary
  claims are seeded.
- Restrictions require positive evidence. Missing facts exclude candidates; absence
  from an ingredient/allergen list does not mean free-from. Explicit conflicting
  declarations override explicit free-from declarations.
- Temporary preferences use a POST body, not persistent profiles or URL parameters.
  No new libraries, recommendation model, external API or infrastructure.

## API and UI

GET `/products/{product_id}/alternatives` returns unrestricted explicit relationships.
POST at the same path accepts diet, avoided allergens/ingredients, same-category and
same-variant restrictions. Invalid inputs return 422; unknown products return 404.
Responses include explanations, per-preference checks/exclusions and inventory rows,
and use `Cache-Control: no-store`. Existing search/inventory product JSON gains optional
sourced metadata; existing endpoints and scan history retain their contracts.

The customer page adds request-only controls, no-match and missing-information states,
demo relationship indicators, shop status, timestamps and related-product navigation.
It refreshes with the existing 30-second/manual mechanism; stale asynchronous responses
cannot replace a newer selection. The page does not claim medical suitability or
guaranteed stock.

## Verification

| Check | Result |
| --- | --- |
| Complete existing + new suite | **148 tests passed**, 83.579 seconds |
| New V0.9 tests | 12 passed: graph constraints, null facts, source validation, preference conflicts/unknowns, category rules, deterministic ranking, inventory states, API, backups and browser |
| Real Chromium browser smoke | Passed against the real local API with a fixture detector and disposable synthetic reviewed counts |
| Backup compatibility | Schema-1 and schema-2 snapshots restore and migrate; schema-3 round trip preserves catalog metadata, relationships, inventory links and evidence |
| Frozen assets | **921 protected files** verified; frozen dataset hashes unchanged |
| Previous tracked assets | **165 prior files** byte-identical to `ec7a3dd`, including previous reports/configs, inference and frozen V0.7 workflow/tests/docs |
| Training / protected test evaluation | Neither occurred |

Reproducible suite command:

```powershell
$env:STOREROOM_V09_SMOKE='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The optional environment flag also writes browser screenshots to ignored
`outputs/v09/` and a compact smoke record. Tests use temporary stores, not private data.
Evidence: [suite log](v0_9_tests.log), [browser smoke](v0_9_smoke.json),
[integrity manifest](v0_9_integrity.json).

The browser covered search/select, fresh requested inventory, deliberately stale
requested inventory, a fresh related-product observation with timestamp, demo and
relationship explanation labels, an incompatible variant filter, unknown vegan
metadata exclusion, a stale alternative, and no alternatives for Red Bull. Mobile
390px layout had no horizontal overflow; no JavaScript errors occurred. Desktop and
mobile screenshots were visually reviewed. These are workflow checks, not measured
model predictions or field-validation evidence.

Checkpoint SHA-256:
`099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`.

Frozen V0.7 protocol SHA-256:
`4d59789dbc368ac7a9b73f58556108c567a8a87eedbbd40b2bf685029953083d`.

## Limitations and next milestone

The catalog still contains five source classes, one demo shop, no verified SKU
enrichment and no true nearby-shop discovery. Dietary/category filters will exclude
the current demo pair because required evidence is missing. Exact-term matching is
not synonym resolution or a complete interpretation of packaging/allergen warnings.
No actual field cohort has been collected; independent model generalization remains
unverified. Counts describe reviewed visible packages, not sales-adjusted stock.

Next: **basic order-request flow**, with a shopkeeper availability confirmation step
before acceptance. Do not add further recommendation intelligence for the next milestone.

See [implementation and usage](../docs/V0_9_ALTERNATIVES.md).
