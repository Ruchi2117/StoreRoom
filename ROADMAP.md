# StoreRoom product roadmap

Status: v0.8 product catalog and inventory bridge is complete. Independent-scene generalization remains unverified; the v0.7 workflow is frozen and awaits real field collection. The model and original experiment history remain unchanged. Current product behavior is documented in [v0.8](docs/V0_8_PRODUCT_CATALOG_INVENTORY.md).

The future customer experience connects a recognized product to its catalog record, the customer's explicit preferences, and alternatives with current offers from nearby participating shops.

## Milestones

| Version | Delivered scope | Status |
| --- | --- | --- |
| v0.1 | Reproducible five-class CV pipeline | Complete; provisional model, generalization unverified |
| v0.2 | Reusable inference API | Complete |
| v0.3 | Shopkeeper scan/review/correction | Complete |
| v0.4 | Durable scan history | Complete |
| v0.5 | Original photos, predictions and detections as evidence | Complete |
| v0.6 | Local backup and restore | Complete; schema-2 compatibility added in v0.8 |
| v0.7 | Independent field-validation workflow | Implemented/frozen; real cohort collection and evaluation pending |
| v0.8 | Source-product catalog, latest reviewed quantities, search and freshness UI | Complete; one local demo shop, no live availability guarantee |

The next milestone is a supervised single-shop pilot measuring correction effort, staleness and gaps between visible observations and shop availability. Independent-scene collection/evaluation remains required for broader model claims. The claim "available nearby" requires actual participating-shop/location data; demo quantities must not be presented as live offers.

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

## Future preference/alternatives acceptance scenarios

- A known conflicting ingredient excludes a candidate, even if it is the closest or cheapest option.
- Missing or contradictory required ingredient data yields unknown and excludes the candidate from verified matches.
- With a hard INR 40 price limit, an INR 42 offer is excluded; without that cap, it may remain eligible.
- A matching product with stale availability is not counted in "2 alternatives available nearby."
- An unresolved pack/variant identity does not borrow attributes from another product of the same brand.
- A scan count is treated as an observation. V0.8 replaces only the explicitly reviewed product quantities; multi-shelf reconciliation and sales-adjusted stock remain future work.

These are future evaluation requirements, not implemented features or current safety guarantees.

## Current engineering commitment

The five-class experimentation phase remains closed; see [v0.1 results](reports/V0_1_RESULTS.md). V0.8 adds a small product layer while retaining `visible_items` semantics, immutable AI evidence and the frozen v0.7 protocol. No model tuning, verified SKU/ingredient enrichment, customer profiles, recommendations, marketplace orders or distributed infrastructure were added. Later capabilities need independently collected evidence and an explicit product requirement.
