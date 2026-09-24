# V1.0 — Basic order request flow

Completed 2026-09-24 against V0.9 commit `366aba5`.

## Delivered MVP

Customers search at `/customer`, select a shop observation, request a quantity and
receive **Pending shop confirmation**. The shopkeeper inbox at `/shopkeeper/orders`
supports explicit acceptance or rejection with an optional reason. Customers refresh
`/customer/orders` for status and history, and can cancel pending requests. Terminal
orders are read-only. Both roles visibly share **Demo Customer**, a local prototype
identity with no authentication or private customer details.

No payments, delivery, notifications, recommendation enhancements, new dependencies
or distributed infrastructure were added. Browser validation used synthetic observations
in a temporary database; no fabricated orders were seeded into the user's live data.

## Database and inventory semantics

Schema **4** adds `demo_customers`, `orders` and `order_items`. Product and shop name
snapshots make historical requests understandable after catalog changes. Unique request
IDs support creation retries; product-per-order uniqueness, quantity bounds, foreign
keys and status/timestamp checks constrain stored data.

Accepted order items are the reservation ledger. Pending, rejected and cancelled
orders reserve nothing. Available quantity is `max(0, reviewed count - accepted
reservations)`. The reviewed observation, scan evidence and original AI prediction
are never decremented or rewritten. New observations retain existing reservations;
a shortfall is flagged and displayed as zero unreserved units.

Acceptance takes the existing cooperative data lock and starts SQLite `BEGIN IMMEDIATE`
before checking all items. It requires shopkeeper confirmation, fresh reviewed inventory
and sufficient unreserved units. Changing status and creating the derived reservation
commit together. Failure returns 409 and leaves the request pending; exceptions roll
back the transaction. Concurrent writers can receive the existing 503 busy response.

## API and UI

- POST `/orders`: validate identities, inventory, 1–100 units per item, up to five unique
  products; create a pending request or return the same request on a safe retry.
- GET `/orders` and `/orders/{UUID}`: newest-first history/detail; status/shop filters,
  limit and offset pagination; UTC timestamps and product name snapshots.
- POST `/orders/{UUID}/accept`, `/reject`, `/cancel`: central state-transition rules;
  invalid transitions fail, and identical terminal retries cannot reserve twice.
- Inventory keeps its original observation `quantity` and adds reserved/available
  quantities and reservation shortfall. Fresh positive flags account for reservations,
  so the unchanged V0.9 matcher cannot promote a fully reserved product as positive.

Customer forms identify the selected shop, show observation/reservation distinctions,
and disable duplicate clicks. New order pages provide status labels, rejection reasons,
pending-only actions, timestamps and read-only history. Fresh counts are required for
requests; staleness is rechecked at acceptance. A request may exceed the current estimate,
but cannot be accepted until enough unreserved inventory is freshly reviewed.

## Validation results

| Check | Result |
| --- | --- |
| Complete suite | **164 tests passed**, final run **92.643 seconds** |
| New order tests | 16 passed; creation/idempotency, invalid inputs, lifecycle, stock, rollback, concurrency, history, APIs, backups and browser |
| Competing acceptance | Two independent stores/connections competed for two units; exactly one accepted, the other stayed pending; retry failed for insufficient stock |
| Atomic rollback | Injected failure after flush rolled back order status and reservation eligibility |
| Exact/insufficient/multi-item stock | Exact quantity succeeds; insufficient quantity or any failing item reserves nothing |
| Rescan/history | Later observations retain accepted reservations; renamed products preserve order snapshots |
| Backup compatibility | Schema-1/2/3 archives restore and migrate; schema-4 round trip preserves accepted/pending history, reservations and evidence |
| Browser smoke | Chromium, real local API, synthetic detector/counts; passed |
| Dependency consistency | `pip check`: no broken requirements |
| Frozen artifacts | **921 protected files**, frozen dataset hashes verified |
| Prior tracked artifacts | **183 files** byte-identical to `366aba5` |
| Model operations | No retraining, fine-tuning, threshold changes or protected test-set evaluation |

Final command:

```powershell
$env:STOREROOM_V10_SMOKE='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Evidence: [test log](v1_0_tests.log), [browser summary](v1_0_smoke.json),
[integrity manifest](v1_0_integrity.json). Screenshots remain ignored in `outputs/v10/`.
The tests use temporary stores; private photos, databases and customer data are excluded
from the commit. Existing historical reports and frozen field-validation artifacts
were not rewritten. Previous schema fixture tests were updated only for the additive
tables and new current version.

### Browser outcomes

1. Search Red Bull, select Demo Shop, request 2 out of a reviewed 5; see pending.
2. Shopkeeper sees pending by default, confirms availability and accepts.
3. Customer refresh shows accepted; product page shows **3 unreserved / 2 reserved**.
4. A second request is rejected with “Currently unavailable”; customer sees the reason.
5. Request 4 when only 3 remain. Acceptance fails visibly; request stays pending and
   availability remains 3.
6. Customer cancels that pending request. Accepted/rejected/cancelled history remains.
7. Shopkeeper switches from pending to all history and sees all three requests.

No JavaScript errors occurred. Mobile 390px and desktop 1280px screenshots were
visually reviewed; mobile history has no horizontal overflow. Review caught a malformed
status option; it was corrected and the browser test now explicitly checks the default
pending filter and completed requests leaving that view. The final complete suite passed
after this correction.

## Protected scope

The prior artifact comparison includes configs, historical reports/docs, inference
sources, field-validation sources/tests, scan storage/review/evidence, shopkeeper scan
HTML/JavaScript and the V0.9 matching module. Model checkpoint SHA-256 remains:

`099b96ecd3cb440991b56c69cd243770ca499b8e246fee994ced3e24b93ec1c4`

Frozen V0.7 protocol SHA-256 remains:

`4d59789dbc368ac7a9b73f58556108c567a8a87eedbbd40b2bf685029953083d`

## Limitations and stopping point

This is a local, shared-identity demo, not an authenticated multi-customer marketplace.
Only five source products and the demo shop exist. Counts describe visible packages,
not sales-adjusted real-time stock. Accepted reservations remain active indefinitely;
there is no fulfillment/release or accepted-order cancellation, and subsequent reviewed
counts must include packages still held for those requests. Operational reconciliation
needs a deliberate future design. UI status refresh is manual; there are no notifications.
Independent model generalization remains unverified.

**Stop here and review the complete MVP with the user before choosing additional
features.** No next marketplace feature was implemented or scheduled.

See [order-flow guide](../docs/V1_0_ORDER_FLOW.md) for startup, contracts and semantics.
