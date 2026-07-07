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
  const sheetHead = document.getElementById("sheet-head");
  const sheetValues = document.getElementById("sheet-values");
  const actionsPanel = document.getElementById("actions-panel");
  const actionsLocked = document.getElementById("actions-locked");
  const commentInput = document.getElementById("review-comment");
  const btnApprovePackage = document.getElementById("btn-approve-package");
  const btnRequestChangesPackage = document.getElementById("btn-request-changes-package");
  const btnRejectPackage = document.getElementById("btn-reject-package");
  const cellIssueModal = document.getElementById("cell-issue-modal");
  const cellIssueContext = document.getElementById("cell-issue-context");
  const cellIssueList = document.getElementById("cell-issue-list");
  const cellIssueValue = document.getElementById("cell-issue-value");
  const cellIssueState = document.getElementById("cell-issue-state");
  const cellIssueAddSection = document.getElementById("cell-issue-add-section");
  const cellIssueText = document.getElementById("cell-issue-text");
  const cellIssueError = document.getElementById("cell-issue-error");
  const btnCloseCellIssue = document.getElementById("btn-close-cell-issue");
  const btnCancelCellIssue = document.getElementById("btn-cancel-cell-issue");
  const btnSaveCellIssue = document.getElementById("btn-save-cell-issue");
  const initialParams = new URLSearchParams(window.location.search);
  const requestedSheet = initialParams.get("sheet");

  let reviewData = null;
  let activeSheetIndex = 0;
  let selectedIssueCell = null;

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

  const escapeHtml = window.WorkbookSheet.escapeHtml;

  async function loadSheetAuditLogs(submissionId) {
    const card = document.getElementById("sheet-audit-logs-card");
    const timeline = document.getElementById("sheet-audit-logs-timeline");
    if (!card || !timeline) return;

    if (!submissionId) {
      card.classList.add("hidden");
      return;
    }

    timeline.innerHTML = `<div class="text-xs text-slate-500 py-2">Loading audit logs...</div>`;
    card.classList.remove("hidden");

    try {
      const response = await fetch(`/module/APPROV/api/submissions/${submissionId}/audit-logs`);
      if (!response.ok) throw new Error("Could not load audit logs.");
      const resData = await response.json();
      const events = resData.data || [];

      if (!events.length) {
        timeline.innerHTML = `<div class="text-xs text-slate-400 py-2 italic">No audit history recorded.</div>`;
        return;
      }

      timeline.innerHTML = `
        <div class="audit-timeline">
          ${events.map(event => {
            let badgeClass = "bg-slate-100 text-slate-800 border-slate-200";
            let dotClass = "";
            let bubbleClass = "bg-slate-50 border-slate-100 text-slate-700";

            if (event.action === "Submitted" || event.action === "Resubmitted") {
              badgeClass = "bg-indigo-50 text-indigo-700 border-indigo-200";
              dotClass = "dot-submitted";
            } else if (event.action === "Approve") {
              badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
              dotClass = "dot-approved";
              bubbleClass = "bg-[#def0e2] border-[#c0e6c7] text-[#1f6b34]";
            } else if (event.action === "Request Changes") {
              badgeClass = "bg-amber-50 text-amber-700 border-amber-200";
              dotClass = "dot-changes-requested";
              bubbleClass = "bg-[#fcf3d7] border-[#f5e4b3] text-[#8a6a13]";
            } else if (event.action === "Reject") {
              badgeClass = "bg-rose-50 text-rose-700 border-rose-200";
              dotClass = "dot-rejected";
              bubbleClass = "bg-[#fbe3e6] border-[#f6c2c8] text-[#9a1224]";
            }

            const displayAction = event.is_approval_action 
              ? (event.action === "Approve" ? "L" + event.level + " Approved" 
                : event.action === "Request Changes" ? "L" + event.level + " Requested Changes" 
                : "L" + event.level + " Rejected")
              : event.action;

            return `
              <div class="audit-timeline-item">
                <div class="audit-timeline-dot ${dotClass}"></div>
                <div class="flex items-center justify-between gap-2">
                  <span class="inline-flex items-center border rounded px-1.5 py-0.5 text-[10px] font-bold ${badgeClass}">
                    ${escapeHtml(displayAction)}
                  </span>
                  <span class="text-[10px] text-slate-400 font-semibold">${formatDate(event.timestamp)}</span>
                </div>
                <div class="mt-1 text-xs font-semibold text-slate-700">${escapeHtml(event.actor)}</div>
                ${event.comment ? `
                  <div class="audit-comment-bubble ${bubbleClass}">
                    <strong>Remark:</strong> "${escapeHtml(event.comment)}"
                  </div>
                ` : ""}
              </div>
            `;
          }).join("")}
        </div>
      `;
    } catch (err) {
      timeline.innerHTML = `<div class="text-xs text-rose-500 py-2 font-semibold">Error: ${escapeHtml(err.message)}</div>`;
    }
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

  function renderLegend() {
    legendItems.innerHTML = Object.entries(window.WorkbookSheet.CELL_STATE_META)
      .map(([state, meta]) => `<span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-bold ${meta.className}" data-state="${state}">${escapeHtml(meta.label)}</span>`)
      .join("");
    cellStateLegend.classList.remove("hidden");
  }

  function renderSheet(sheet) {
    loadSheetAuditLogs(sheet.submission_id);
    sheetTitle.textContent = sheet.form_name;
    sheetMeta.textContent = `Full FY context · Submitted month highlighted · Submitted by ${sheet.submitted_by} on ${formatDate(sheet.submitted_at)}`;
    sheetStatus.className = `inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${getStatusClass(sheet.status)}`;
    sheetStatus.classList.remove("hidden");
    sheetStatus.textContent = sheet.status;
    sheetFallbackLink.classList.remove("hidden");
    sheetFallbackLink.href = `/module/APPROV/packages/${packageId}?sheet=${encodeURIComponent(sheet.form_id)}#sheet-${sheet.submission_id}`;
    sheetFallbackLink.dataset.submissionId = String(sheet.submission_id);
    sheetFallbackLink.dataset.formId = String(sheet.form_id);

    const fields = [...(sheet.fields || [])].sort(
      (a, b) => (a.display_order || 0) - (b.display_order || 0)
    );

    if (!fields.length) {
      sheetHead.innerHTML = "";
      sheetValues.innerHTML = `
        <tr>
          <td colspan="2" class="px-5 py-8 text-center text-slate-400 italic">No fields configured for this form.</td>
        </tr>
      `;
      return;
    }

    window.WorkbookSheet.render({
      mode: "review",
      headEl: sheetHead,
      bodyEl: sheetValues,
      fields,
      sections: sheet.sections || [],
      workbookValues: sheet.workbook_values || {},
      canEditWorkbookValues: false,
      rows: sheet.rows || [{
        row_key: `submission-${sheet.submission_id}`,
        label: reviewData.package.period_label,
        period_label: sheet.form_name,
        status: sheet.status,
        submission_status: sheet.status,
        submission_id: sheet.submission_id,
        submitted_at: sheet.submitted_at,
        values: sheet.values || {},
        proofs: sheet.proofs || {},
        editable: false,
        is_active_period: true,
      }],
      selectedRowKey: sheet.active_row_key || null,
      onCellOpen: openCellIssueModal
    });
  }

  function renderTabs() {
    formTabs.innerHTML = "";
    reviewData.sheets.forEach((sheet, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.id = `sheet-tab-${sheet.submission_id}`;
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

  function focusSheet(index, updateUrl = true) {
    if (!reviewData || !reviewData.sheets[index]) return;
    activeSheetIndex = index;
    renderTabs();
    renderSheet(reviewData.sheets[activeSheetIndex]);
    const activeSheet = document.getElementById("active-sheet");
    if (activeSheet) {
      activeSheet.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (updateUrl && window.history && window.history.replaceState) {
      const sheet = reviewData.sheets[activeSheetIndex];
      const url = `/module/APPROV/packages/${packageId}?sheet=${encodeURIComponent(sheet.form_id)}#sheet-${sheet.submission_id}`;
      window.history.replaceState(null, "", url);
    }
  }

  function renderReview(data) {
    reviewData = data;
    const pkg = data.package;
    if (requestedSheet) {
      const requestedIndex = data.sheets.findIndex((sheet) => (
        String(sheet.form_id) === String(requestedSheet) ||
        String(sheet.submission_id) === String(requestedSheet)
      ));
      if (requestedIndex >= 0) activeSheetIndex = requestedIndex;
    }

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

  function activeSheet() {
    return reviewData && reviewData.sheets ? reviewData.sheets[activeSheetIndex] : null;
  }

  function activeField(fieldCode) {
    const sheet = activeSheet();
    if (!sheet) return null;
    return (sheet.fields || []).find((field) => String(field.field_code) === String(fieldCode)) || null;
  }

  function activeCellIssues(fieldCode) {
    const sheet = activeSheet();
    if (!sheet || !window.WorkbookSheet) return [];
    const activeRow = (sheet.rows || []).find((row) => row.row_key === sheet.active_row_key);
    return window.WorkbookSheet.cellIssues(
      activeRow || { values: sheet.values || {}, issues: sheet.issues || {} },
      activeField(fieldCode) || { field_code: fieldCode }
    );
  }

  function renderCellIssueList(issues) {
    if (!issues.length) {
      cellIssueList.innerHTML = '<div class="rounded-lg bg-slate-50 px-3 py-2 text-slate-400">No comments for this cell yet.</div>';
      return;
    }
    const canResolve = Boolean(selectedIssueCell && selectedIssueCell.canAddIssues);
    cellIssueList.innerHTML = issues.map((issue) => {
      const isResolved = issue.status === "Resolved";
      const statusBadge = isResolved
        ? `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 ml-1.5">Resolved</span>`
        : "";
      const resolveBtn = (!isResolved && canResolve)
        ? `<button class="resolve-cell-issue-btn mt-2 inline-flex items-center px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-bold rounded-lg transition-all" data-id="${issue.id}">Resolve</button>`
        : "";
      return `
        <div class="rounded-lg border border-amber-100 bg-amber-50 px-3 py-2">
          <div class="text-xs font-bold text-amber-900">${escapeHtml(issue.raised_by_name || "Reviewer")}${statusBadge}</div>
          <div class="mt-1 text-sm text-amber-800">${escapeHtml(issue.issue_text || "")}</div>
          ${resolveBtn}
        </div>
      `;
    }).join("");

    cellIssueList.querySelectorAll(".resolve-cell-issue-btn").forEach((btn) => {
      btn.onclick = function () {
        resolveCellIssue(parseInt(this.dataset.id, 10));
      };
    });
  }

  function resolveCellIssue(issueId) {
    if (!selectedIssueCell || !selectedIssueCell.canAddIssues) return;
    if (!confirm("Mark this cell issue as resolved?")) return;

    fetch(`/module/APPROV/api/packages/${packageId}/values/${selectedIssueCell.submissionValueId}/issues/${issueId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    })
      .then((res) => res.json().then((data) => {
        if (!res.ok) throw new Error(data.error || "Could not resolve cell issue.");
        return data;
      }))
      .then((data) => {
        const resolved = data.data && data.data.issue;
        const sheet = activeSheet();
        const field = activeField(selectedIssueCell.fieldCode);
        if (resolved && sheet && field) {
          const row = (sheet.rows || []).find((item) => item.row_key === selectedIssueCell.rowKey);
          const source = row || sheet;
          const cell = source.values ? source.values[field.field_code] : null;
          if (cell && typeof cell === "object" && Array.isArray(cell.issues)) {
            const idx = cell.issues.findIndex((i) => i.id === resolved.id);
            if (idx !== -1) cell.issues[idx] = resolved;
          }
        }
        renderCellIssueList(activeCellIssues(selectedIssueCell.fieldCode));
      })
      .catch((err) => showCellIssueError(err.message));
  }

  function openCellIssueModal(cellInfo) {
    const field = activeField(cellInfo.fieldCode);
    const actions = reviewData.package.actions || {};
    const canAddIssues = Boolean(actions.can_add_issues && cellInfo.submissionValueId);
    selectedIssueCell = {
      submissionValueId: cellInfo.submissionValueId,
      fieldCode: cellInfo.fieldCode,
      rowKey: cellInfo.rowKey,
      canAddIssues,
    };
    cellIssueContext.textContent = `${activeSheet() ? activeSheet().form_name : "Sheet"} · ${cellInfo.rowLabel} · ${field ? field.field_name : cellInfo.fieldCode}`;
    cellIssueValue.textContent = cellInfo.value || "Empty";
    cellIssueState.textContent = `${cellInfo.cellStateLabel}${cellInfo.locked ? " · Locked" : ""}`;
    cellIssueText.value = "";
    cellIssueError.classList.add("hidden");
    renderCellIssueList(cellInfo.issues || activeCellIssues(cellInfo.fieldCode));
    cellIssueAddSection.classList.toggle("hidden", !canAddIssues);
    btnSaveCellIssue.classList.toggle("hidden", !canAddIssues);
    cellIssueModal.classList.remove("hidden");
    cellIssueModal.classList.add("flex");
    if (canAddIssues) cellIssueText.focus();
  }

  function closeCellIssueModal() {
    selectedIssueCell = null;
    cellIssueModal.classList.add("hidden");
    cellIssueModal.classList.remove("flex");
  }

  function showCellIssueError(message) {
    cellIssueError.textContent = message;
    cellIssueError.classList.remove("hidden");
  }

  function saveCellIssue() {
    if (!selectedIssueCell || !selectedIssueCell.canAddIssues) return;
    const issueText = cellIssueText.value.trim();
    if (!issueText) {
      showCellIssueError("Enter a comment before saving.");
      return;
    }
    btnSaveCellIssue.disabled = true;
    btnSaveCellIssue.textContent = "Saving...";
    fetch(`/module/APPROV/api/packages/${packageId}/values/${selectedIssueCell.submissionValueId}/issues`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ issue_text: issueText }),
    })
      .then((res) => {
        return res.json().then((data) => {
          if (!res.ok) throw new Error(data.error || "Could not save cell comment.");
          return data;
        });
      })
      .then((data) => {
        const issue = data.data && data.data.issue;
        const valueId = selectedIssueCell.submissionValueId;
        const sheet = activeSheet();
        const field = activeField(selectedIssueCell.fieldCode);
        if (issue && sheet && field) {
          const row = (sheet.rows || []).find((item) => item.row_key === selectedIssueCell.rowKey);
          const source = row || sheet;
          const cell = source.values ? source.values[field.field_code] : null;
          if (cell && typeof cell === "object") {
            if (!Array.isArray(cell.issues)) cell.issues = [];
            cell.issues.push(issue);
          }
        }
        const fieldCode = selectedIssueCell.fieldCode;
        closeCellIssueModal();
        renderSheet(activeSheet());
        const refreshedField = activeField(fieldCode);
        if (refreshedField) {
          const selector = `[data-submission-value-id="${valueId}"]`;
          const cellEl = sheetValues.querySelector(selector);
          if (cellEl) cellEl.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
        }
      })
      .catch((err) => showCellIssueError(err.message))
      .finally(() => {
        btnSaveCellIssue.disabled = false;
        btnSaveCellIssue.textContent = "Save comment";
      });
  }

  [btnCloseCellIssue, btnCancelCellIssue].forEach((button) => {
    if (button) button.addEventListener("click", closeCellIssueModal);
  });
  if (cellIssueModal) {
    cellIssueModal.addEventListener("click", function (event) {
      if (event.target === cellIssueModal) closeCellIssueModal();
    });
  }
  if (btnSaveCellIssue) btnSaveCellIssue.addEventListener("click", saveCellIssue);

  if (sheetFallbackLink) {
    sheetFallbackLink.addEventListener("click", function (event) {
      event.preventDefault();
      if (!reviewData) return;
      const index = reviewData.sheets.findIndex((sheet) => (
        String(sheet.submission_id) === String(sheetFallbackLink.dataset.submissionId) ||
        String(sheet.form_id) === String(sheetFallbackLink.dataset.formId)
      ));
      focusSheet(index >= 0 ? index : activeSheetIndex);
    });
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
