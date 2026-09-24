# V1.0 — Basic order request flow

StoreRoom now supports discovery → order request → explicit shopkeeper acceptance
or rejection → customer status/history. This is a **local commerce prototype** with
a shared demo identity. It does not process payment, arrange delivery, or prove
physical real-time stock. No model or inference changes are involved.

## Start and use

Use the existing environment and database:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

1. At `/`, upload a shelf photo and review/confirm its counts using the existing
   shopkeeper workflow. Confirmed observations are required for requests; seeded
   V0.8 demonstration quantities do not qualify.
2. At `/customer`, search for a supported product and choose it. Each eligible shop
   observation shows confirmed, reserved and unreserved quantities, plus a quantity
   input and **Request order from [shop]** button. This button selects the shop.
3. Request 1–100 units. The success message says **Pending shop confirmation** and
   links to `/customer/orders`. Nothing is reserved at this point.
4. Open `/shopkeeper/orders`. It defaults to pending requests. Check actual stock,
   tick **I checked current availability**, then accept; or enter an optional reason
   and reject. If the count has gone stale, use **Re-scan shelf** and review it first.
5. Refresh `/customer/orders` to see the decision. Customers may cancel only pending
   requests. Both pages expose all-history/status filters and older/newer pagination.

The order pages refresh manually, preserving typed rejection reasons and confirmation
checkboxes. Product counts retain the existing 30-second refresh when visible, except
while the quantity form has focus or is submitting. API validation always rechecks
the database, even if the displayed count has aged.

## Identity and shop boundaries

There is one persisted identity, `demo_customer`, named **Demo Customer**. No names,
phone numbers, addresses or accounts are collected. Every browser on this server
shares this identity and can see and operate the same orders. This is **not production
authentication or authorization**. The page labels this explicitly. Keep the app on
localhost; do not expose the prototype as a multi-customer service.

The existing catalog seeds only `local_demo_shop` / **Demo Shop**. Neither UI activity
nor synthetic browser fixtures are evidence of real customer commerce. APIs support
shop IDs and filtering, but there is no shop login, registration or location routing.

## State machine and retry behavior

| Current state | Allowed new state | Effect |
| --- | --- | --- |
| PENDING | ACCEPTED | Atomically reserve all requested items after availability checks |
| PENDING | REJECTED | Save optional reason; no reservation |
| PENDING | CANCELLED | Save cancellation time; no reservation |
| ACCEPTED / REJECTED / CANCELLED | None | Historical terminal state is read-only |

Repeating the same terminal action is an idempotent read of the result. It cannot
reserve twice; changing a completed rejection reason returns 409. Moving between
different terminal states also returns 409. There is no accepted-order cancellation,
fulfillment, reservation release, expiry, quantity edit or refund in V1.0.

Creation requires a UUID `request_id`. Retrying the same ID/shop/items returns the
existing request, including after it reaches a terminal state. Reusing an ID for a
different shop or quantities returns 409. The browser reuses its form's request ID
on retry. It does not persist that key across page reloads: after an ambiguous network
failure, check history before submitting a fresh form. Disabling the submit button
also prevents repeated clicks while a request is in flight.

## Observations, reservations and available quantities

The original `shop_inventory.quantity` and `source_scan_id` remain the latest reviewed
visible shelf observation and its immutable evidence. Acceptance does **not** rewrite
that row or its scan. Accepted `order_items.quantity` values form the reservation ledger:

```text
reserved_quantity = sum(items in ACCEPTED orders for this shop and product)
available_quantity = max(0, observed quantity - reserved_quantity)
reservation_shortfall = max(0, reserved quantity - observed quantity)
```

Examples:

- Reviewed 5, requested 2 pending: observed 5, reserved 0, available 5.
- Shop accepts 2: observed 5, reserved 2, available 3.
- Shop rejects another request: those figures do not change.
- A new shelf review records 4: reservations stay 2, available becomes 2.
- A new review records 1: reservations stay 2, available becomes 0, shortfall is 1.

Refreshing the shelf never silently cancels commitments. The UI flags a reservation
shortfall. **Reviewed counts must include packages still held for accepted requests.**
Because no fulfillment/reconciliation lifecycle exists yet, reserved quantities remain
active indefinitely; do not use the prototype as an operational sales ledger after
products leave the shelf. This conservative limitation avoids restoring sold/reserved
units merely by resetting an observation. Hidden stock, other shelves and offline
sales remain unknown.

Inventory JSON preserves `quantity` as the observation and adds `reserved_quantity`,
`available_quantity`, `reservation_shortfall` and `availability_meaning`. A fresh positive
availability flag now requires a positive **unreserved** quantity. V0.9 relationships,
preference logic and deterministic ordering are unchanged; their inventory flags
naturally stop promoting fully reserved products. With no orders, prior behavior is
unchanged. Demo/stale quantities retain their explicit labels and are never guaranteed.

## Validation and acceptance transaction

Creation validates the shop/product identities, an inventory record, positive integer
quantities (maximum 100 per product), 1–5 unique products, and a fresh non-seeded
observation with at least one unreserved unit. This prevents requests against clearly
unavailable, demo-only or stale observations. The requested quantity may exceed the
current estimate: it is intent, not a reservation, and the UI explains this.

Acceptance requires explicit shopkeeper confirmation, then independently rechecks
freshness and sufficient unreserved quantity **for every item**. Missing, future-dated,
stale or seeded observations cannot pass. The same V0.8 freshness window is used
(`INVENTORY_FRESHNESS_SECONDS`, default 3600). On insufficient stock or staleness:
return **409**, leave the order **PENDING**, and change no reservation. The shop may
review a fresh count and retry, or explicitly reject.

All order writes share the existing cooperative data lock with scans/backups and use
a SQLAlchemy transaction with SQLite **BEGIN IMMEDIATE** before reads. The write lock
covers reading observations/reservations, checking all items and changing order status.
Status is the source of reservation eligibility, so it cannot commit separately from
the reservation. Exceptions roll back the transaction. Two processes cannot both read
the same unreserved units and commit competing acceptances. A competing cooperative
writer/backup may return the existing 503 busy response; refresh/retry after it finishes.
This is local SQLite coordination, not distributed locking.

## API

Every order response uses `Cache-Control: no-store`. Errors use the existing JSON
`detail` convention. No internal SQL or database paths are exposed.

| Method/path | Request and behavior |
| --- | --- |
| POST `/orders` | Create pending request or return idempotent prior result (200) |
| GET `/orders` | Shared-demo history, newest first; optional shop_id, status, limit 1–100 (default 50), offset >= 0 |
| GET `/orders/{UUID}` | Order detail with snapshot names, quantities, status and UTC timestamps |
| POST `/orders/{UUID}/accept` | `{"availability_confirmed":true}`; check and reserve atomically |
| POST `/orders/{UUID}/reject` | `{"reason":"Currently unavailable"}` or `{}`; maximum 200 characters |
| POST `/orders/{UUID}/cancel` | Cancel pending request; no payload required |

The `/customer/orders` and `/shopkeeper/orders` routes are HTML pages; they use the
same `/orders` JSON endpoints. Malformed fields return 422, missing identities return
404, and stock/transition conflicts return 409.

Example creation body (generate a new UUID once per intentional request):

```json
{
  "request_id": "a710a12a-45d6-4814-b9e7-d329a1f91d64",
  "shop_id": "local_demo_shop",
  "items": [{"product_id":"hs_redbull_regular","quantity":2}]
}
```

The API supports up to five different items from one shop atomically; the deliberately
small customer UI submits one product at a time. There is no cart or payment checkout.

## Persistence and backups

Schema **4** adds `demo_customers`, `orders` and `order_items`. Orders store IDs, state,
creation/update/terminal timestamps, optional rejection reason and shop name snapshot.
Items store product ID, product name snapshot and quantity. Foreign keys, unique
request IDs/product-per-order, positive bounded quantities and status/timestamp checks
protect the records. Product names remain understandable if the catalog is renamed.
There is no order delete/edit API.

No previous scan/catalog column is rebuilt. Backup format remains 1 and now accepts
schemas **1–4** with version-specific table validation. Orders and accepted reservations
are part of the same SQLite snapshot; they require no separate reservation file.
Older backups migrate additively on startup and introduce no historical orders.
As before, stop the app for restore and keep the retained rollback copies until checked.
Older app versions cannot open schema 4; keep an older snapshot before downgrading.

## Verification and stopping point

```powershell
$env:STOREROOM_V10_SMOKE='1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The optional flag records a browser-smoke summary and ignored screenshots. Fixtures
use temporary synthetic reviewed counts, not private customer data or new model runs.
Tests cover creation, state transitions, exact/insufficient counts, simultaneous
acceptance through separate connections, rollback, rescan semantics, history snapshots,
API validation, browser accept/reject/cancel and schema-1/2/3/4 backup compatibility.

After V1.0, review the entire MVP with the user before choosing another feature.
No payments, delivery, notifications, new recommendation intelligence or infrastructure
are scheduled by this milestone. Field generalization of the provisional model remains
unverified and the independent validation workflow remains frozen.
