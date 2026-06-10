document.addEventListener("DOMContentLoaded", function () {
  const statPending = document.getElementById("stat-pending");
  const statHistory = document.getElementById("stat-history");

  const badgePending = document.getElementById("badge-pending");
  const badgeHistory = document.getElementById("badge-history");

  const tablePending = document.getElementById("table-pending");
  const tableHistory = document.getElementById("table-history");

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

  function loadQueueData() {
    if (window.PACKAGE_ID) {
      loadPackageSummary(window.PACKAGE_ID);
      return;
    }

    fetch("/module/APPROV/api/queue")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load approval queues.");
        return res.json();
      })
      .then((resData) => {
        const data = resData.data;
        const pendingCount = data.pending.length;
        const historyCount = data.history.length;

        // Update stats
        statPending.textContent = pendingCount;
        statHistory.textContent = historyCount;

        badgePending.textContent = `${pendingCount} items`;
        badgeHistory.textContent = `${historyCount} sheets`;

        // Render queues
        renderPendingTable(data.pending);
        renderHistoryTable(data.history);
      })
      .catch((err) => {
        console.error("Queue load error:", err);
        const errRow = `<tr><td colspan="7" class="px-6 py-6 text-center text-rose-500 font-bold">Error loading queue: ${err.message}</td></tr>`;
        tablePending.innerHTML = errRow;
        tableHistory.innerHTML = errRow;
      });
  }

  function loadPackageSummary(packageId) {
    const target = document.getElementById("package-summary");
    if (!target) return;
    fetch(`/module/APPROV/api/packages/${packageId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load package summary.");
        return res.json();
      })
      .then((resData) => {
        const data = resData.data;
        const pkg = data.package;
        target.innerHTML = `
          <div class="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <div class="text-xs font-bold uppercase tracking-wider text-indigo-600">Monthly Workbook Package</div>
              <h2 class="mt-1 text-xl font-bold text-slate-900">${pkg.period_label} · ${pkg.site_name}</h2>
              <p class="mt-1 text-sm text-slate-500">Submitted by ${pkg.submitted_by} on ${formatDate(pkg.submitted_at)}</p>
            </div>
            <span class="inline-flex w-max rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">${pkg.status}</span>
          </div>
          <div class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="text-xs font-semibold text-slate-500">Included sheets</div>
              <div class="mt-1 text-lg font-bold text-slate-900">${pkg.included_submission_count}</div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="text-xs font-semibold text-slate-500">Current level</div>
              <div class="mt-1 text-lg font-bold text-slate-900">${pkg.current_level || "—"}</div>
            </div>
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div class="text-xs font-semibold text-slate-500">Package ID</div>
              <div class="mt-1 text-lg font-bold text-slate-900">${pkg.package_id}</div>
            </div>
          </div>
          <div class="mt-6 overflow-hidden rounded-lg border border-slate-200">
            <table class="min-w-full divide-y divide-slate-200 text-sm">
              <thead class="bg-slate-50 text-left text-xs font-bold uppercase tracking-wider text-slate-500">
                <tr>
                  <th class="px-4 py-3">Form</th>
                  <th class="px-4 py-3">Status</th>
                  <th class="px-4 py-3">Submitted By</th>
                  <th class="px-4 py-3 text-right">Fallback Review</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                ${data.submissions.map((sub) => `
                  <tr>
                    <td class="px-4 py-3 font-semibold text-slate-900">${sub.form_name}</td>
                    <td class="px-4 py-3 text-slate-600">${sub.status}</td>
                    <td class="px-4 py-3 text-slate-600">${sub.submitted_by}</td>
                    <td class="px-4 py-3 text-right">
                      <a href="/module/APPROV/submissions/${sub.submission_id}" class="text-xs font-bold text-indigo-600 hover:text-indigo-700">Open sheet</a>
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        `;
      })
      .catch((err) => {
        target.innerHTML = `<p class="text-sm font-semibold text-rose-600">${err.message}</p>`;
      });
  }

  function renderPendingTable(rows) {
    tablePending.innerHTML = "";
    if (rows.length === 0) {
      tablePending.innerHTML = `
        <tr>
          <td colspan="7" class="px-6 py-8 text-center text-slate-400 italic">
            No sheets pending your approval. Well done!
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/50 transition-colors";

      // Days Waiting Colour Coding: green <3, amber 3-5, red >5
      let daysClass = "bg-emerald-50 text-emerald-700 border border-emerald-200";
      if (row.days_waiting >= 3 && row.days_waiting <= 5) {
        daysClass = "bg-amber-50 text-amber-700 border border-amber-200";
      } else if (row.days_waiting > 5) {
        daysClass = "bg-rose-50 text-rose-700 border border-rose-200 animate-pulse";
      }

      // Actionable column button
      let actionBtn = "";
      if (row.is_my_turn) {
        const href = row.item_type === "package"
          ? `/module/APPROV/packages/${row.package_id}`
          : `/module/APPROV/submissions/${row.submission_id}`;
        const label = row.item_type === "package" ? "Review Package" : "Review Submission";
        actionBtn = `
          <a href="${href}" class="inline-flex items-center px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm hover:shadow transition-all">
            ${label}
          </a>
        `;
      } else {
        actionBtn = `
          <span class="inline-flex items-center px-2 py-1 bg-slate-100 text-slate-500 text-xs font-medium rounded-lg border border-slate-200 cursor-not-allowed" title="It is not your turn in the sequence.">
            Awaiting Sequence
          </span>
        `;
      }

      const itemLabel = row.item_type === "package"
        ? (row.label || "Monthly Workbook Package")
        : (row.form_name || "Unknown Form");
      const includedForms = Array.isArray(row.forms_included) ? row.forms_included : [];
      const itemMeta = row.item_type === "package"
        ? `${row.included_submission_count || 0} sheets · ${includedForms.join(", ") || "Forms unavailable"}`
        : "Single sheet";

      tr.innerHTML = `
        <td class="px-6 py-4">
          <div class="font-bold text-slate-900">${itemLabel}</div>
          <div class="mt-0.5 text-xs font-medium text-slate-500">${itemMeta}</div>
        </td>
        <td class="px-6 py-4 font-semibold text-slate-600">${row.site_name}</td>
        <td class="px-6 py-4 font-medium text-slate-700">${row.period_label}</td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 text-xs font-semibold">
            Level ${row.current_level_number}: ${row.current_level_name}
          </span>
        </td>
        <td class="px-6 py-4 text-xs font-medium text-slate-600">${row.submitted_by_name}</td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${daysClass}">
            ${row.days_waiting} day${row.days_waiting === 1 ? "" : "s"}
          </span>
        </td>
        <td class="px-6 py-4 text-right">
          ${actionBtn}
        </td>
      `;
      tablePending.appendChild(tr);
    });
  }

  function renderHistoryTable(rows) {
    tableHistory.innerHTML = "";
    if (rows.length === 0) {
      tableHistory.innerHTML = `
        <tr>
          <td colspan="7" class="px-6 py-8 text-center text-slate-400 italic">
            You haven't actioned any sheets recently.
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/50 transition-colors";

      let actionBadgeClass = "bg-emerald-100 text-emerald-800 border-emerald-200";
      if (row.action === "Request Changes") {
        actionBadgeClass = "bg-amber-100 text-amber-800 border-amber-200";
      } else if (row.action === "Reject") {
        actionBadgeClass = "bg-rose-100 text-rose-800 border-rose-200";
      }

      let statusBadgeClass = "bg-slate-100 text-slate-700";
      if (row.current_status === "Approved") statusBadgeClass = "bg-emerald-100 text-emerald-800 border border-emerald-200";
      else if (row.current_status === "Under Review") statusBadgeClass = "bg-blue-100 text-blue-800 border border-blue-200";
      else if (row.current_status === "Changes Requested") statusBadgeClass = "bg-amber-100 text-amber-800 border border-amber-200";
      else if (row.current_status === "Rejected") statusBadgeClass = "bg-rose-100 text-rose-800 border border-rose-200";

      tr.innerHTML = `
        <td class="px-6 py-4 font-bold text-slate-900">${row.form_name}</td>
        <td class="px-6 py-4 font-semibold text-slate-600">${row.site_name}</td>
        <td class="px-6 py-4 font-medium text-slate-700">${row.period_label}</td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-bold border ${actionBadgeClass}">
            ${row.action}
          </span>
        </td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${statusBadgeClass}">
            ${row.current_status}
          </span>
        </td>
        <td class="px-6 py-4 text-xs text-slate-500">${formatDate(row.acted_at)}</td>
        <td class="px-6 py-4 text-right">
          <a href="/module/APPROV/submissions/${row.submission_id}" class="inline-flex items-center px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-all">
            View Details
          </a>
        </td>
      `;
      tableHistory.appendChild(tr);
    });
  }

  loadQueueData();
});
