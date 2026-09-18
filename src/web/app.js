/* The browser only reviews API results; it never implements inference. */
"use strict";
const $ = id => document.getElementById(id);
let file = null, previewURL = null, prediction = null, items = [], confirmed = null;
let generation = 0, request = null, busy = false;

function error(message = "") {
  $("error").textContent = message;
  $("error").hidden = !message;
}
function screen(name) {
  for (const key of ["scan", "review", "confirmed", "history", "saved-scan"]) {
    $(key).hidden = key !== name;
    $("step-" + key)?.removeAttribute("aria-current");
  }
  $("step-" + name)?.setAttribute("aria-current", "step");
  document.querySelector(".steps").hidden = ["history", "saved-scan"].includes(name);
  $(name + "-title").focus();
}
function setBusy(value, stage) {
  busy = value;
  $("file").disabled = value;
  $("analyse").disabled = value || !file;
  $("loading").hidden = !(value && stage === "scan");
  $("cancel").hidden = !(value && stage === "scan");
  $("confirming").hidden = !(value && stage === "review");
  $("confirm").disabled = value;
  document.querySelectorAll(".browse-history, #refresh-history").forEach(button => { button.disabled = value; });
  $("upload-form").setAttribute("aria-busy", String(value && stage === "scan"));
  $("review").setAttribute("aria-busy", String(value && stage === "review"));
  for (const control of document.querySelectorAll("#products button, #products input, #missed-products button")) {
    control.disabled = value || (control.dataset.direction === "-1" && Number(control.dataset.count) === 0);
  }
}
function reset() {
  generation++;
  request?.abort(); request = null;
  if (previewURL) URL.revokeObjectURL(previewURL);
  file = previewURL = prediction = confirmed = null; items = [];
  $("file").value = ""; $("filename").textContent = "";
  $("preview").removeAttribute("src"); $("preview").hidden = true;
  $("annotated").removeAttribute("src");
  $("products").replaceChildren(); $("confirmed-items").replaceChildren();
  $("missed-products").replaceChildren(); $("missed").open = false;
  $("review-total").textContent = "0";
  $("history-list").replaceChildren(); $("saved-items").replaceChildren();
  $("history-loading").hidden = true; $("saved-loading").hidden = true;
  error(); setBusy(false); screen("scan");
}
$("file").addEventListener("change", () => {
  error();
  if (previewURL) URL.revokeObjectURL(previewURL);
  previewURL = null; file = $("file").files[0] || null;
  $("preview").hidden = true; $("preview").removeAttribute("src");
  $("filename").textContent = file?.name || "";
  if (file && file.size > 20 * 1024 * 1024) {
    file = null; error("That photo is too large. Choose a JPG or PNG under 20 MB.");
  }
  if (file) {
    previewURL = URL.createObjectURL(file);
    $("preview").src = previewURL; $("preview").hidden = false;
  }
  setBusy(false);
});
$("preview").addEventListener("error", () => { $("preview").hidden = true; });
$("annotated").addEventListener("error", () => {
  if (!prediction) return;
  $("image-note").textContent = "Annotated photo unavailable. Showing your original photo; counts are still available.";
  if ($("annotated").getAttribute("src") !== previewURL) $("annotated").src = previewURL;
});

async function responseJSON(response, fallback) {
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : fallback);
  if (!data) throw new Error(fallback);
  return data;
}
$("upload-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (!file || busy) return;
  const current = ++generation;
  request = new AbortController(); error(); setBusy(true, "scan");
  try {
    const body = new FormData(); body.append("file", file);
    const response = await fetch("/predict?annotate=true", {method: "POST", body, signal: request.signal});
    const result = await responseJSON(response, "We couldn’t analyse this photo. Try again or choose another photo.");
    if (current !== generation) return;
    prediction = result; // Never mutate the original prediction or its counts.
    items = result.products.filter(p => p.count > 0).map(reviewItem);
    $("annotated").src = result.annotated_image || previewURL;
    $("image-note").textContent = result.annotated_image
      ? "AI detections · boxes stay unchanged when you edit counts."
      : "Original photo · annotated photo unavailable.";
    $("ai-total").textContent = `AI detected ${result.total_count}`;
    $("empty").hidden = result.total_count !== 0;
    renderItems(); screen("review");
  } catch (e) {
    if (current === generation && e.name !== "AbortError") error(e instanceof TypeError
      ? "Couldn’t reach StoreRoom. Check the local server and try again." : e.message);
  } finally {
    if (current === generation) { request = null; setBusy(false); }
  }
});
function reviewItem(product) {
  return {class_id: product.class_id, class_name: product.class_name,
    predicted_count: product.count, confirmed_count: product.count};
}
function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function updateTotal() {
  $("review-total").textContent = items.reduce((sum, item) => sum + item.confirmed_count, 0);
}
function renderItems() {
  $("products").replaceChildren();
  for (const item of items) {
    const row = node("div", "product-row"); row.dataset.classId = item.class_id;
    const info = node("div");
    info.append(node("h3", "", item.class_name), node("p", "prediction", `AI detected ${item.predicted_count}`));
    const controls = node("div"), counter = node("div", "counter");
    const label = node("label", "count-label", "Your count"); label.htmlFor = `count-${item.class_id}`;
    const input = node("input"); input.type = "number"; input.min = "0"; input.step = "1";
    input.max = String(Number.MAX_SAFE_INTEGER); input.inputMode = "numeric";
    input.id = label.htmlFor; input.value = item.confirmed_count;
    input.setAttribute("aria-label", `${item.class_name} confirmed count`);
    const buttons = [-1, 1].map(direction => {
      const button = node("button", "", direction < 0 ? "−" : "+"); button.type = "button";
      button.dataset.direction = direction; button.dataset.count = item.confirmed_count;
      button.setAttribute("aria-label", `${direction < 0 ? "Decrease" : "Increase"} ${item.class_name}`);
      button.disabled = direction < 0 && item.confirmed_count === 0;
      button.addEventListener("click", () => {
        if (busy) return;
        const value = item.confirmed_count + direction;
        if (Number.isSafeInteger(value) && value >= 0) changeCount(value);
      });
      return button;
    });
    function changeCount(value) {
      item.confirmed_count = value; input.value = value; error();
      buttons[0].disabled = value === 0;
      buttons.forEach(button => { button.dataset.count = value; });
      updateTotal();
    }
    input.addEventListener("change", () => {
      const value = Number(input.value);
      if (busy || input.value.trim() === "" || !Number.isSafeInteger(value) || value < 0) {
        input.value = item.confirmed_count;
        if (!busy) error("Use a whole number of zero or more for each count.");
      } else changeCount(value);
    });
    counter.append(buttons[0], input, buttons[1]); controls.append(label, counter);
    row.append(info, controls); $("products").append(row);
  }
  const missing = prediction.products.filter(product => !items.some(item => item.class_id === product.class_id));
  $("missed").hidden = !missing.length;
  $("missed-products").replaceChildren();
  for (const product of missing) {
    const add = node("button", "", `+ ${product.class_name}`); add.type = "button";
    add.addEventListener("click", () => {
      if (busy) return;
      items.push(reviewItem(product)); renderItems();
      $(`count-${product.class_id}`).focus();
    });
    $("missed-products").append(add);
  }
  updateTotal();
}
$("confirm").addEventListener("click", async () => {
  if (busy || !prediction) return;
  const current = ++generation;
  request = new AbortController(); error(); setBusy(true, "review");
  try {
    const response = await fetch("/inventory/confirm", {method: "POST", signal: request.signal,
      headers: {"Content-Type": "application/json"}, body: JSON.stringify({items})});
    const result = await responseJSON(response, "Couldn’t confirm these counts. Please check them and try again.");
    if (current !== generation) return;
    confirmed = result;
    renderReceipt(confirmed, "confirmed-items");
    $("confirmed-total").textContent = `${confirmed.items.reduce((sum, item) => sum + item.confirmed_count, 0)} packages`;
    $("confirmed-time").textContent = `Reviewed ${new Date(confirmed.confirmed_at).toLocaleString()}`;
    screen("confirmed");
  } catch (e) {
    if (current === generation && e.name !== "AbortError") error(e instanceof TypeError
      ? "Couldn’t verify the save. Your edits are still here. Check Scan History before confirming again." : e.message);
  } finally {
    if (current === generation) { request = null; setBusy(false); }
  }
});
$("cancel").addEventListener("click", reset);
document.querySelectorAll(".new-scan").forEach(button => button.addEventListener("click", reset));

function renderReceipt(result, target) {
  $(target).replaceChildren();
  for (const item of result.items) {
    const row = node("div", "receipt-row"), info = node("div");
    info.append(node("b", "", item.class_name), node("p", "", `AI detected ${item.predicted_count} → You confirmed ${item.confirmed_count}`));
    row.append(info, node("strong", "", String(item.confirmed_count))); $(target).append(row);
  }
  if (!result.items.length) $(target).append(node("p", "", "No supported products confirmed in this photo."));
}
async function openHistory() {
  const current = ++generation;
  request?.abort(); request = new AbortController();
  error(); screen("history"); setBusy(true, "history");
  $("history-loading").hidden = false; $("history-empty").hidden = true;
  $("history-list").replaceChildren();
  try {
    const response = await fetch("/inventory/scans?limit=20", {signal: request.signal, cache: "no-store"});
    const data = await responseJSON(response, "Couldn’t load saved scans. Try refreshing history.");
    if (current !== generation) return;
    $("history-empty").hidden = data.scans.length !== 0;
    for (const scan of data.scans) {
      const row = node("div", "history-row"), info = node("div");
      info.append(node("b", "", new Date(scan.created_at).toLocaleString()),
        node("p", "muted", `${scan.item_count} product ${scan.item_count === 1 ? "class" : "classes"}`));
      const open = node("button", "secondary", "Open scan"); open.type = "button";
      open.addEventListener("click", () => openSaved(scan.scan_id));
      row.append(info, open); row.dataset.scanId = scan.scan_id; $("history-list").append(row);
    }
  } catch (e) {
    if (current === generation && e.name !== "AbortError") error("Couldn’t load saved scans. Check the local server, then refresh history.");
  } finally {
    if (current === generation) { request = null; $("history-loading").hidden = true; setBusy(false); }
  }
}
async function openSaved(id) {
  const current = ++generation;
  request?.abort(); request = new AbortController();
  error(); screen("saved-scan"); $("saved-items").replaceChildren();
  $("saved-receipt").hidden = true; $("saved-loading").hidden = false;
  try {
    const response = await fetch(`/inventory/scans/${encodeURIComponent(id)}`, {signal: request.signal, cache: "no-store"});
    const data = await responseJSON(response, "Couldn’t open this scan. Return to Scan History and try again.");
    if (current !== generation) return;
    renderReceipt(data, "saved-items");
    $("saved-time").textContent = `Confirmed ${new Date(data.created_at).toLocaleString()}`;
    $("saved-receipt").hidden = false;
  } catch (e) {
    if (current === generation && e.name !== "AbortError") error(e instanceof TypeError
      ? "Couldn’t reach StoreRoom. Return to Scan History and try again." : e.message);
  } finally {
    if (current === generation) { request = null; $("saved-loading").hidden = true; }
  }
}
document.querySelectorAll(".browse-history").forEach(button => button.addEventListener("click", openHistory));
$("refresh-history").addEventListener("click", openHistory);
$("return-current").addEventListener("click", () => {
  generation++; request?.abort(); request = null; error(); setBusy(false);
  screen(confirmed ? "confirmed" : prediction ? "review" : "scan");
});
