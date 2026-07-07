document.addEventListener("DOMContentLoaded", function () {
  const statActionNeeded = document.getElementById("stat-action-needed");
  const statNotStarted = document.getElementById("stat-not-started");
  const statUnderReview = document.getElementById("stat-under-review");
  const statApproved = document.getElementById("stat-approved");

  const badgeActionNeeded = document.getElementById("badge-action-needed");
  const badgeNotStarted = document.getElementById("badge-not-started");
  const badgeSubmitted = document.getElementById("badge-submitted");

  const workbookCards = document.getElementById("annual-workbook-cards");
  const workbookFyHelper = document.getElementById("workbook-fy-helper");

  const tableActionNeeded = document.getElementById("table-action-needed");
  const tableNotStarted = document.getElementById("table-not-started");
  const tableSubmitted = document.getElementById("table-submitted");

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
    if (targetWorkbookId) {
      params.set("workbook_id", targetWorkbookId);
    }
    const startYear = rowOrSite.year && rowOrSite.month
      ? fyForMonth(rowOrSite.year, rowOrSite.month)
      : defaultFyStartYear();
    params.set("fy", startYear);
    const targetMonth = month || rowOrSite.month;
    if (targetMonth) {
      params.set("month", targetMonth);
    }
    return `/module/SUBMIT/annual?${params.toString()}`;
  }

  function submittedViewUrl(row) {
    if (row.package_id) {
      return `/module/APPROV/packages/${row.package_id}`;
    }
    return `/module/SUBMIT/submissions/${row.submission_id}`;
  }

  // Format date string to local readable string
  function formatDate(dateStr) {
    if (!dateStr) return "—";
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true
    });
  }

  // Format date string to short date
  function formatShortDate(dateStr) {
    if (!dateStr) return "—";
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return date.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric"
    });
  }

  function humanStatus(status) {
    return {
      "Approved": "Approved and locked",
      "Draft": "Draft saved",
      "Changes Requested": "Needs correction",
      "Rejected": "Sent back",
      "Resubmitted": "Sent again for review",
      "Under Review": "Under review",
      "Submitted": "Submitted"
    }[status] || status || "Unknown";
  }

  // Fetch all sheets for the dashboard
  function loadDashboardData() {
    Promise.all([
      fetch("/module/SUBMIT/api/sheets").then((res) => {
        if (!res.ok) throw new Error("Failed to load environmental sheets.");
        return res.json();
      }),
      fetch("/module/SUBMIT/api/annual-workbook/options").then((res) => {
        if (!res.ok) throw new Error("Failed to load annual workbook options.");
        return res.json();
      })
    ])
      .then(([data, workbookOptions]) => {
        // 1. Calculate stats counts
        const actionNeededCount = data.action_needed.length;
        const notStartedCount = data.not_started.length;
        
        // Count submitted which are under review vs approved
        const underReviewCount = data.submitted.filter(s => 
          ["Submitted", "Under Review", "Resubmitted", "Rejected"].includes(s.status)
        ).length;
        const approvedCount = data.submitted.filter(s => s.status === "Approved").length;

        // Set counts
        statActionNeeded.textContent = actionNeededCount;
        statNotStarted.textContent = notStartedCount;
        statUnderReview.textContent = underReviewCount;
        statApproved.textContent = approvedCount;

        badgeActionNeeded.textContent = `${actionNeededCount} sheets`;
        badgeNotStarted.textContent = `${notStartedCount} sheets`;
        badgeSubmitted.textContent = `${data.submitted.length} sheets`;

        renderAnnualWorkbookCards(data, workbookOptions);

        // 2. Render Action Needed Queue
        renderActionNeededTable(data.action_needed);

        // 3. Render Not Started Queue
        renderNotStartedTable(data.not_started);

        // 4. Render Submitted & History Queue
        renderSubmittedTable(data.submitted);
      })
      .catch((err) => {
        console.error("Dashboard load error:", err);
        const errRow = `<tr><td colspan="7" class="px-6 py-6 text-center text-rose-500 font-bold">Error loading dashboard: ${err.message}</td></tr>`;
        tableActionNeeded.innerHTML = errRow;
        tableNotStarted.innerHTML = errRow;
        tableSubmitted.innerHTML = errRow;
        if (workbookCards) {
          workbookCards.innerHTML = `
            <div class="rounded-xl border border-rose-200 bg-rose-50 px-5 py-6 text-center text-sm font-semibold text-rose-700 md:col-span-2 xl:col-span-3">
              Error loading annual workbooks: ${err.message}
            </div>
          `;
        }
      });
  }

  function renderAnnualWorkbookCards(data, options) {
    if (!workbookCards) return;
    const currentFy = defaultFyStartYear();
    if (workbookFyHelper) {
      workbookFyHelper.textContent = fyLabel(currentFy);
    }

    const sites = options.sites || [];
    const workbooksBySite = options.workbooks_by_site || {};
    const siteSummaries = new Map();

    sites.forEach((site) => {
      const workbooks = workbooksBySite[String(site.id)] || [];
      workbooks.forEach((workbook) => {
        const key = `${site.id}:${workbook.id}`;
        siteSummaries.set(key, {
          id: key,
          workbook_id: workbook.id || workbook.workbook_id,
          workbook_name: workbook.name,
          workbook_code: workbook.code,
          site_name: site.name,
          site_code: site.code,
          sheet_count: workbook.sheet_count || (workbook.sheets ? workbook.sheets.length : 0),
          site_id: site.id,
          actionNeeded: 0,
          underReview: 0,
          approved: 0
        });
      });
    });

    (data.action_needed || []).forEach((row) => {
      if (fyForMonth(row.year, row.month) !== currentFy) return;
      siteSummaries.forEach((summary) => {
        if (String(summary.site_id) !== String(row.site_id)) return;
        if (row.workbook_id && String(summary.workbook_id) !== String(row.workbook_id)) return;
        summary.actionNeeded += 1;
      });
    });

    (data.submitted || []).forEach((row) => {
      if (fyForMonth(row.year, row.month) !== currentFy) return;
      siteSummaries.forEach((summary) => {
        if (String(summary.site_id) !== String(row.site_id)) return;
        if (row.workbook_id && String(summary.workbook_id) !== String(row.workbook_id)) return;
        if (row.status === "Approved") {
          summary.approved += 1;
        } else if (["Submitted", "Under Review", "Resubmitted"].includes(row.status)) {
          summary.underReview += 1;
        }
      });
    });

    const summaries = Array.from(siteSummaries.values()).filter((summary) => summary.sheet_count > 0);
    if (!summaries.length) {
      const needsSubmitterAssignment = Boolean(options.needs_submitter_assignment || data.needs_submitter_assignment);
      const title = needsSubmitterAssignment
        ? "You're not assigned as a submitter yet."
        : "No annual workbook is available.";
      const body = needsSubmitterAssignment
        ? (options.message || data.message)
        : "Ask your setup team to assign workbooks and open reporting periods for your site.";
      workbookCards.innerHTML = `
        <div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center md:col-span-2 xl:col-span-3">
          <p class="text-sm font-bold text-slate-700">${title}</p>
          <p class="mt-1 text-sm text-slate-500">${body}</p>
        </div>
      `;
      return;
    }

    workbookCards.innerHTML = summaries.map((summary) => `
      <article class="flex min-h-[168px] flex-col justify-between rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50/30">
        <div>
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-sm font-semibold text-slate-900">${summary.workbook_name}</h3>
              <p class="mt-1 text-xs font-medium text-slate-500">${summary.site_name}${summary.site_code ? ` (${summary.site_code})` : ""}</p>
            </div>
            <span class="status-badge status-badge-info">${fyLabel(currentFy)}</span>
          </div>
          <p class="mt-4 text-[13px] text-slate-500">
            ${summary.sheet_count} sheet${summary.sheet_count === 1 ? "" : "s"} ·
            <span class="${summary.actionNeeded > 0 ? 'font-semibold text-amber-700' : 'text-slate-500'}">${summary.actionNeeded} action needed</span> ·
            ${summary.approved} completed
          </p>
        </div>
        <a href="${workbookUrl(summary, summary.workbook_id)}" class="btn btn-outline btn-sm mt-5 justify-center">
          Open workbook
        </a>
      </article>
    `).join("");
  }

  function renderActionNeededTable(rows) {
    tableActionNeeded.innerHTML = "";
    if (rows.length === 0) {
      tableActionNeeded.innerHTML = `
        <tr>
          <td colspan="6" class="px-6 py-8 text-center text-slate-400 italic">
            No sheets need your attention right now.
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/50 transition-colors";
      
      let badgeClass = "bg-amber-100 text-amber-800 border border-amber-200";
      if (row.status === "Changes Requested") {
        badgeClass = "bg-rose-100 text-rose-800 border border-rose-200 animate-pulse";
      }

      tr.innerHTML = `
        <td class="px-6 py-4 font-bold text-slate-900">${row.form_name}</td>
        <td class="px-6 py-4 font-semibold text-slate-600">${row.site_name}</td>
        <td class="px-6 py-4 font-medium text-slate-700">${row.period_label}</td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${badgeClass}">
            ${row.status_text || humanStatus(row.status)}
          </span>
        </td>
        <td class="px-6 py-4 text-xs text-slate-500">${formatDate(row.last_saved)}</td>
        <td class="px-6 py-4 text-right">
          <a href="${workbookUrl(row)}" class="btn btn-primary btn-sm">
            Open workbook
          </a>
        </td>
      `;
      tableActionNeeded.appendChild(tr);
    });
  }

  function renderNotStartedTable(rows) {
    tableNotStarted.innerHTML = "";
    if (rows.length === 0) {
      tableNotStarted.innerHTML = `
        <tr>
          <td colspan="5" class="px-6 py-8 text-center text-slate-400 italic">
            All open sheets have been started or submitted.
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/50 transition-colors";

      tr.innerHTML = `
        <td class="px-6 py-4 font-bold text-slate-900">${row.form_name}</td>
        <td class="px-6 py-4 font-semibold text-slate-600">${row.site_name}</td>
        <td class="px-6 py-4 font-medium text-slate-700">${row.period_label}</td>
        <td class="px-6 py-4 text-xs font-medium text-slate-500">${formatShortDate(row.deadline)}</td>
        <td class="px-6 py-4 text-right">
          <a href="${workbookUrl(row)}" class="btn btn-outline btn-sm">
            Open workbook
          </a>
        </td>
      `;

      tableNotStarted.appendChild(tr);
    });
  }

  function renderSubmittedTable(rows) {
    tableSubmitted.innerHTML = "";
    if (rows.length === 0) {
      tableSubmitted.innerHTML = `
        <tr>
          <td colspan="7" class="px-6 py-8 text-center text-slate-400 italic">
            No submissions recorded.
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/50 transition-colors";

      let badgeClass = "bg-slate-100 text-slate-700";
      if (row.status === "Approved") badgeClass = "bg-emerald-100 text-emerald-800 border border-emerald-200";
      else if (row.status === "Submitted" || row.status === "Resubmitted") badgeClass = "bg-blue-100 text-blue-800 border border-blue-200";
      else if (row.status === "Under Review") badgeClass = "bg-indigo-100 text-indigo-800 border border-indigo-200";
      else if (row.status === "Rejected") badgeClass = "bg-rose-100 text-rose-800 border border-rose-200";

      tr.innerHTML = `
        <td class="px-6 py-4 font-bold text-slate-900">${row.form_name}</td>
        <td class="px-6 py-4 font-semibold text-slate-600">${row.site_name}</td>
        <td class="px-6 py-4 font-medium text-slate-700">${row.period_label}</td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${badgeClass}">
            ${row.status_text || row.status}
          </span>
        </td>
        <td class="px-6 py-4 text-xs font-medium text-slate-600">${row.submitted_by}</td>
        <td class="px-6 py-4 text-xs text-slate-500">${formatDate(row.submitted_at)}</td>
        <td class="px-6 py-4 text-right">
          <a href="${submittedViewUrl(row)}" class="btn btn-neutral btn-sm">
            View submitted sheet
          </a>
        </td>
      `;
      tableSubmitted.appendChild(tr);
    });
  }

  // Load on start
  loadDashboardData();
});
