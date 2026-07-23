/* Closed Deals — archived won deals & revenue */

async function loadClosedDeals() {
  const res = await fetch("/api/closed-deals");
  const data = await res.json();
  const badge = document.getElementById("badgeClosed");
  if (badge) badge.textContent = data.total || 0;

  const list = document.getElementById("closedList");
  if (!list) return;
  if (!data.closed?.length) {
    list.innerHTML = `<div class="empty-state"><h3>No closed deals yet</h3><p>Deals appear here only after you manually close them from the Tracking page.</p></div>`;
    return;
  }
  list.innerHTML = `<div class="table-wrap"><table class="data-table">
    <thead><tr>
      <th>Client</th><th>Product</th><th>Supplier</th><th>Closed</th><th></th>
    </tr></thead>
    <tbody>${data.closed.map((c) => {
      const o = c.offer || {};
      return `<tr>
        <td><strong>${esc(c.company_name)}</strong></td>
        <td>${esc(o.product || "—")}</td>
        <td>${esc((o.recommended_supplier || "").slice(0, 40))}</td>
        <td>${fmtDate(c.updated_at)}</td>
        <td><button class="btn ghost btn-sm btn-view-deal" data-id="${esc(c.deal_id)}">View</button></td>
      </tr>`;
    }).join("")}</tbody>
  </table></div>`;
  list.querySelectorAll(".btn-view-deal").forEach((btn) => {
    btn.onclick = () => showDealDetail(btn.dataset.id);
  });
}
