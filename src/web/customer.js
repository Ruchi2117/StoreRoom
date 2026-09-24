"use strict";
const el = id => document.getElementById(id);
let searchVersion = 0, detailVersion = 0, selected = null;
function node(tag, className, text) {
  const result = document.createElement(tag);
  if (className) result.className = className;
  if (text !== undefined) result.textContent = text;
  return result;
}
function showError(message="") {
  el("customer-error").textContent = message;
  el("customer-error").hidden = !message;
}
async function getJSON(url) {
  const response = await fetch(url, {cache:"no-store"});
  if (!response.ok) throw new Error("Couldn’t load product counts. Check the local server and try again.");
  return response.json();
}
async function search(event) {
  event?.preventDefault();
  const version = ++searchVersion;
  ++detailVersion; selected = null;
  el("product-detail").hidden = true;
  el("product-results").replaceChildren();
  el("search-status").textContent = "Finding products…";
  showError();
  try {
    const data = await getJSON("/products/search?q="+encodeURIComponent(el("query").value));
    if (version !== searchVersion) return;
    el("search-status").textContent = data.products.length ? `${data.products.length} matching products · Select one to see shop counts.` : "No matching supported products.";
    for (const [index, product] of data.products.entries()) {
      const button = node("button", "card product-choice"); button.type = "button";
      button.dataset.productId = product.product_id; button.setAttribute("aria-pressed", "false");
      button.append(node("span", "product-number", String(index+1).padStart(2,"0")), node("strong", "", product.name),
        node("span", "", product.brand || "Brand unknown"), node("span", "", "View shop counts →"));
      button.addEventListener("click", () => openProduct(product.product_id, true));
      el("product-results").append(button);
    }
  } catch (error) {
    if (version === searchVersion) { el("search-status").textContent = "Search unavailable."; showError(error.message); }
  }
}
async function openProduct(id, focus=false) {
  selected = id;
  const version = ++detailVersion;
  showError();
  // Remove old quantities immediately; failed refresh must not look current.
  el("inventory-results").replaceChildren(node("p", "muted", "Loading latest counts…"));
  el("product-detail").hidden = false;
  el("refresh-inventory").disabled = true;
  try {
    const data = await getJSON("/inventory/"+encodeURIComponent(id));
    if (version !== detailVersion) return;
    el("detail-title").textContent = data.product.name;
    el("product-meta").textContent = `${data.product.brand || "Brand unknown"} · Pack size ${data.product.package_size || "not verified"}`;
    el("inventory-results").replaceChildren();
    document.querySelectorAll(".product-choice").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.productId === id)));
    if (!data.inventory.length) el("inventory-results").append(node("p", "notice", "No confirmed count recorded for this product. Availability is unknown."));
    for (const item of data.inventory) {
      const row = node("article", "inventory-row"); row.dataset.freshness = item.freshness;
      row.append(node("h3", "", item.shop_name+(item.shop_is_demo ? " · local demo" : "")));
      let label = item.is_demo ? "Demo quantities — examples only" : item.freshness === "STALE" ? "Stale inventory — please recheck" :
        item.quantity > 0 ? "Recently confirmed — check with the shop" : "Zero visible units last confirmed";
      row.append(node("span", "status-badge "+(item.is_demo ? "demo" : item.freshness.toLowerCase()), label));
      const quantity = node("p", "quantity", String(item.quantity)+" ");
      quantity.append(node("small", "", item.is_demo ? "example units" : "visible units confirmed")); row.append(quantity);
      const time = node("time", "", item.last_confirmed_at ? "Last confirmed: "+new Date(item.last_confirmed_at).toLocaleString() : "Not confirmed — seeded demonstration data");
      if (item.last_confirmed_at) time.dateTime = item.last_confirmed_at;
      row.append(time);
      row.append(node("p", "muted", item.is_demo ? "Not observed shop stock." : `Freshness window: ${item.freshness_seconds} seconds. Current availability is not guaranteed.`));
      el("inventory-results").append(row);
    }
    if (focus) el("detail-title").focus();
  } catch (error) {
    if (version === detailVersion) { el("inventory-results").replaceChildren(); showError(error.message); }
  } finally {
    if (version === detailVersion) el("refresh-inventory").disabled = false;
  }
}
el("search-form").addEventListener("submit", search);
el("refresh-inventory").addEventListener("click", () => selected && openProduct(selected));
setInterval(() => { if (selected && !document.hidden) openProduct(selected); }, 30000);
search();
