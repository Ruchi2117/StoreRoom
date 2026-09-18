# StoreRoom product roadmap

Status: v0.1 CV experimentation is complete; independent-scene generalization remains unverified. The next engineering milestone is a reusable product-detection inference pipeline/API, not another model experiment. The [v0.1 scope](V0_1_SCOPE.md) and [reuse audit](REUSE_AUDIT.md) govern the first build.

The future customer experience connects a recognized product to its catalog record, the customer's explicit preferences, and alternatives with current offers from nearby participating shops.

## Milestones

| Version | Scope | Evidence needed to move forward |
| --- | --- | --- |
| v0.1 | Detect, identify and count visible instances of five products in one image | Annotated images, JSON output, detection/counting measurements on separate scenes and documented errors |
| v0.2 | Small product catalog | Stable product IDs; verified variant/pack identity; sourced product attributes with unknown values represented explicitly |
| v0.3 | Inventory synchronization | Shop-specific observations and inventory records, timestamps, corrections and reconciliation; repeated scans do not create duplicate stock |
| v0.4 | Preference-based alternatives | Explicit eligibility rules, explainable ranking, and evaluation using the catalog and inventory foundation from v0.2/v0.3 |
| v0.5 | Marketplace and local availability | Customer-facing alternatives linked to actual nearby shop offers, current prices and availability checks |
| v1 | Limited shopkeeper/customer pilot | Measure inventory discrepancies, correction effort, successful substitutions and purchase fulfillment in real shops |

v0.4 can be developed with clearly marked test inventory. The claim "available nearby" requires actual participating-shop data; a demonstration fixture must not be presented as a live offer.

These milestones define capabilities, not separate services. Add infrastructure only when implementation needs justify it.

## Data responsibilities

| Component | Owns | Required distinction |
| --- | --- | --- |
| Computer vision | Proposed identity, box, confidence and visible-item count | Recognition does not establish ingredients, price, dietary suitability or total stock |
| Product catalog | Product/variant identity, brand, pack size, ingredients, nutrition, allergen declarations and dietary attributes | Every relevant attribute needs a source, verification date and explicit unknown state |
| Shop offer/inventory | Shop ID, product ID, selling price, currency, quantity/status and update time | Price and availability vary by shop and time; they are not inferred from packaging appearance |
| Preference profile | Customer-specified restrictions and ranking preferences | Hard exclusions and budget limits must be distinguished from soft preferences |
| Alternative selection | Eligible candidates, rank and explanation | Similarity must not override a hard restriction or missing required evidence |

Model class IDs such as 0-4 are local to a model version. Map them to stable product IDs; do not use them as permanent catalog identities. Retain source product identifiers/GTINs where available. A brand-level or uncertain detection must not silently resolve to an exact variant with different ingredients. Ask for identification confirmation or abstain from attribute-based recommendations when identity is unresolved.

## Future alternative-selection behavior

1. Resolve the exact product identity or flag it for confirmation.
2. Find candidates serving the same intended use; consider pack size and product category.
3. Evaluate explicit restrictions against sourced catalog attributes. Each rule returns match, conflict or unknown, with a reason. Missing ingredient/allergen information, conflicting sources or unresolved ingredient names must not become a positive match.
4. Apply hard price limits and local offer eligibility. Candidates with unknown/stale availability or price cannot be described as confirmed purchasable alternatives.
5. Rank eligible offers using suitability for the intended use, comparable quantity/unit price where available, distance and soft brand preferences.
6. Explain the result using the relevant catalog evidence, shop, current offer price and availability timestamp. Return no verified match when the evidence is insufficient.

Start with transparent rules and a simple ranking function. A learned recommender or embedding system is a later option if evaluation shows a specific need.

Ingredient declarations, allergen warnings such as "may contain", explicit free-from claims, and missing information must remain distinct. Absence of a term from an incomplete record is not evidence that a product is free of it. Apply the customer's stated policy; do not invent acceptable exposure thresholds. Attribute provenance and packaging/formulation changes must be considered before presenting a current match.

## Medical-condition boundary

The product can surface ingredient/nutrition information and apply explicit restrictions supplied by the user, including a clinician-provided profile. It must not infer a treatment diet from a condition name or independently declare a product medically safe.

Use explanations such as "Excluded because your profile says to avoid ingredient X" or "Matches the recorded ingredient rules; source and verification date shown." Do not present a filter match as medical clearance, including for allergies. Vegetarian, vegan or religious-dietary claims also require appropriate product evidence; uncertain status stays unknown.

## Example acceptance scenarios for v0.4

- A known conflicting ingredient excludes a candidate, even if it is the closest or cheapest option.
- Missing or contradictory required ingredient data yields unknown and excludes the candidate from verified matches.
- With a hard INR 40 price limit, an INR 42 offer is excluded; without that cap, it may remain eligible.
- A matching product with stale availability is not counted in "2 alternatives available nearby."
- An unresolved pack/variant identity does not borrow attributes from another product of the same brand.
- A scan count is treated as an observation. It does not overwrite reconciled inventory without the v0.3 reconciliation rules.

These are future evaluation requirements, not implemented features or current safety guarantees.

## Current engineering commitment

The five-class experimentation phase is closed; see [v0.1 results](reports/V0_1_RESULTS.md). Next, reuse the tested class-confidence gate and counting functions in an image-to-structured-result component before adding a thin API. Preserve stable identity mapping, per-instance evidence and the explicit `visible_items` count meaning so later work has a useful foundation. Catalog enrichment, customer profiles, recommendation code and marketplace integration are outside v0.1.
