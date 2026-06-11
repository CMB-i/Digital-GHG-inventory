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

  function workbookUrl(rowOrSite, formId = null, month = null) {
    const params = new URLSearchParams();
    params.set("site_id", rowOrSite.site_id || rowOrSite.id);
    const targetFormId = formId || rowOrSite.form_id;
    if (targetFormId) {
      params.set("form_id", targetFormId);
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
    const formsBySite = options.forms_by_site || {};
    const siteSummaries = new Map();

    sites.forEach((site) => {
      const forms = formsBySite[String(site.id)] || [];
      siteSummaries.set(String(site.id), {
        id: site.id,
        site_id: site.id,
        name: site.name,
        code: site.code,
        assignedForms: forms.length,
        firstFormId: forms[0] ? forms[0].id : null,
        actionNeeded: 0,
        underReview: 0,
        approved: 0
      });
    });

    (data.action_needed || []).forEach((row) => {
      if (fyForMonth(row.year, row.month) !== currentFy) return;
      const summary = siteSummaries.get(String(row.site_id));
      if (summary) summary.actionNeeded += 1;
    });

    (data.submitted || []).forEach((row) => {
      if (fyForMonth(row.year, row.month) !== currentFy) return;
      const summary = siteSummaries.get(String(row.site_id));
      if (!summary) return;
      if (row.status === "Approved") {
        summary.approved += 1;
      } else if (["Submitted", "Under Review", "Resubmitted"].includes(row.status)) {
        summary.underReview += 1;
      }
    });

    const summaries = Array.from(siteSummaries.values()).filter((summary) => summary.assignedForms > 0);
    if (!summaries.length) {
      workbookCards.innerHTML = `
        <div class="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-5 py-8 text-center md:col-span-2 xl:col-span-3">
          <p class="text-sm font-bold text-slate-700">No annual workbook is available.</p>
          <p class="mt-1 text-sm text-slate-500">Ask an admin to assign forms and open reporting periods for your site.</p>
        </div>
      `;
      return;
    }

    workbookCards.innerHTML = summaries.map((summary) => `
      <article class="flex min-h-[220px] flex-col justify-between rounded-2xl border border-indigo-100 bg-gradient-to-br from-white to-indigo-50/50 p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
        <div>
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-lg font-bold text-slate-900">${summary.name}</h3>
              <p class="mt-1 text-xs font-semibold uppercase tracking-wide text-slate-400">${summary.code || "Site"}</p>
            </div>
            <span class="rounded-full bg-indigo-100 px-2.5 py-1 text-xs font-bold text-indigo-700">${fyLabel(currentFy)}</span>
          </div>
          <dl class="mt-5 grid grid-cols-2 gap-3 text-sm">
            <div class="rounded-xl border border-slate-200 bg-white/80 p-3">
              <dt class="text-xs font-semibold text-slate-400">Assigned forms</dt>
              <dd class="mt-1 text-xl font-bold text-slate-900">${summary.assignedForms}</dd>
            </div>
            <div class="rounded-xl border border-amber-100 bg-amber-50/70 p-3">
              <dt class="text-xs font-semibold text-amber-600">Action needed</dt>
              <dd class="mt-1 text-xl font-bold text-amber-800">${summary.actionNeeded}</dd>
            </div>
            <div class="rounded-xl border border-blue-100 bg-blue-50/70 p-3">
              <dt class="text-xs font-semibold text-blue-600">Under review</dt>
              <dd class="mt-1 text-xl font-bold text-blue-800">${summary.underReview}</dd>
            </div>
            <div class="rounded-xl border border-emerald-100 bg-emerald-50/70 p-3">
              <dt class="text-xs font-semibold text-emerald-600">Completed</dt>
              <dd class="mt-1 text-xl font-bold text-emerald-800">${summary.approved}</dd>
            </div>
          </dl>
        </div>
        <a href="${workbookUrl(summary, summary.firstFormId)}" class="mt-5 inline-flex h-10 items-center justify-center rounded-lg bg-slate-900 px-4 text-sm font-bold text-white shadow-sm hover:bg-slate-800">
          Open Workbook
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
            No drafts or pending actions. Excellent!
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
            ${row.status}
          </span>
        </td>
        <td class="px-6 py-4 text-xs text-slate-500">${formatDate(row.last_saved)}</td>
        <td class="px-6 py-4 text-right">
          <a href="${workbookUrl(row)}" class="inline-flex items-center px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm hover:shadow transition-all">
            Open in Workbook
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
            All forms have been started or submitted for the current periods!
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
          <a href="${workbookUrl(row)}" class="inline-flex items-center px-3 py-1.5 bg-white border border-slate-300 hover:border-indigo-500 hover:text-indigo-600 text-slate-700 text-xs font-bold rounded-lg shadow-sm transition-all">
            Open in Workbook
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
          <a href="${submittedViewUrl(row)}" class="inline-flex items-center px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-all">
            View Details
          </a>
        </td>
      `;
      tableSubmitted.appendChild(tr);
    });
  }

  // Load on start
  loadDashboardData();
});
