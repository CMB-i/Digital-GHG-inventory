document.addEventListener("DOMContentLoaded", function () {
  const statActionNeeded = document.getElementById("stat-action-needed");
  const statNotStarted = document.getElementById("stat-not-started");
  const statUnderReview = document.getElementById("stat-under-review");
  const statApproved = document.getElementById("stat-approved");

  const badgeActionNeeded = document.getElementById("badge-action-needed");
  const badgeNotStarted = document.getElementById("badge-not-started");
  const badgeSubmitted = document.getElementById("badge-submitted");

  const tableActionNeeded = document.getElementById("table-action-needed");
  const tableNotStarted = document.getElementById("table-not-started");
  const tableSubmitted = document.getElementById("table-submitted");

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
    fetch("/module/SUBMIT/api/sheets")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load environmental sheets.");
        return res.json();
      })
      .then((data) => {
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
      });
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
          <a href="/module/SUBMIT/submissions/${row.submission_id}" class="inline-flex items-center px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm hover:shadow transition-all">
            Resume Entry
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

      const btnStart = document.createElement("button");
      btnStart.type = "button";
      btnStart.className = "inline-flex items-center px-3 py-1.5 bg-white border border-slate-300 hover:border-indigo-500 hover:text-indigo-600 text-slate-700 text-xs font-bold rounded-lg shadow-sm transition-all";
      btnStart.textContent = "Start Entry";
      btnStart.onclick = () => startSubmission(row.site_id, row.form_id, row.reporting_period_id, btnStart);

      tr.innerHTML = `
        <td class="px-6 py-4 font-bold text-slate-900">${row.form_name}</td>
        <td class="px-6 py-4 font-semibold text-slate-600">${row.site_name}</td>
        <td class="px-6 py-4 font-medium text-slate-700">${row.period_label}</td>
        <td class="px-6 py-4 text-xs font-medium text-slate-500">${formatShortDate(row.deadline)}</td>
        <td class="px-6 py-4 text-right action-td"></td>
      `;
      
      tr.querySelector(".action-td").appendChild(btnStart);
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
          <a href="/module/SUBMIT/submissions/${row.submission_id}" class="inline-flex items-center px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-all">
            View Details
          </a>
        </td>
      `;
      tableSubmitted.appendChild(tr);
    });
  }

  // Call POST API to create draft
  function startSubmission(siteId, formId, periodId, btn) {
    // Set loading
    const origText = btn.textContent;
    btn.textContent = "Creating...";
    btn.disabled = true;

    fetch("/module/SUBMIT/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        site_id: siteId,
        form_id: formId,
        reporting_period_id: periodId
      })
    })
      .then(async (res) => {
        const data = await res.json();
        if (res.status === 409) {
          // Duplicate exists, redirect directly
          window.location.href = `/module/SUBMIT/submissions/${data.existing_id}`;
          return;
        }
        if (!res.ok) throw new Error(data.error || "Failed to create draft sheet.");
        // Redirect to new draft sheet
        window.location.href = `/module/SUBMIT/submissions/${data.data.submission_id}`;
      })
      .catch((err) => {
        alert(err.message);
        btn.textContent = origText;
        btn.disabled = false;
      });
  }

  // Load on start
  loadDashboardData();
});
