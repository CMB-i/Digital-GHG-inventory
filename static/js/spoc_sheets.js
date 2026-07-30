document.addEventListener("DOMContentLoaded", function () {
  const summaryRoot = document.getElementById("my-workbooks-dashboard");
  const detailRoot = document.getElementById("my-workbooks-detail");
  if (!summaryRoot && !detailRoot) return;

  const formatDate = window.UIHelpers.formatDate;
  const formatShortDate = window.UIHelpers.formatShortDate;

  const state = {
    data: null,
    options: null,
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

  function defaultFyStartYear() {
    const now = new Date();
    const month = now.getMonth() + 1;
    return month >= 4 ? now.getFullYear() : now.getFullYear() - 1;
  }

  function fyLabel(startYear) {
    return `FY ${startYear}-${String(startYear + 1).slice(-2)}`;
  }

  function fyForMonth(year, month) {
    return month >= 4 ? year : year - 1;
  }

  function workbookUrl(rowOrSite, workbookId = null, month = null) {
    const params = new URLSearchParams();
    params.set("site_id", rowOrSite.site_id || rowOrSite.id);
    const targetWorkbookId = workbookId || rowOrSite.workbook_id;
    if (targetWorkbookId) params.set("workbook_id", targetWorkbookId);
    const startYear = rowOrSite.year && rowOrSite.month ? fyForMonth(rowOrSite.year, rowOrSite.month) : defaultFyStartYear();
    params.set("fy", startYear);
    const targetMonth = month || rowOrSite.month;
    if (targetMonth) params.set("month", targetMonth);
    return `/module/SUBMIT/annual?${params.toString()}`;
  }

  function submittedViewUrl(row) {
    if (row.package_id) return `/module/APPROV/packages/${row.package_id}`;
    return `/module/SUBMIT/submissions/${row.submission_id}`;
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

  // Same border/bg/text shade family (-200/-50/-700) and uppercase pill
  // treatment as the GRI Summary sheet's "Calculated" status badges
  // (see sheetResultStatusMeta in workbook_sheet.js), so drafts/submissions
  // read as one visual system with the workbook view.
  function statusBadge(row) {
    let cls = "border-slate-200 bg-slate-100 text-slate-600";
    if (row.status === "Approved") cls = "border-emerald-200 bg-emerald-50 text-emerald-700";
    else if (row.status === "Changes Requested" || row.status === "Rejected") cls = "border-rose-200 bg-rose-50 text-rose-700";
    else if (row.status === "Draft") cls = "border-amber-200 bg-amber-50 text-amber-700";
    else if (["Submitted", "Resubmitted"].includes(row.status)) cls = "border-blue-200 bg-blue-50 text-blue-700";
    else if (row.status === "Under Review") cls = "border-indigo-200 bg-indigo-50 text-indigo-700";
    return `<span class="whitespace-nowrap rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${cls}">${row.status_text || humanStatus(row.status)}</span>`;
  }

  function rowRecency(row) {
    const value = row.last_saved || row.submitted_at || row.deadline || "";
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function loadData() {
    return Promise.all([
      fetch("/module/SUBMIT/api/sheets").then((res) => {
        if (!res.ok) throw new Error("Failed to load monthly sheet data.");
        return res.json();
      }),
      fetch("/module/SUBMIT/api/annual-workbook/options").then((res) => {
        if (!res.ok) throw new Error("Failed to load workbook options.");
        return res.json();
      }),
    ]).then(([data, options]) => {
      state.data = data || {};
      state.options = options || {};
      return state;
    });
  }

  function countUnderReview(rows) {
    return (rows || []).filter(row => ["Submitted", "Under Review", "Resubmitted", "Rejected"].includes(row.status)).length;
  }

  function renderStats(data) {
    const byId = {
      "stat-action-needed": (data.action_needed || []).length,
      "stat-not-started": (data.not_started || []).length,
      "stat-under-review": countUnderReview(data.submitted || []),
      "stat-approved": (data.submitted || []).filter(row => row.status === "Approved").length,
    };
    Object.entries(byId).forEach(([id, value]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    });
    const fy = document.getElementById("workbook-fy-helper");
    if (fy) fy.textContent = fyLabel(defaultFyStartYear());
  }

  function siteSummaries(data, options) {
    const sites = options.sites || [];
    const workbooksBySite = options.workbooks_by_site || {};
    const countsBySite = new Map();
    const bump = (siteId, key) => {
      const mapKey = String(siteId);
      if (!countsBySite.has(mapKey)) countsBySite.set(mapKey, { actionNeeded: 0, notStarted: 0, submitted: 0 });
      countsBySite.get(mapKey)[key] += 1;
    };
    (data.action_needed || []).forEach((row) => bump(row.site_id, "actionNeeded"));
    (data.not_started || []).forEach((row) => bump(row.site_id, "notStarted"));
    (data.submitted || []).forEach((row) => bump(row.site_id, "submitted"));

    return sites.map((site) => {
      const workbooks = workbooksBySite[String(site.id)] || [];
      const sheetCount = workbooks.reduce((sum, workbook) => (
        sum + (workbook.sheet_count || (Array.isArray(workbook.sheets) ? workbook.sheets.length : 0))
      ), 0);
      const counts = countsBySite.get(String(site.id)) || { actionNeeded: 0, notStarted: 0, submitted: 0 };
      const openCount = counts.actionNeeded + counts.notStarted;
      return {
        ...site,
        sheet_count: sheetCount,
        workbook_count: workbooks.length,
        open_period_count: openCount,
        total_period_count: openCount + counts.submitted,
        first_workbook_id: workbooks[0] ? (workbooks[0].id || workbooks[0].workbook_id) : null,
      };
    }).sort((a, b) => a.name.localeCompare(b.name));
  }

  // Same navy token (--ghg-navy) already used for open-period counts
  // elsewhere on this dashboard -- a compact ring reads at a glance instead
  // of a plain "N OPEN" text label, matching the GRI Summary donut language.
  function siteProgressRing(open, total) {
    const size = 40;
    const stroke = 4;
    const radius = (size - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const fraction = total > 0 ? Math.min(1, open / total) : 0;
    const dash = circumference * fraction;
    const center = size / 2;
    const percent = total > 0 ? Math.round((open / total) * 100) : 0;
    return `
      <div class="relative h-10 w-10 shrink-0">
        <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="-rotate-90">
          <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="#e2e8f0" stroke-width="${stroke}"></circle>
          ${fraction > 0 ? `<circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="#1a3a6b" stroke-width="${stroke}" stroke-linecap="round" stroke-dasharray="${dash} ${circumference}"></circle>` : ""}
        </svg>
        <div class="absolute inset-0 flex items-center justify-center text-[9px] font-bold text-[#1a3a6b]">${percent}%</div>
      </div>
    `;
  }

  function renderSitesPanel(data, options) {
    const list = document.getElementById("sites-panel-list");
    const badge = document.getElementById("site-count-badge");
    if (!list) return;
    const summaries = siteSummaries(data, options);
    if (badge) badge.textContent = `${summaries.length} site${summaries.length === 1 ? "" : "s"}`;
    if (!summaries.length) {
      const message = options.needs_submitter_assignment || data.needs_submitter_assignment
        ? (options.message || data.message)
        : "No assigned live workbooks are available.";
      list.innerHTML = `<div class="px-3 py-6 text-center text-sm text-slate-500">${message}</div>`;
      return;
    }

    list.innerHTML = `<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">${summaries.map(site => `
      <a href="${site.first_workbook_id ? workbookUrl(site, site.first_workbook_id) : "#"}" class="flex items-center gap-3 rounded border border-rowBorder bg-white px-4 py-3 transition-colors hover:border-[#1a3a6b]/40 hover:bg-slate-50">
        ${siteProgressRing(site.open_period_count, site.total_period_count)}
        <div class="min-w-0" title="${site.name}">
          <div class="truncate text-sm font-normal text-slate-800">${site.name}</div>
          <div class="mt-0.5 truncate text-[11px] font-normal text-slate-500">${site.open_period_count} open · ${site.total_period_count} total</div>
        </div>
      </a>
    `).join("")}</div>`;
  }

  function renderCompactList(containerId, rows, emptyText, kind) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const limited = rows.slice(0, kind === "history" ? 5 : 8);
    if (!limited.length) {
      container.innerHTML = `<div class="px-3 py-6 text-center text-sm text-slate-400">${emptyText}</div>`;
      return;
    }
    container.innerHTML = limited.map(row => {
      const href = kind === "history" ? submittedViewUrl(row) : workbookUrl(row);
      const right = kind === "history" ? formatShortDate(row.submitted_at || row.last_saved) : formatShortDate(row.last_saved);
      return `
        <a href="${href}" class="mb-1.5 block rounded border border-transparent px-4 py-3 transition-colors hover:border-rowBorder hover:bg-slate-50">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="truncate text-sm font-normal text-slate-800">${row.form_name}</div>
              <div class="mt-0.5 truncate text-[11px] font-normal text-slate-500">${row.site_name} · ${row.period_label}</div>
            </div>
            <div class="shrink-0 text-right text-[11px] font-normal text-slate-400">${right || "—"}</div>
          </div>
          <div class="mt-1.5">${statusBadge(row)}</div>
        </a>
      `;
    }).join("");
  }

  function renderSummary() {
    setFixedDashboardShell(true);
    loadData()
      .then(({ data, options }) => {
        renderStats(data);
        renderSitesPanel(data, options);
        const needsAttention = [...(data.action_needed || [])].sort((a, b) => {
          if (a.status === "Changes Requested" && b.status !== "Changes Requested") return -1;
          if (b.status === "Changes Requested" && a.status !== "Changes Requested") return 1;
          return rowRecency(b) - rowRecency(a);
        });
        const history = [...(data.submitted || [])].sort((a, b) => rowRecency(b) - rowRecency(a));
        renderCompactList("needs-attention-list", needsAttention, "No rows need attention right now.", "needs");
        renderCompactList("submission-history-list", history, "No submissions recorded yet.", "history");
      })
      .catch((err) => {
        console.error("Dashboard load error:", err);
        ["sites-panel-list", "needs-attention-list", "submission-history-list"].forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.innerHTML = `<div class="px-3 py-6 text-center text-sm font-semibold text-rose-600">${err.message}</div>`;
        });
      });
  }

  function detailRowsForType(type, data) {
    if (type === "drafts") return data.action_needed || [];
    if (type === "open-rows") return data.not_started || [];
    return data.submitted || [];
  }

  function detailColumns(type) {
    if (type === "open-rows") {
      return [
        ["form_name", "Sheet Name"], ["site_name", "Site"], ["period_label", "Reporting Period"],
        ["deadline", "Deadline"], ["action", "Actions"],
      ];
    }
    if (type === "submissions") {
      return [
        ["form_name", "Sheet Name"], ["site_name", "Site"], ["period_label", "Reporting Period"],
        ["status", "Status"], ["submitted_by", "Submitted By"], ["submitted_at", "Submitted At"], ["action", "Actions"],
      ];
    }
    return [
      ["form_name", "Sheet Name"], ["site_name", "Site"], ["period_label", "Reporting Period"],
      ["status", "Status"], ["last_saved", "Last Saved"], ["action", "Actions"],
    ];
  }

  function renderDetailHead(type) {
    const head = document.getElementById("detail-table-head");
    if (!head) return;
    head.innerHTML = `<tr>${detailColumns(type).map(([, label]) => `<th class="px-6 py-3 text-left">${label}</th>`).join("")}</tr>`;
  }

  function rowText(row) {
    return [row.form_name, row.site_name, row.period_label, row.status, row.status_text, row.submitted_by, row.workbook_name]
      .filter(Boolean).join(" ").toLowerCase();
  }

  function applyDetailFilters() {
    const search = (document.getElementById("detail-search")?.value || "").trim().toLowerCase();
    const site = document.getElementById("detail-site-filter")?.value || "";
    state.filteredRows = state.detailRows.filter((row) => {
      if (site && String(row.site_id) !== site) return false;
      if (search && !rowText(row).includes(search)) return false;
      return true;
    });
    state.page = 1;
    renderDetailRows();
  }

  function detailCell(type, row, key) {
    if (key === "status") return statusBadge(row);
    if (key === "deadline") return formatShortDate(row.deadline);
    if (key === "last_saved") return formatDate(row.last_saved);
    if (key === "submitted_at") return formatDate(row.submitted_at);
    if (key === "action") {
      const href = type === "submissions" ? submittedViewUrl(row) : workbookUrl(row);
      const label = type === "submissions" ? "View" : "Open workbook";
      return `<a href="${href}" class="btn btn-outline btn-sm">${label}</a>`;
    }
    return row[key] || "—";
  }

  function renderDetailRows() {
    const type = detailRoot.dataset.detailType;
    const body = document.getElementById("detail-table-body");
    const totalBadge = document.getElementById("detail-total-badge");
    const summary = document.getElementById("detail-page-summary");
    const pageNumber = document.getElementById("detail-page-number");
    if (!body) return;
    const pageCount = Math.max(1, Math.ceil(state.filteredRows.length / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), pageCount);
    const start = (state.page - 1) * state.pageSize;
    const rows = state.filteredRows.slice(start, start + state.pageSize);
    const columns = detailColumns(type);
    if (totalBadge) totalBadge.textContent = `${state.filteredRows.length} row${state.filteredRows.length === 1 ? "" : "s"}`;
    if (summary) {
      const from = state.filteredRows.length ? start + 1 : 0;
      const to = Math.min(start + state.pageSize, state.filteredRows.length);
      summary.textContent = `Showing ${from}-${to} of ${state.filteredRows.length}`;
    }
    if (pageNumber) pageNumber.textContent = `${state.page} / ${pageCount}`;
    document.getElementById("detail-prev").disabled = state.page <= 1;
    document.getElementById("detail-next").disabled = state.page >= pageCount;

    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="${columns.length}" class="px-6 py-8 text-center text-slate-400">No rows match the current filters.</td></tr>`;
      return;
    }
    body.innerHTML = rows.map(row => `
      <tr class="hover:bg-slate-50">
        ${columns.map(([key]) => `<td class="px-6 py-4 ${key === "action" ? "text-right" : ""}">${detailCell(type, row, key)}</td>`).join("")}
      </tr>
    `).join("");
  }

  function renderDetail() {
    setFixedDashboardShell(false);
    const type = detailRoot.dataset.detailType;
    renderDetailHead(type);
    loadData()
      .then(({ data }) => {
        state.detailRows = detailRowsForType(type, data).sort((a, b) => rowRecency(b) - rowRecency(a));
        const siteFilter = document.getElementById("detail-site-filter");
        if (siteFilter) {
          const sites = Array.from(new Map(state.detailRows.map(row => [String(row.site_id), row.site_name])).entries())
            .sort((a, b) => a[1].localeCompare(b[1]));
          siteFilter.innerHTML = `<option value="">All sites</option>${sites.map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}`;
        }
        state.pageSize = parseInt(document.getElementById("detail-page-size")?.value || "25", 10);
        applyDetailFilters();
      })
      .catch((err) => {
        console.error("Detail load error:", err);
        const body = document.getElementById("detail-table-body");
        if (body) body.innerHTML = `<tr><td class="px-6 py-8 text-center font-semibold text-rose-600">${err.message}</td></tr>`;
      });

    document.getElementById("detail-search")?.addEventListener("input", applyDetailFilters);
    document.getElementById("detail-site-filter")?.addEventListener("change", applyDetailFilters);
    document.getElementById("detail-page-size")?.addEventListener("change", (event) => {
      state.pageSize = parseInt(event.target.value, 10) || 25;
      state.page = 1;
      renderDetailRows();
    });
    document.getElementById("detail-prev")?.addEventListener("click", () => {
      state.page -= 1;
      renderDetailRows();
    });
    document.getElementById("detail-next")?.addEventListener("click", () => {
      state.page += 1;
      renderDetailRows();
    });
  }

  if (summaryRoot) renderSummary();
  if (detailRoot) renderDetail();
});
