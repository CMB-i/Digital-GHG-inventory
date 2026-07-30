document.addEventListener("DOMContentLoaded", function () {
  const summaryRoot = document.getElementById("review-queue-dashboard");
  const detailRoot = document.getElementById("review-queue-detail");
  if (!summaryRoot && !detailRoot) return;

  const formatDate = window.UIHelpers.formatDate;

  const state = {
    data: null,
    detailRows: [],
    filteredRows: [],
    page: 1,
    pageSize: 25,
  };

  function setFixedDashboardShell(enabled) {
    const main = document.querySelector("main.flex-1");
    if (!main) return;
    if (enabled) {
      main.classList.remove("overflow-y-auto");
      main.classList.add("overflow-hidden");
    } else {
      main.classList.remove("overflow-hidden");
      main.classList.add("overflow-y-auto");
    }
  }

  function loadQueueData() {
    return fetch("/module/APPROV/api/queue")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load approval queues.");
        return res.json();
      })
      .then((resData) => {
        state.data = resData.data || { pending: [], history: [] };
        return state.data;
      });
  }

  function itemHref(row) {
    if (row.item_type === "package" || row.package_id) return `/module/APPROV/packages/${row.package_id}`;
    return `/module/APPROV/submissions/${row.submission_id}`;
  }

  function itemName(row) {
    if (row.item_type === "package") return row.label || "Monthly Workbook Package";
    return row.form_name || "Monthly Sheet";
  }

  function itemMeta(row) {
    if (row.item_type === "package") {
      const forms = Array.isArray(row.forms_included) ? row.forms_included : [];
      return `${row.included_submission_count || 0} sheet${row.included_submission_count === 1 ? "" : "s"}${forms.length ? ` · ${forms.join(", ")}` : ""}`;
    }
    return row.form_name || "Single sheet";
  }

  function humanStatus(status) {
    return {
      Approved: "Approved",
      Draft: "Draft",
      "Changes Requested": "Needs correction",
      Rejected: "Sent back",
      Resubmitted: "Resubmitted",
      "Under Review": "Under review",
      Submitted: "Submitted",
    }[status] || status || "Unknown";
  }

  function daysBadge(days) {
    const value = Number(days) || 0;
    let cls = "bg-emerald-50 text-emerald-700 border border-emerald-200";
    if (value >= 3 && value <= 5) cls = "bg-amber-50 text-amber-700 border border-amber-200";
    if (value > 5) cls = "bg-rose-50 text-rose-700 border border-rose-200";
    return `<span class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold ${cls}">${value} day${value === 1 ? "" : "s"}</span>`;
  }

  function actionBadge(row) {
    let cls = "bg-emerald-100 text-emerald-800 border-emerald-200";
    if (row.action === "Request Changes") cls = "bg-amber-100 text-amber-800 border-amber-200";
    if (row.action === "Reject") cls = "bg-rose-100 text-rose-800 border-rose-200";
    return `<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-bold ${cls}">${row.action_text || row.action || "Reviewed"}</span>`;
  }

  function statusBadge(status, label) {
    let cls = "bg-slate-100 text-slate-700 border border-slate-200";
    if (status === "Approved") cls = "bg-emerald-100 text-emerald-800 border border-emerald-200";
    else if (status === "Under Review" || status === "Submitted" || status === "Resubmitted") cls = "bg-blue-100 text-blue-800 border border-blue-200";
    else if (status === "Changes Requested") cls = "bg-amber-100 text-amber-800 border border-amber-200";
    else if (status === "Rejected") cls = "bg-rose-100 text-rose-800 border border-rose-200";
    return `<span class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold ${cls}">${label || humanStatus(status)}</span>`;
  }

  function renderStats(data) {
    const pending = data.pending || [];
    const history = data.history || [];
    const statPending = document.getElementById("stat-pending");
    const statHistory = document.getElementById("stat-history");
    if (statPending) statPending.textContent = pending.length;
    if (statHistory) statHistory.textContent = history.length;
  }

  function renderPendingList(rows) {
    const container = document.getElementById("pending-review-list");
    if (!container) return;
    const limited = rows.slice(0, 8);
    if (!limited.length) {
      container.innerHTML = `<div class="px-3 py-8 text-center text-sm text-slate-400">No monthly packages are waiting for your review.</div>`;
      return;
    }
    container.innerHTML = limited.map(row => {
      const waitingText = row.is_my_turn ? "Ready for review" : "Waiting for earlier review";
      return `
        <a href="${itemHref(row)}" class="mb-1 block rounded border border-transparent px-3 py-2 hover:border-slate-200 hover:bg-slate-50">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold text-slate-800">${itemName(row)}</div>
              <div class="mt-0.5 truncate text-[11px] font-medium text-slate-500">${row.site_name} · ${row.period_label} · ${row.submitted_by_name || "Unknown submitter"}</div>
            </div>
            <div class="shrink-0">${daysBadge(row.days_waiting)}</div>
          </div>
          <div class="mt-1 flex items-center justify-between gap-3">
            <span class="truncate text-[11px] text-slate-500">Step ${row.current_level_number || "?"}: ${row.current_level_name || "Review"}</span>
            <span class="shrink-0 text-[11px] font-semibold ${row.is_my_turn ? "text-[#1a3a6b]" : "text-slate-400"}">${waitingText}</span>
          </div>
        </a>
      `;
    }).join("");
  }

  function renderHistoryList(rows) {
    const container = document.getElementById("review-history-list");
    if (!container) return;
    const limited = rows.slice(0, 6);
    if (!limited.length) {
      container.innerHTML = `<div class="px-3 py-8 text-center text-sm text-slate-400">You haven't reviewed any packages recently.</div>`;
      return;
    }
    container.innerHTML = limited.map(row => `
      <a href="${itemHref(row)}" class="mb-1 block rounded border border-transparent px-3 py-2 hover:border-slate-200 hover:bg-slate-50">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-slate-800">${row.form_name || "Reviewed item"}</div>
            <div class="mt-0.5 truncate text-[11px] font-medium text-slate-500">${row.site_name} · ${row.period_label} · ${formatDate(row.acted_at)}</div>
          </div>
          <div class="shrink-0">${actionBadge(row)}</div>
        </div>
        <div class="mt-1">${statusBadge(row.current_status, row.current_status_text)}</div>
      </a>
    `).join("");
  }

  function renderSummary() {
    setFixedDashboardShell(true);
    loadQueueData()
      .then((data) => {
        const pending = [...(data.pending || [])].sort((a, b) => (Number(b.days_waiting) || 0) - (Number(a.days_waiting) || 0));
        const history = [...(data.history || [])].sort((a, b) => Date.parse(b.acted_at || 0) - Date.parse(a.acted_at || 0));
        renderStats(data);
        renderPendingList(pending);
        renderHistoryList(history);
      })
      .catch((err) => {
        console.error("Queue load error:", err);
        ["pending-review-list", "review-history-list"].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.innerHTML = `<div class="px-3 py-6 text-center text-sm font-semibold text-rose-600">${err.message}</div>`;
        });
      });
  }

  function detailRowsForType(type, data) {
    return type === "history" ? data.history || [] : data.pending || [];
  }

  function detailColumns(type) {
    if (type === "history") {
      return [
        ["form_name", "Review Item"], ["site_name", "Site"], ["period_label", "Reporting Period"],
        ["action", "Your Action"], ["current_status", "Current Status"], ["acted_at", "Action Date"], ["action_link", "Actions"],
      ];
    }
    return [
      ["item", "Review Item"], ["site_name", "Site"], ["period_label", "Reporting Period"],
      ["step", "Review Step"], ["submitted_by_name", "Submitted By"], ["days_waiting", "Days Waiting"], ["action_link", "Actions"],
    ];
  }

  function renderDetailHead(type) {
    const head = document.getElementById("review-detail-table-head");
    if (!head) return;
    head.innerHTML = `<tr>${detailColumns(type).map(([, label]) => `<th class="px-6 py-3 text-left">${label}</th>`).join("")}</tr>`;
  }

  function rowText(row) {
    return [
      itemName(row), itemMeta(row), row.form_name, row.site_name, row.period_label,
      row.current_level_name, row.submitted_by_name, row.action_text, row.current_status_text,
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function applyDetailFilters() {
    const search = (document.getElementById("review-detail-search")?.value || "").trim().toLowerCase();
    const site = document.getElementById("review-detail-site-filter")?.value || "";
    state.filteredRows = state.detailRows.filter((row) => {
      if (site && row.site_name !== site) return false;
      if (search && !rowText(row).includes(search)) return false;
      return true;
    });
    state.page = 1;
    renderDetailRows();
  }

  function detailCell(type, row, key) {
    if (key === "item") {
      return `<div class="font-semibold text-slate-800">${itemName(row)}</div><div class="mt-0.5 max-w-md truncate text-[11px] text-slate-500">${itemMeta(row)}</div>`;
    }
    if (key === "step") return `Step ${row.current_level_number || "?"}: ${row.current_level_name || "Review"}`;
    if (key === "days_waiting") return daysBadge(row.days_waiting);
    if (key === "action") return actionBadge(row);
    if (key === "current_status") return statusBadge(row.current_status, row.current_status_text);
    if (key === "acted_at") return formatDate(row.acted_at);
    if (key === "action_link") return `<a href="${itemHref(row)}" class="btn btn-outline btn-sm">${type === "history" ? "View" : "Review"}</a>`;
    return row[key] || "—";
  }

  function renderDetailRows() {
    const type = detailRoot.dataset.detailType;
    const body = document.getElementById("review-detail-table-body");
    const totalBadge = document.getElementById("review-detail-total-badge");
    const summary = document.getElementById("review-detail-page-summary");
    const pageNumber = document.getElementById("review-detail-page-number");
    if (!body) return;
    const columns = detailColumns(type);
    const pageCount = Math.max(1, Math.ceil(state.filteredRows.length / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), pageCount);
    const start = (state.page - 1) * state.pageSize;
    const rows = state.filteredRows.slice(start, start + state.pageSize);
    if (totalBadge) totalBadge.textContent = `${state.filteredRows.length} row${state.filteredRows.length === 1 ? "" : "s"}`;
    if (summary) {
      const from = state.filteredRows.length ? start + 1 : 0;
      const to = Math.min(start + state.pageSize, state.filteredRows.length);
      summary.textContent = `Showing ${from}-${to} of ${state.filteredRows.length}`;
    }
    if (pageNumber) pageNumber.textContent = `${state.page} / ${pageCount}`;
    document.getElementById("review-detail-prev").disabled = state.page <= 1;
    document.getElementById("review-detail-next").disabled = state.page >= pageCount;

    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="${columns.length}" class="px-6 py-8 text-center text-slate-400">No rows match the current filters.</td></tr>`;
      return;
    }
    body.innerHTML = rows.map(row => `
      <tr class="hover:bg-slate-50">
        ${columns.map(([key]) => `<td class="px-6 py-4 ${key === "action_link" ? "text-right" : ""}">${detailCell(type, row, key)}</td>`).join("")}
      </tr>
    `).join("");
  }

  function renderDetail() {
    setFixedDashboardShell(false);
    const type = detailRoot.dataset.detailType;
    renderDetailHead(type);
    loadQueueData()
      .then((data) => {
        state.detailRows = detailRowsForType(type, data).sort((a, b) => {
          if (type === "history") return Date.parse(b.acted_at || 0) - Date.parse(a.acted_at || 0);
          return (Number(b.days_waiting) || 0) - (Number(a.days_waiting) || 0);
        });
        const siteFilter = document.getElementById("review-detail-site-filter");
        if (siteFilter) {
          const sites = Array.from(new Set(state.detailRows.map(row => row.site_name).filter(Boolean))).sort();
          siteFilter.innerHTML = `<option value="">All sites</option>${sites.map(site => `<option value="${site}">${site}</option>`).join("")}`;
        }
        state.pageSize = parseInt(document.getElementById("review-detail-page-size")?.value || "25", 10);
        applyDetailFilters();
      })
      .catch((err) => {
        console.error("Queue detail load error:", err);
        const body = document.getElementById("review-detail-table-body");
        if (body) body.innerHTML = `<tr><td class="px-6 py-8 text-center font-semibold text-rose-600">${err.message}</td></tr>`;
      });

    document.getElementById("review-detail-search")?.addEventListener("input", applyDetailFilters);
    document.getElementById("review-detail-site-filter")?.addEventListener("change", applyDetailFilters);
    document.getElementById("review-detail-page-size")?.addEventListener("change", (event) => {
      state.pageSize = parseInt(event.target.value, 10) || 25;
      state.page = 1;
      renderDetailRows();
    });
    document.getElementById("review-detail-prev")?.addEventListener("click", () => {
      state.page -= 1;
      renderDetailRows();
    });
    document.getElementById("review-detail-next")?.addEventListener("click", () => {
      state.page += 1;
      renderDetailRows();
    });
  }

  if (summaryRoot) renderSummary();
  if (detailRoot) renderDetail();
});
