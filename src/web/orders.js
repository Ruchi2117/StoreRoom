"use strict";
const el = id => document.getElementById(id);
const shopkeeper = location.pathname === "/shopkeeper/orders";
const labels = {PENDING:"Pending shop confirmation",ACCEPTED:"Accepted — units reserved",REJECTED:"Rejected",CANCELLED:"Cancelled"};
let generation=0, offset=0, busy=false;
function node(tag, className, text) {
  const element=document.createElement(tag); if(className) element.className=className;
  if(text!==undefined) element.textContent=text; return element;
}
function error(message="") { el("orders-error").textContent=message; el("orders-error").hidden=!message; }
async function json(url, options) {
  const response=await fetch(url,{cache:"no-store",...options});
  const data=await response.json();
  if(!response.ok) throw new Error(typeof data.detail==="string" ? data.detail : "Could not process the order request. Check the server and retry.");
  return data;
}
async function action(order, actionName, body) {
  if(busy) return;
  busy=true; error(); el("orders-message").textContent=""; ++generation;
  document.querySelectorAll("#order-list button").forEach(button=>button.disabled=true);
  try {
    const result=await json(`/orders/${order.order_id}/${actionName}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
    el("orders-message").textContent=`Request ${result.order_id}: ${labels[result.status]}.`;
    if(result.status==="ACCEPTED") el("orders-message").textContent+=" Available quantities now exclude these reservations; shelf observations are unchanged.";
    busy=false; await load();
  } catch(problem) {
    error(problem.message+" Refresh orders to verify status before retrying.");
    document.querySelectorAll("#order-list button").forEach(button=>button.disabled=false);
    busy=false;
  }
}
function render(order) {
  const card=node("article","card order-card"); card.dataset.orderId=order.order_id; card.dataset.status=order.status;
  card.append(node("h2","",order.shop_name),node("p","muted","Order #"+order.order_id),node("p","","Demo Customer · shared prototype"),node("strong","order-status",labels[order.status]));
  const list=node("ul"); for(const item of order.items) list.append(node("li","",`${item.product_name} × ${item.quantity}`)); card.append(list);
  const time=node("time","muted","Requested: "+new Date(order.created_at).toLocaleString()); time.dateTime=order.created_at; card.append(time);
  if(order.status!=="PENDING") card.append(node("p","muted","Updated: "+new Date(order.updated_at).toLocaleString()));
  if(order.rejection_reason) card.append(node("p","rejection-reason","Reason: "+order.rejection_reason));
  if(order.status==="PENDING") {
    if(shopkeeper) {
      card.append(node("p","notice","Check physical availability. Acceptance also requires a fresh reviewed count and sufficient unreserved units. Re-scan first if needed."));
      const label=node("label","confirm-availability"), check=node("input"); check.type="checkbox";
      label.append(check,document.createTextNode(" I checked current availability")); card.append(label);
      const accept=node("button","primary","Accept request"); accept.type="button";
      accept.addEventListener("click",()=>{ if(!check.checked) { error("Confirm current availability before accepting."); check.focus(); return; } action(order,"accept",{availability_confirmed:true}); });
      const reasonLabel=node("label","","Rejection reason (optional)"), reason=node("input"); reason.type="text"; reason.maxLength=200;
      reasonLabel.append(reason); const reject=node("button","secondary","Reject request"); reject.type="button";
      reject.addEventListener("click",()=>action(order,"reject",{reason:reason.value || null}));
      card.append(accept,reasonLabel,reject);
    } else {
      card.append(node("p","muted","Nothing is reserved until the shop accepts. You can cancel while this request is pending."));
      const cancel=node("button","secondary","Cancel request"); cancel.type="button";
      cancel.addEventListener("click",()=>action(order,"cancel",{})); card.append(cancel);
    }
  }
  return card;
}
async function load() {
  if(busy) return;
  const version=++generation; error();
  el("order-list").replaceChildren(node("p","muted","Loading requests…"));
  el("previous-orders").disabled=true; el("next-orders").disabled=true;
  try {
    const filter=el("status-filter").value;
    const data=await json(`/orders?limit=20&offset=${offset}`+(filter ? "&status="+filter : ""));
    if(version!==generation) return;
    el("order-list").replaceChildren(...data.orders.map(render));
    if(!data.orders.length) el("order-list").append(node("p","notice","No order requests in this view."));
    el("previous-orders").disabled=offset===0; el("next-orders").disabled=data.orders.length<20;
  } catch(problem) { if(version===generation) { el("order-list").replaceChildren(); error(problem.message); } }
}
el("page-title").textContent=shopkeeper ? "Shopkeeper order inbox" : "Your order requests";
el("page-description").textContent=shopkeeper ? "Review intent. Confirm stock. Accept or reject." : "Follow your requests here. Acceptance reserves units; it does not arrange payment or delivery.";
el("status-filter").value=shopkeeper ? "PENDING" : "";
el("orders-filter").addEventListener("submit",event=>{event.preventDefault();offset=0;load();});
el("previous-orders").addEventListener("click",()=>{offset=Math.max(0,offset-20);load();});
el("next-orders").addEventListener("click",()=>{offset+=20;load();});
// Manual refresh preserves typed reasons and explicit confirmation checkboxes.
load();
