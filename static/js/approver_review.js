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
      case "Approved": return "bg-emerald-100 text-emerald-800 border border-emerald-200";
      case "Under Review": return "bg-indigo-100 text-indigo-800 border border-indigo-200";
      case "Changes Requested": return "bg-amber-100 text-amber-800 border border-amber-200";
      case "Rejected": return "bg-rose-100 text-rose-800 border border-rose-200";
      default: return "bg-slate-100 text-slate-800 border border-slate-200";
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
        reviewSubtitle.textContent = `Site: ${data.metadata.site_name} · Period: ${data.metadata.period_label} · Submitted by ${data.metadata.submitted_by} on ${formatDate(data.metadata.submitted_at)}`;
        
        badgeStatus.className = `inline-flex items-center px-3 py-1 rounded-full text-xs font-bold ${getStatusClass(data.metadata.status)}`;
        badgeStatus.textContent = data.metadata.status;

        // Hide action controls if already Approved or Rejected
        if (data.metadata.status === "Approved" || data.metadata.status === "Rejected") {
          const actionsPanel = document.getElementById("actions-panel");
          if (actionsPanel) {
            actionsPanel.innerHTML = `<div class="text-center py-4 text-slate-500 italic text-sm border-2 border-dashed border-slate-200 rounded-lg">Submission is locked (${data.metadata.status}). No review actions required.</div>`;
          }
          if (btnRaiseIssueModal) btnRaiseIssueModal.classList.add("hidden");
        }

        // 2. Render Form in readonly_review mode
        // Prepare values map and proofs map
        const valuesMap = {};
        const proofsMap = {};
        
        data.fields.forEach((field) => {
          const valObj = data.values[field.field_id];
          if (valObj) {
            if (field.field_type === "calculated") {
              valuesMap[field.field_code] = valObj.calculated_value;
            } else {
              valuesMap[field.field_code] = valObj.raw_value;
            }
          }
          
          const proofObj = data.proofs[field.field_id];
          if (proofObj) {
            valuesMap[field.field_code] = {
              storage_key: proofObj.storage_key,
              original_name: proofObj.original_name
            };
          }
        });

        if (window.renderForm) {
          window.renderForm(data.fields, formContainer, "readonly_review", valuesMap);
        }

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
      } else if (submissionData && submissionData.metadata.status === "Under Review") {
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
    if (actions.length === 0) {
      workflowLog.innerHTML = `<li class="text-slate-400 italic text-xs py-2">No workflow actions recorded yet.</li>`;
      return;
    }

    actions.forEach((act, idx) => {
      const li = document.createElement("li");
      li.className = "relative pb-8";
      
      const isLast = idx === actions.length - 1;
      const timelineLine = isLast ? "" : '<span class="absolute top-4 left-4 -ml-px h-full w-0.5 bg-slate-200" aria-hidden="true"></span>';

      let actionColorClass = "bg-slate-400";
      if (act.action === "Approve") actionColorClass = "bg-emerald-500";
      else if (act.action === "Request Changes") actionColorClass = "bg-amber-500";
      else if (act.action === "Reject") actionColorClass = "bg-rose-500";

      li.innerHTML = `
        <div class="relative flex space-x-3">
          ${timelineLine}
          <div>
            <span class="h-8 w-8 rounded-full ${actionColorClass} flex items-center justify-center ring-8 ring-white text-white">
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4" />
              </svg>
            </span>
          </div>
          <div class="flex-1 min-w-0 pt-1.5 flex justify-between space-x-4">
            <div>
              <p class="text-xs text-slate-500">${act.action} by <span class="font-bold text-slate-800">${act.actor_name}</span> at level ${act.level_number}</p>
              ${act.comment ? `<p class="mt-1 text-xs text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-100 italic">"${act.comment}"</p>` : ""}
            </div>
            <div class="text-right text-[10px] whitespace-nowrap text-slate-400">
              <time>${formatDate(act.acted_at)}</time>
            </div>
          </div>
        </div>
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
      if (!comment || !comment.strip || !comment.strip()) {
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
          alert("Submission returned to SPOC for changes.");
          window.location.href = "/module/APPROV/";
        })
        .catch(err => alert(err.message));
    };
  }

  if (btnReject) {
    btnReject.onclick = function () {
      const comment = commentInput.value;
      if (!comment || !comment.strip || !comment.strip()) {
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
