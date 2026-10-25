# Portfolio presentation results

Completed: 2026-10-26. This is a presentation pass, not a new product or model milestone.

## Changes

- Rewrote the README around the product, actual screenshots, a short walkthrough, the implemented stack, engineering tradeoffs and explicit limitations.
- Added a compact overview at `/static/overview.html`; kept `/` as the existing scan workspace so existing links continue working.
- Unified navigation and visual styling across scan/review, discovery and order pages. Added clear prototype scope and order-state styling. Human corrections remain separate from predictions.
- Added `docs/ARCHITECTURE.md` and `docs/ENGINEERING_DECISIONS.md`, describing the existing vanilla JavaScript, FastAPI, SQLAlchemy/SQLite and local-evidence architecture.
- Added `scripts/run_demo.ps1` and `docs/PORTFOLIO_DEMO.md` for isolated demo storage, real inference and repeatable manual orders. No new infrastructure or business behavior was introduced.

## Run the demo

From an already configured, artifact-complete checkout:

```powershell
powershell -NoProfile -File scripts/run_demo.ps1
```

One server serves backend and frontend on port 8001:

- Overview: http://127.0.0.1:8001/static/overview.html
- Scan/history: http://127.0.0.1:8001/
- Discovery/inventory: http://127.0.0.1:8001/customer
- Customer orders: http://127.0.0.1:8001/customer/orders
- Shopkeeper inbox: http://127.0.0.1:8001/shopkeeper/orders

The script uses `outputs/portfolio-demo/` and seeds only the existing labelled alternative relationships. Confirmed quantities come from the real scan/review workflow. See the README for dependency installation and checkpoint restoration. No secrets or separate frontend server are required.

## Browser evidence

The complete manual flow and desktop captures were performed on 2026-09-27 during this presentation pass. On 2026-10-26 the application was restarted, the persisted UI was checked, mobile routes were inspected, and the full tests and restore checks were rerun. The older inventory now correctly appears stale; it was not backdated to make the demo look fresh. Scan and confirm again before new acceptances.

The real frozen model processed the attributed public validation photo in `docs/demo/shelf.jpg`. It predicted Red Bull 4, Valser Classic 1 and Valser Still 1 (the other two classes zero). Review controls were exercised by decreasing and restoring Red Bull before confirmation. These are demonstration predictions, not verified ground truth or new accuracy results.

Verified through the browser:

1. Upload, inference, count controls, confirmation and reopening persisted scan evidence.
2. Red Bull search, quantity 2 request, PENDING state and shopkeeper acceptance.
3. Customer ACCEPTED state, with 4 observed, 2 reserved and 2 unreserved Red Bull units.
4. A second Red Bull request rejected with the visible reason: “Demo walkthrough: customer requested a different product.” Reservations remained unchanged.
5. Valser Classic acceptance reserved its one unit. The explicitly seeded Valser Still alternative appeared; a vegan preference excluded unknown metadata rather than claiming suitability.
6. Another Red Bull request remained pending for the inbox demonstration.

The isolated demo contains one scan and four real UI-created demo orders: two ACCEPTED, one REJECTED and one PENDING. These are not actual customer or business results.

Responsive checks at 390px covered overview, scan, discovery, customer orders and shopkeeper orders. All had document width 375px within the 390px viewport (no horizontal overflow). Desktop overview at 1280px had no broken images or captured console errors. The viewport was reset afterward.

## Screenshot set

Actual application captures in `src/web/screenshots/`:

| File | View |
|---|---|
| `00-scan.png` | Upload workspace |
| `01-overview.png` | Portfolio overview |
| `02-review.png` | Real model boxes and editable human counts |
| `03-confirmed.png` | Confirmed observation |
| `04-discovery.png` | Product search and recorded inventory |
| `05-alternatives.png` | Explicit demo alternative |
| `06-request.png` | Order request |
| `07-inbox.png` | Shopkeeper pending request |
| `08-accepted.png` | Customer accepted order |
| `09-rejected.png` | Rejection and reason |
| `10-mobile-overview.png` | 390px overview, captured 2026-10-26 |

Desktop captures date from 2026-09-27. Screenshots were not retouched. The sample is an unchanged copy of `IMG_20181218_170247.jpg` from the existing validation split, not protected test data or a private field photo. Dataset attribution and license accompany it in `docs/demo/ATTRIBUTION.md`.

## Verification

| Check | Result |
|---|---|
| Complete existing test suite | **164 passed**, 106.466 seconds, 2026-10-26 |
| JavaScript syntax | `node --check` passed for app, customer and orders scripts |
| Backend syntax | `python -m compileall -q src` passed |
| Frontend build | Not applicable: static HTML/CSS/JavaScript, no build configuration |
| Manual browser flows | Scan/review/inventory/discovery/alternatives/accept/reject passed as detailed above |
| Backup and restore | Existing CLI restored isolated demo; all 11 database tables matched source rows and referenced image bytes matched |
| Frozen artifacts | 921 protected snapshot files verified; dataset hashes and checkpoints unchanged |
| Historical source/configuration/tests/reports/docs | 262 protected prior files compared byte-for-byte with pre-pass commit `bf3aaf3` |
| Demo photo | Byte-identical to its attributed validation source |
| Retraining / protected test-set inference | Neither performed |

Integrity details are saved in [portfolio_integrity.json](portfolio_integrity.json). Test/runtime/backup logs and local databases remain under ignored `outputs/`. Recovery used a separate destination and did not replace the running demo. The V0.7 field protocol and all historical experiment results remain unchanged.

## Repository hygiene and limitations

Only source presentation files, documentation, the attributed public sample and curated screenshots are included. No local database, backup, checkpoint, environment, secret or private field-validation photo is included. Existing ignore rules already cover these artifacts. Meaningful experiment history was retained.

The GitHub repository description was checked and is unset; it was not changed. The README now supplies the product description prominently.

The model still recognizes five source classes. Independent field generalization and expanded Indian retail recognition are unverified. No model, threshold, evaluator or dataset was changed. Historical metrics are labelled as validation evidence, not production outcomes.

A fresh clone does not contain the frozen checkpoint; it must be restored from preserved artifacts. The app remains a local prototype with a shared customer identity, one demo shop, no authentication, payments or delivery, and no fulfillment/release workflow for accepted reservations. These limitations are visible in the UI and README.
