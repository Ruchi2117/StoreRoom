# Engineering decisions

These describe implemented behavior, including its limits. They are interview discussion points, not claims of production scale.

## AI output is not ground truth

The inference service stores a prediction and returns a prediction ID. Confirmation validates the review against that original evidence. Corrections change reviewed quantities, not the original detections or annotated image. History can show both. This makes mistakes inspectable and prevents a correction from being misrepresented as a better model result. See `src/evidence.py`, `src/storage.py` and the evidence tests.

## Observations become stale

Inventory records retain source scan and confirmation time. Freshness is computed against a configured window (default one hour). Seeded examples, unknown counts and stale observations remain distinct; they are not labelled live stock. Customer refresh clears old detail before fetching a replacement. Order creation and acceptance independently recheck freshness on the server, so a previously open browser cannot authorize stale acceptance.

## Two requests can compete for the same inventory

Pending requests express intent. On acceptance, `src/orders.py` begins a SQLite `BEGIN IMMEDIATE` write transaction before reading quantities and reservations. All items must pass the freshness and stock checks; otherwise the whole transaction fails. Accepted order items become reservations. A unique request ID makes creation retries safe; repeated terminal transitions cannot reserve twice. The suite tests competing connections, insufficient stock and rollback.

This is a single-machine design. It has no fulfillment/release workflow and does not reconcile POS sales. It should not be used as an operational stock ledger without that work.

## Product identity should outlast a model

Catalog records use stable product IDs, separate from numeric YOLO class IDs. The current catalog still enforces five mapped classes; it is not yet an arbitrary-SKU recognition system. Unknown pack sizes stay unknown. The V1.1 design proposes a broader identity hierarchy, but its implementation is blocked on data verification. See [V1.1 audit](../reports/V1_1_DATASET_AUDIT.md).

## Recommendation evidence can be incomplete

Alternatives use explicit relationships, not generated product claims. The opt-in demo contains a Valser variant pair, clearly labelled as a demonstration relationship. Restrictions require explicit supporting metadata; unknown ingredients cannot become a positive dietary match. Preferences are transient request data. The system does not declare medical suitability.

## A database backup alone loses image evidence

The local backup CLI packages a consistent SQLite snapshot and its referenced original/annotated images with checksums. Restore validates archive paths, hashes, database schema and references before replacing the data pair. Cooperative locks prevent conflicting operations. Previous data is retained for rollback; power loss across two filesystem replacements remains a documented limitation. Backup does not include model weights or training data.

## Evaluation can look better through leakage

The dataset/splits/model and field protocol are frozen. The later model results describe the existing validation cohort, not independent Indian field performance. The independent-scene audit found no eligible unused verified groups, so evaluation stopped rather than fabricating independence. V0.7 provides collection/evaluation tooling but no field accuracy result. This presentation pass performs a UI demonstration on one existing validation image, not another model benchmark.

## Keep infrastructure proportional

FastAPI serves static HTML/CSS/JavaScript and JSON from one process; SQLAlchemy provides local SQLite persistence. A separate React build, Docker deployment, Redis or queue would not improve this presentation task. The tradeoff is a deliberately local, unauthenticated single-shop prototype. Dependencies and artifact restoration remain explicit in the README.
