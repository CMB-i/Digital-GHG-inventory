document.addEventListener("DOMContentLoaded", function () {
  const submissionId = window.SUBMISSION_ID;
  if (!submissionId) return;

  const reviewTitle = document.getElementById("review-title");
  const reviewSubtitle = document.getElementById("review-subtitle");
  const badgeStatus = document.getElementById("badge-status");
  const formContainer = document.getElementById("form-container");
  const issuesList = document.getElementById("issues-list");
  const workflowLog = document.getElementById("workflow-log");
  const commentInput = document.getElementById("review-comment");
  const issueFieldSelect = document.getElementById("issue-field");

  // Buttons
  const btnApprove = document.getElementById("btn-approve");
  const btnRequestChanges = document.getElementById("btn-request-changes");
  const btnReject = document.getElementById("btn-reject");
  const btnRaiseIssueModal = document.getElementById("btn-raise-issue-modal");
  const btnCloseIssueModal = document.getElementById("btn-close-issue-modal");
  const btnCancelIssue = document.getElementById("btn-cancel-issue");
  const issueModal = document.getElementById("issue-modal");
  const issueForm = document.getElementById("issue-form");

  let submissionData = null;
  const reviewableStatuses = new Set(["Submitted", "Resubmitted", "Under Review"]);

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

  function getStatusClass(status) {
    switch (status) {
      case "Approved": return "ghg-status ghg-status-success";
      case "Under Review": return "ghg-status ghg-status-info";
      case "Submitted":
      case "Resubmitted": return "ghg-status ghg-status-info";
      case "Changes Requested": return "ghg-status ghg-status-warning";
      case "Rejected": return "ghg-status ghg-status-danger";
      default: return "ghg-status ghg-status-neutral";
    }
  }

  const escapeHtml = window.WorkbookSheet.escapeHtml;

  function renderSubmissionTable(data) {
    const rows = Array.isArray(data.rows) && data.rows.length
      ? data.rows
      : (() => {
          const valuesByCode = {};
          (data.fields || []).forEach((field) => {
            valuesByCode[field.field_code] = data.values ? data.values[field.field_id] : null;
          });
          return [{
            row_key: `submission-${submissionId}`,
            label: data.metadata.period_label || "Submission",
            period_label: data.metadata.form_name || "",
            status: data.metadata.status,
            submission_status: data.metadata.status,
            submission_id: data.metadata.submission_id,
            values: valuesByCode,
            proofs: data.proofs || {},
            is_locked: data.metadata.is_locked,
            editable: false,
            is_active_period: true,
          }];
        })();

    window.WorkbookSheet.render({
      mode: "review",
      headEl: document.getElementById("review-sheet-head"),
      bodyEl: document.getElementById("review-sheet-body"),
      fields: data.fields || [],
      sections: data.sections || [],
      workbookValues: data.workbook_values || {},
      rows,
      selectedRowKey: rows.find(row => row.is_active_period)?.row_key || null,
    });

    const activeRow = rows.find(row => row.is_active_period);
    if (activeRow) {
      const key = window.WorkbookSheet.rowKey(activeRow);
      const rowEl = Array.from(document.getElementById("review-sheet-body")?.querySelectorAll("tr[data-row-key]") || [])
        .find(row => row.dataset.rowKey === key);
      if (rowEl) rowEl.classList.add("approver-reviewed-month-row");
    }
  }

  function loadSubmissionDetails() {
    fetch(`/module/APPROV/api/submissions/${submissionId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load submission details.");
        return res.json();
      })
      .then((resData) => {
        const data = resData.data;
        submissionData = data;

        // 1. Titles & Status
        reviewTitle.textContent = `${data.metadata.form_name}`;
        reviewSubtitle.textContent = `${data.metadata.site_name} · ${data.metadata.period_label} · Submitted by ${data.metadata.submitted_by || "—"} · ${formatDate(data.metadata.submitted_at)}`;

        badgeStatus.className = `inline-flex w-max items-center px-3 py-1 text-xs font-bold ${getStatusClass(data.metadata.status)}`;
        badgeStatus.textContent = data.metadata.status;

        // Surface calculated-field formula errors flagged at submit time -- the raw
        // data was allowed through, but a stored calculated value may be wrong.
        const existingRecalcBanner = document.getElementById("recalc-review-banner");
        if (existingRecalcBanner) existingRecalcBanner.remove();
        if (data.metadata.needs_recalc_review && reviewSubtitle) {
          const banner = document.createElement("div");
          banner.id = "recalc-review-banner";
          banner.className = "mt-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2";
          const text = document.createElement("span");
          text.textContent = "Needs recalculation review: one or more calculated fields had formula errors when this was submitted."
            + (data.metadata.recalc_review_notes ? ` (${data.metadata.recalc_review_notes})` : "")
            + " This must be cleared before final approval.";
          banner.appendChild(text);

          if (reviewableStatuses.has(data.metadata.status)) {
            const clearBtn = document.createElement("button");
            clearBtn.className = "clear-recalc-review-btn inline-flex items-center px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-bold rounded-lg transition-all";
            clearBtn.textContent = "Confirm value is acceptable";
            clearBtn.onclick = () => {
              if (!confirm("Confirm the calculated value is acceptable and clear the recalculation review flag?")) return;

              fetch(`/module/APPROV/api/submissions/${submissionId}/clear-recalc-review`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
              })
                .then((res) => {
                  if (!res.ok) return res.json().then(d => { throw new Error(d.error); });
                  return res.json();
                })
                .then(() => {
                  loadSubmissionDetails();
                })
                .catch(err => alert(err.message));
            };
            banner.appendChild(clearBtn);
          }

          reviewSubtitle.insertAdjacentElement("afterend", banner);
        }

        // Hide action controls if already Approved, Rejected, or Changes Requested
        if (data.metadata.status === "Approved" || data.metadata.status === "Rejected" || data.metadata.status === "Changes Requested") {
          const actionsPanel = document.getElementById("actions-panel");
          if (actionsPanel) {
            if (data.metadata.status === "Changes Requested") {
              if (data.metadata.can_resubmit) {
                actionsPanel.innerHTML = `
                  <div class="space-y-4 text-center">
                    <div class="p-4 bg-amber-50 border border-amber-200 text-amber-800 text-xs font-bold rounded-lg leading-relaxed">
                      Changes have been requested for this submission.
                    </div>
                    <a href="/module/SUBMIT/submissions/${submissionId}" class="w-full inline-flex justify-center items-center px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-bold rounded-lg shadow-sm hover:shadow transition-all">
                      Edit Entry &amp; Resubmit
                    </a>
                  </div>
                `;
              } else {
                actionsPanel.innerHTML = `
                  <div class="text-center py-4 text-slate-500 italic text-sm border-2 border-dashed border-slate-200 rounded-lg leading-relaxed">
                    Changes have been requested from the submitter. Awaiting resubmission.
                  </div>
                `;
              }
            } else {
              actionsPanel.innerHTML = `<div class="text-center py-4 text-slate-500 italic text-sm border-2 border-dashed border-slate-200 rounded-lg">Submission is locked (${data.metadata.status}). No review actions required.</div>`;
            }
          }
          if (btnRaiseIssueModal) btnRaiseIssueModal.classList.add("hidden");
        }

        // 2. Render entered data in workbook-style cells.
        renderSubmissionTable(data);

        // 3. Populate dropdown fields in Raise Issue Modal
        issueFieldSelect.innerHTML = '<option value="">General Submission Issue (No specific field)</option>';
        data.fields.forEach((f) => {
          const opt = document.createElement("option");
          opt.value = f.field_id;
          opt.textContent = f.field_name;
          issueFieldSelect.appendChild(opt);
        });

        // 4. Populate Issues List
        renderIssues(data.issues);

        // 5. Populate Workflow Audit Log
        renderWorkflowLog(data.actions);
      })
      .catch((err) => {
        console.error(err);
        formContainer.innerHTML = `<div class="text-rose-500 font-bold italic py-8 text-center">${err.message}</div>`;
      });
  }

  function renderIssues(issues) {
    issuesList.innerHTML = "";
    if (issues.length === 0) {
      issuesList.innerHTML = `<li class="py-3 text-slate-400 italic text-sm text-center">No issues raised on this submission yet.</li>`;
      return;
    }

    issues.forEach((issue) => {
      const li = document.createElement("li");
      li.className = "py-4 flex flex-col sm:flex-row sm:items-start justify-between gap-4";

      const hasField = issue.field_id;
      let fieldBadge = "";
      if (hasField && submissionData) {
        const field = submissionData.fields.find(f => f.field_id === issue.field_id);
        if (field) {
          fieldBadge = `<span class="bg-indigo-50 text-indigo-700 text-[10px] px-1.5 py-0.5 rounded font-bold border border-indigo-100 mr-2">${field.field_name}</span>`;
        }
      }

      let statusBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">Open</span>`;
      let resolveBtn = "";

      if (issue.status === "Resolved") {
        statusBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">Resolved</span>`;
      } else if (submissionData && reviewableStatuses.has(submissionData.metadata.status)) {
        resolveBtn = `
          <button class="resolve-btn inline-flex items-center px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 text-xs font-bold rounded-lg transition-all" data-id="${issue.id}">
            Resolve
          </button>
        `;
      }

      li.innerHTML = `
        <div class="space-y-1">
          <div class="flex items-center flex-wrap gap-1">
            ${statusBadge}
            <span class="font-bold text-slate-900 ml-1.5">${issue.title}</span>
          </div>
          <p class="text-xs text-slate-500 pl-1">${issue.description}</p>
          <div class="text-[10px] text-slate-400 pl-1 pt-1">
            ${fieldBadge}
          </div>
        </div>
        <div class="flex-shrink-0 self-center">
          ${resolveBtn}
        </div>
      `;
      issuesList.appendChild(li);
    });

    // Add listeners to resolve buttons
    document.querySelectorAll(".resolve-btn").forEach((btn) => {
      btn.onclick = function () {
        const issueId = this.dataset.id;
        if (!confirm("Are you sure you want to resolve this issue?")) return;

        fetch(`/module/APPROV/api/issues/${issueId}/resolve`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        })
          .then((res) => {
            if (!res.ok) return res.json().then(d => { throw new Error(d.error); });
            return res.json();
          })
          .then(() => {
            loadSubmissionDetails();
          })
          .catch(err => alert(err.message));
      };
    });
  }

  function renderWorkflowLog(actions) {
    workflowLog.innerHTML = "";
    const events = [];
    if (submissionData && submissionData.metadata && submissionData.metadata.submitted_at) {
      events.push({
        action: "Submitted",
        actor_name: submissionData.metadata.submitted_by || "Submitter",
        acted_at: submissionData.metadata.submitted_at,
        comment: "",
      });
    }
    (actions || []).forEach((act) => {
      const label = {
        Approve: "Approved",
        "Request Changes": "Changes Requested",
        Reject: "Rejected",
      }[act.action] || act.action;
      events.push({ ...act, action: label });
    });

    if (events.length === 0) {
      workflowLog.innerHTML = `<li class="text-slate-400 italic text-xs py-2">No workflow actions recorded yet.</li>`;
      return;
    }

    events.forEach((act) => {
      const li = document.createElement("li");
      const actionKey = String(act.action || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
      li.className = "audit-timeline-item";

      let dotClass = "dot-submitted";
      if (act.action === "Approved") dotClass = "dot-approved";
      else if (act.action === "Changes Requested") dotClass = "dot-changes-requested";
      else if (act.action === "Rejected") dotClass = "dot-rejected";

      li.innerHTML = `
        <span class="audit-timeline-dot ${dotClass}" aria-hidden="true"></span>
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <div class="inline-flex items-center border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide audit-action-badge audit-action-${escapeHtml(actionKey)}">
              ${escapeHtml(act.action || "Action")}
            </div>
            <div class="mt-1 text-xs font-bold text-slate-800">${escapeHtml(act.actor_name || "Unknown actor")}</div>
            ${act.level_number ? `<div class="mt-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Level ${escapeHtml(act.level_number)}</div>` : ""}
          </div>
          <time class="shrink-0 text-right text-[10px] font-semibold text-slate-400">${formatDate(act.acted_at)}</time>
        </div>
        ${act.comment ? `
          <div class="audit-comment-bubble border-slate-200 bg-slate-50 text-slate-600">
            ${escapeHtml(act.comment)}
          </div>
        ` : ""}
      `;
      workflowLog.appendChild(li);
    });
  }

  // Action listeners
  if (btnApprove) {
    btnApprove.onclick = function () {
      const comment = commentInput.value;
      if (!confirm("Are you sure you want to approve this submission?")) return;

      fetch(`/module/APPROV/api/submissions/${submissionId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: comment })
      })
        .then((res) => {
          if (!res.ok) return res.json().then(d => { throw new Error(d.error); });
          return res.json();
        })
        .then((data) => {
          alert("Submission approved successfully!");
          window.location.href = "/module/APPROV/";
        })
        .catch(err => alert(err.message));
    };
  }

  if (btnRequestChanges) {
    btnRequestChanges.onclick = function () {
      const comment = commentInput.value;
      if (!comment || !comment.trim()) {
        alert("A review comment is required to request changes.");
        commentInput.focus();
        return;
      }

      if (!confirm("Are you sure you want to return this submission for changes?")) return;

      fetch(`/module/APPROV/api/submissions/${submissionId}/request-changes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: comment })
      })
        .then((res) => {
          if (!res.ok) return res.json().then(d => { throw new Error(d.error); });
          return res.json();
        })
        .then((data) => {
          alert("Submission returned for changes.");
          window.location.href = "/module/APPROV/";
        })
        .catch(err => alert(err.message));
    };
  }

  if (btnReject) {
    btnReject.onclick = function () {
      const comment = commentInput.value;
      if (!comment || !comment.trim()) {
        alert("A review comment is required to reject a submission.");
        commentInput.focus();
        return;
      }

      if (!confirm("CAUTION: Are you sure you want to permanently REJECT this submission? This action is terminal and will lock the sheet.")) return;

      fetch(`/module/APPROV/api/submissions/${submissionId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment: comment })
      })
        .then((res) => {
          if (!res.ok) return res.json().then(d => { throw new Error(d.error); });
          return res.json();
        })
        .then((data) => {
          alert("Submission rejected permanently.");
          window.location.href = "/module/APPROV/";
        })
        .catch(err => alert(err.message));
    };
  }

  // Issue Modal Actions
  if (btnRaiseIssueModal) {
    btnRaiseIssueModal.onclick = () => {
      issueForm.reset();
      issueModal.classList.remove("hidden");
      issueModal.classList.add("flex");
    };
  }

  function hideIssueModal() {
    issueModal.classList.remove("flex");
    issueModal.classList.add("hidden");
  }

  if (btnCloseIssueModal) btnCloseIssueModal.onclick = hideIssueModal;
  if (btnCancelIssue) btnCancelIssue.onclick = hideIssueModal;

  if (issueForm) {
    issueForm.onsubmit = function (e) {
      e.preventDefault();
      const fId = document.getElementById("issue-field").value;
      const title = document.getElementById("issue-title").value;
      const desc = document.getElementById("issue-desc").value;

      fetch(`/module/APPROV/api/submissions/${submissionId}/raise-issue`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          field_id: fId ? parseInt(fId) : null,
          title: title,
          description: desc
        })
      })
        .then((res) => {
          if (!res.ok) return res.json().then(d => { throw new Error(d.error); });
          return res.json();
        })
        .then(() => {
          hideIssueModal();
          loadSubmissionDetails();
        })
        .catch(err => alert(err.message));
    };
  }

  // Load details
  loadSubmissionDetails();
});
