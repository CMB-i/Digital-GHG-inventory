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

  function loadQueueData() {
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
        badgeHistory.textContent = `${historyCount} reviews`;

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

  function renderPendingTable(rows) {
    tablePending.innerHTML = "";
    if (rows.length === 0) {
      tablePending.innerHTML = `
        <tr>
          <td colspan="7" class="px-6 py-8 text-center text-slate-400 italic">
            No monthly packages are waiting for your review.
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
        const label = row.item_type === "package" ? "Review package" : "Review sheet";
        actionBtn = `
          <a href="${href}" class="inline-flex items-center px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm hover:shadow transition-all">
            ${label}
          </a>
        `;
      } else {
        actionBtn = `
          <span class="inline-flex items-center px-2 py-1 bg-slate-100 text-slate-500 text-xs font-medium rounded-lg border border-slate-200 cursor-not-allowed" title="It is not your turn in the sequence.">
            Waiting for earlier review
          </span>
        `;
      }

      const itemLabel = row.item_type === "package"
        ? (row.label || "Monthly Workbook Package")
        : (row.form_name || "Unknown sheet");
      const includedForms = Array.isArray(row.forms_included) ? row.forms_included : [];
      const itemMeta = row.item_type === "package"
        ? `${row.included_submission_count || 0} sheets · ${includedForms.join(", ") || "Sheet names unavailable"}`
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
            Step ${row.current_level_number}: ${row.current_level_name}
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
            You haven't reviewed any packages recently.
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-50/50 transition-colors";
      const detailsHref = row.package_id
        ? `/module/APPROV/packages/${row.package_id}`
        : `/module/APPROV/submissions/${row.submission_id}`;

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
            ${row.action_text || row.action}
          </span>
        </td>
        <td class="px-6 py-4">
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${statusBadgeClass}">
            ${row.current_status_text || humanStatus(row.current_status)}
          </span>
        </td>
        <td class="px-6 py-4 text-xs text-slate-500">${formatDate(row.acted_at)}</td>
        <td class="px-6 py-4 text-right">
          <a href="${detailsHref}" class="inline-flex items-center px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-lg transition-all">
            View package
          </a>
        </td>
      `;
      tableHistory.appendChild(tr);
    });
  }

  loadQueueData();
});
