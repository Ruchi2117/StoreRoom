# A five-minute StoreRoom walkthrough

Use the artifact-complete checkout and `powershell -NoProfile -File scripts/run_demo.ps1`. The app runs at `http://127.0.0.1:8001`, with separate ignored data under `outputs/portfolio-demo/`. It creates the existing labelled demo alternative relationships, not invented confirmed stock or model predictions. No account or secret is required. Startup initializes the database; wait for Uvicorn's startup-complete message.

## Demonstrate the product

1. Open `/static/overview.html` for the product and architecture overview.
2. Open **Scan inventory** (`/`). Choose `docs/demo/shelf.jpg`, an attributed public validation photo. Click **Analyse shelf photo**. The real frozen CPU model runs.
3. Review the photo. **AI detected** stays separate from **Your count**. To demonstrate editing without claiming new ground truth, decrease Red Bull once, then increase it back before confirming. Check the other visible products and click **Confirm Inventory**.
4. Open **Scan History** and the saved scan: original photo, boxes and reviewed counts persist independently.
5. Open **Discover** (`/customer`), search **Red Bull**, select it, and inspect Demo Shop's timestamp and unreserved units. Request **2** if at least two reviewed units are present.
6. Open **Shopkeeper orders**, find that pending request, check **I checked current availability**, and accept. Return to **Customer orders** and refresh to see accepted status.
7. In discovery, refresh Red Bull. The original observation remains the same; accepted reservations reduce unreserved quantity by two.
8. Request **1** more, then reject it in the inbox with **Demo walkthrough: customer requested a different product.** Refresh customer orders and inspect the reason. Rejection does not reserve stock.
9. Request **1** again and leave it pending. The scenario now contains accepted, rejected and pending requests. These are actual local workflow actions, not real commercial orders.
10. For alternatives, request and accept the one reviewed **Valser Classic**, then refresh its counts. With that unit reserved, the existing demo relationship exposes Valser Still with honest availability/metadata labels. This adds a second accepted demonstration order. Alternatively, view the relationship before the first scan or after inventory is stale. Unknown metadata excludes restrictive matches.

Freshness expires after one hour. Re-scan/review when needed; do not change the threshold or timestamp to make a screenshot look current. On a repeat walkthrough, old reservations persist. Start with a new isolated database/scan directory if there are insufficient units; do not erase existing data or manufacture higher counts. UUIDs and timestamps vary; the sequence is deterministic on empty demo storage, but it is not a fixed database dump.

## Recovery demonstration

In a second terminal, back up the running portfolio data:

```powershell
.\.venv\Scripts\python.exe -m src.data_cli backup --database outputs/portfolio-demo/storeroom.db --scans outputs/portfolio-demo/scans --output outputs/portfolio-backups
```

Use the exact archive path printed above in place of `<archive.zip>`:

```powershell
.\.venv\Scripts\python.exe -m src.data_cli validate <archive.zip>
.\.venv\Scripts\python.exe -m src.data_cli restore <archive.zip> --database outputs/portfolio-restored/storeroom.db --scans outputs/portfolio-restored/scans
```

Restore into these separate locations with no app using them. It does not replace the running demo. See [backup/restore](V0_6_BACKUP_RESTORE.md) for locks, rollback and replacement precautions. Model weights are managed separately.

## Screenshots and limitations

The curated captures under `src/web/screenshots/` are from the actual app. See [photo attribution](demo/ATTRIBUTION.md). There are no generated detection images, fake success metrics, private photos, customer identities or database dumps in the screenshot set. All shops/orders are explicitly local demonstration activity. The five source classes are not verified Indian SKU coverage.
