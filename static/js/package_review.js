document.addEventListener("DOMContentLoaded", function () {
  const packageId = window.PACKAGE_ID;
  if (!packageId) return;

  const reviewTitle = document.getElementById("review-title");
  const reviewSubtitle = document.getElementById("review-subtitle");
  const badgeStatus = document.getElementById("badge-status");
  const cellStateLegend = document.getElementById("cell-state-legend");
  const legendItems = document.getElementById("legend-items");
  const reviewLoading = document.getElementById("review-loading");
  const reviewError = document.getElementById("review-error");
  const reviewContent = document.getElementById("review-content");
  const metaSheetCount = document.getElementById("meta-sheet-count");
  const metaLevel = document.getElementById("meta-level");
  const metaPackageId = document.getElementById("meta-package-id");
  const formTabs = document.getElementById("form-tabs");
  const sheetTitle = document.getElementById("sheet-title");
  const sheetMeta = document.getElementById("sheet-meta");
  const sheetStatus = document.getElementById("sheet-status");
  const sheetFallbackLink = document.getElementById("sheet-fallback-link");
  const sheetValues = document.getElementById("sheet-values");
  const actionsPanel = document.getElementById("actions-panel");
  const actionsLocked = document.getElementById("actions-locked");
  const commentInput = document.getElementById("review-comment");
  const btnApprovePackage = document.getElementById("btn-approve-package");
  const btnRequestChangesPackage = document.getElementById("btn-request-changes-package");
  const btnRejectPackage = document.getElementById("btn-reject-package");

  let reviewData = null;
  let activeSheetIndex = 0;

  const CELL_STATE_META = {
    blank_editable: { label: "Blank", className: "bg-slate-100 text-slate-700 border-slate-200" },
    draft_filled: { label: "Draft", className: "bg-blue-50 text-blue-700 border-blue-200" },
    submitted: { label: "Pending review", className: "bg-indigo-50 text-indigo-700 border-indigo-200" },
    approved_locked: { label: "Approved", className: "bg-emerald-50 text-emerald-700 border-emerald-200" },
    changes_requested: { label: "Changes requested", className: "bg-amber-50 text-amber-700 border-amber-200" },
    late_entry: { label: "Late entry", className: "bg-violet-50 text-violet-700 border-violet-200" },
  };

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
      hour12: true,
    });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function getStatusClass(status) {
    switch (status) {
      case "Approved":
        return "bg-emerald-100 text-emerald-800 border border-emerald-200";
      case "Submitted":
      case "Resubmitted":
      case "Under Review":
        return "bg-indigo-100 text-indigo-800 border border-indigo-200";
      case "Changes Requested":
        return "bg-amber-100 text-amber-800 border border-amber-200";
      case "Rejected":
        return "bg-rose-100 text-rose-800 border border-rose-200";
      default:
        return "bg-slate-100 text-slate-800 border border-slate-200";
    }
  }

  function cellStateBadge(cellState) {
    const meta = CELL_STATE_META[cellState] || {
      label: cellState || "Unknown",
      className: "bg-slate-100 text-slate-700 border-slate-200",
    };
    return `<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold ${meta.className}">${escapeHtml(meta.label)}</span>`;
  }

  function renderLegend() {
    legendItems.innerHTML = Object.keys(CELL_STATE_META)
      .map((state) => cellStateBadge(state))
      .join("");
    cellStateLegend.classList.remove("hidden");
  }

  function formatFieldValue(field, valueObj, proofs) {
    if (!valueObj) return "—";

    if (field.field_type === "file") {
      const proof = proofs[field.field_id] || proofs[String(field.field_id)];
      if (proof && proof.storage_key) {
        const href = `/module/SUBMIT/submissions/download/${encodeURIComponent(proof.storage_key)}`;
        const label = proof.original_name || "Download file";
        return `<a href="${href}" class="font-semibold text-indigo-600 hover:text-indigo-700">${escapeHtml(label)}</a>`;
      }
      return "—";
    }

    if (field.field_type === "boolean") {
      const raw = valueObj.raw_value;
      if (raw === true || raw === "true" || raw === "1" || raw === 1 || raw === "on") return "Yes";
      if (raw === false || raw === "false" || raw === "0" || raw === 0) return "No";
      return "—";
    }

    if (field.field_type === "calculated") {
      if (valueObj.calculated_value !== null && valueObj.calculated_value !== undefined) {
        return escapeHtml(valueObj.calculated_value);
      }
      return "—";
    }

    if (valueObj.raw_value !== null && valueObj.raw_value !== undefined && valueObj.raw_value !== "") {
      return escapeHtml(valueObj.raw_value);
    }

    if (valueObj.calculated_value !== null && valueObj.calculated_value !== undefined) {
      return escapeHtml(valueObj.calculated_value);
    }

    return "—";
  }

  function renderSheet(sheet) {
    sheetTitle.textContent = sheet.form_name;
    sheetMeta.textContent = `Submitted by ${sheet.submitted_by} on ${formatDate(sheet.submitted_at)}`;
    sheetStatus.className = `inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${getStatusClass(sheet.status)}`;
    sheetStatus.textContent = sheet.status;
    sheetFallbackLink.href = `/module/APPROV/submissions/${sheet.submission_id}`;

    const fields = [...(sheet.fields || [])].sort(
      (a, b) => (a.display_order || 0) - (b.display_order || 0)
    );

    if (!fields.length) {
      sheetValues.innerHTML = `
        <tr>
          <td colspan="4" class="px-5 py-8 text-center text-slate-400 italic">No fields configured for this form.</td>
        </tr>
      `;
      return;
    }

    sheetValues.innerHTML = fields.map((field) => {
      const valueObj = sheet.values ? sheet.values[field.field_code] : null;
      const lockIcon = valueObj && valueObj.is_locked
        ? `<span class="inline-flex items-center text-emerald-700" title="Locked">`
          + `<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">`
          + `<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />`
          + `</svg></span>`
        : `<span class="text-slate-300">—</span>`;
      const remark = valueObj && valueObj.remark
        ? `<div class="mt-1 text-xs text-slate-400">${escapeHtml(valueObj.remark)}</div>`
        : "";

      return `
        <tr class="hover:bg-slate-50/50">
          <td class="px-5 py-4 align-top">
            <div class="font-semibold text-slate-900">${escapeHtml(field.field_name)}</div>
            ${field.field_config && field.field_config.unit
              ? `<div class="text-xs text-slate-400">${escapeHtml(field.field_config.unit)}</div>`
              : ""}
          </td>
          <td class="px-5 py-4 align-top text-slate-700">
            ${formatFieldValue(field, valueObj, sheet.proofs || {})}
            ${remark}
          </td>
          <td class="px-5 py-4 align-top">
            ${cellStateBadge(valueObj ? valueObj.cell_state : "blank_editable")}
          </td>
          <td class="px-5 py-4 align-top text-center">${lockIcon}</td>
        </tr>
      `;
    }).join("");
  }

  function renderTabs() {
    formTabs.innerHTML = "";
    reviewData.sheets.forEach((sheet, index) => {
      const button = document.createElement("button");
      button.type = "button";
      const active = index === activeSheetIndex;
      button.className = `rounded-full border px-3 py-1.5 text-xs font-bold transition ${
        active
          ? "border-indigo-200 bg-indigo-50 text-indigo-700"
          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
      }`;
      button.textContent = sheet.form_name;
      button.onclick = function () {
        activeSheetIndex = index;
        renderTabs();
        renderSheet(reviewData.sheets[activeSheetIndex]);
      };
      formTabs.appendChild(button);
    });
  }

  function renderReview(data) {
    reviewData = data;
    const pkg = data.package;

    reviewTitle.textContent = `${pkg.period_label} · ${pkg.site_name}`;
    reviewSubtitle.textContent = `Submitted by ${pkg.submitted_by} on ${formatDate(pkg.submitted_at)}`;
    badgeStatus.className = `inline-flex w-max items-center rounded-full px-3 py-1 text-xs font-bold ${getStatusClass(pkg.status)}`;
    badgeStatus.textContent = pkg.status;

    metaSheetCount.textContent = String(pkg.included_submission_count);
    metaLevel.textContent = pkg.current_level_name
      ? `Level ${pkg.current_level}: ${pkg.current_level_name}`
      : (pkg.current_level ? `Level ${pkg.current_level}` : "—");
    metaPackageId.textContent = String(pkg.package_id);

    reviewLoading.classList.add("hidden");
    renderLegend();
    renderTabs();
    renderSheet(data.sheets[activeSheetIndex] || data.sheets[0]);
    renderActions(pkg);
    reviewContent.classList.remove("hidden");
  }

  function renderActions(pkg) {
    const actions = pkg.actions || {};
    const reviewableStatuses = new Set(["Submitted", "Resubmitted", "Under Review"]);
    const canAct = reviewableStatuses.has(pkg.status);

    if (!canAct) {
      actionsPanel.classList.add("hidden");
      actionsLocked.classList.remove("hidden");
      actionsLocked.textContent = `Package is ${pkg.status}. No review actions are available.`;
      return;
    }

    if (!actions.can_approve && !actions.can_request_changes && !actions.can_reject) {
      actionsPanel.classList.add("hidden");
      actionsLocked.classList.remove("hidden");
      actionsLocked.textContent = "You do not have permission to action this package.";
      return;
    }

    actionsPanel.classList.remove("hidden");
    actionsLocked.classList.add("hidden");
    if (btnApprovePackage) {
      btnApprovePackage.disabled = !actions.can_approve;
      btnApprovePackage.title = actions.can_approve ? "" : "It is not your turn to approve this package.";
    }
    if (btnRequestChangesPackage) btnRequestChangesPackage.disabled = !actions.can_request_changes;
    if (btnRejectPackage) btnRejectPackage.disabled = !actions.can_reject;
  }

  function postPackageAction(path, options) {
    const { requireComment = false, confirmMessage, successMessage } = options;
    const comment = commentInput ? commentInput.value : "";
    if (requireComment && (!comment || !comment.trim())) {
      alert("A review comment is required for this action.");
      if (commentInput) commentInput.focus();
      return;
    }
    if (!confirm(confirmMessage)) return;

    fetch(`/module/APPROV/api/packages/${packageId}/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comment: comment }),
    })
      .then((res) => {
        if (!res.ok) {
          return res.json().then((data) => {
            throw new Error(data.error || "Package action failed.");
          });
        }
        return res.json();
      })
      .then(() => {
        alert(successMessage);
        window.location.href = "/module/APPROV/";
      })
      .catch((err) => alert(err.message));
  }

  if (btnApprovePackage) {
    btnApprovePackage.addEventListener("click", function () {
      postPackageAction("approve", {
        confirmMessage: "Approve the entire workbook package?",
        successMessage: "Package approved successfully.",
      });
    });
  }

  if (btnRequestChangesPackage) {
    btnRequestChangesPackage.addEventListener("click", function () {
      postPackageAction("request-changes", {
        requireComment: true,
        confirmMessage: "Return the entire workbook package to the submitter for changes?",
        successMessage: "Package returned for changes.",
      });
    });
  }

  if (btnRejectPackage) {
    btnRejectPackage.addEventListener("click", function () {
      postPackageAction("reject", {
        requireComment: true,
        confirmMessage: "Reject the entire workbook package? This is terminal.",
        successMessage: "Package rejected.",
      });
    });
  }

  function showError(message) {
    reviewLoading.classList.add("hidden");
    reviewError.textContent = message;
    reviewError.classList.remove("hidden");
  }

  fetch(`/module/APPROV/api/packages/${packageId}/review`)
    .then((res) => {
      if (!res.ok) throw new Error("Failed to load package review.");
      return res.json();
    })
    .then((resData) => {
      if (!resData.data || !resData.data.sheets) {
        throw new Error("Package review data is unavailable.");
      }
      renderReview(resData.data);
    })
    .catch((err) => {
      showError(err.message);
    });
});
