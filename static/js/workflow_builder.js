document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const listView = document.getElementById("list-view");
  const editorView = document.getElementById("editor-view");
  const workflowsListBody = document.getElementById("workflows-list-body");

  // Editor Inputs
  const dfName = document.getElementById("df-name");
  const dfCode = document.getElementById("df-code");
  const editorTitle = document.getElementById("editor-title");
  const editorVersionBadge = document.getElementById("editor-version-badge");
  
  // Workspace Card and Level containers
  const levelsContainer = document.getElementById("levels-container");
  const btnAddLevel = document.getElementById("btn-add-level");
  const btnSaveDraft = document.getElementById("btn-save-draft");
  const validationErrors = document.getElementById("validation-errors");
  const versionActions = document.getElementById("version-actions");

  // Create workflow modal
  const modalCreateWorkflow = document.getElementById("modal-create-workflow");
  const btnCloseWorkflowModal = document.getElementById("btn-close-workflow-modal");
  const btnCancelWorkflowModal = document.getElementById("btn-cancel-workflow-modal");
  const formCreateWorkflow = document.getElementById("form-create-workflow");

  // State
  let workflows = [];
  let currentWorkflowId = null;
  let currentVersionId = null;
  let currentVersion = null;
  let levelsList = [];
  let availableUsers = [];
  let hasUnsavedChanges = false;
  let permissions = {
    can_edit: false,
    can_publish: false,
    can_create_version: false
  };

  // Toast Helper
  function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `p-4 rounded-xl shadow-lg border text-xs font-bold transition-all duration-300 transform translate-y-2 opacity-0 flex items-center justify-between ${
      type === "success" 
        ? "bg-emerald-50 border-emerald-200 text-emerald-800" 
        : "bg-rose-50 border-rose-200 text-rose-800"
    }`;
    toast.innerHTML = `
      <span>${message}</span>
      <button class="ml-4 font-normal text-slate-400 hover:text-slate-600">✕</button>
    `;
    toast.querySelector("button").onclick = () => toast.remove();
    container.appendChild(toast);
    
    setTimeout(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
    }, 10);
    
    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // --- View Switching ---
  window.showList = function () {
    if (hasUnsavedChanges && !confirm("You have unsaved changes. Discard and return to list?")) {
      return;
    }
    editorView.classList.add("hidden");
    listView.classList.remove("hidden");
    loadWorkflows();
  };

  window.startNewWorkflow = function () {
    modalCreateWorkflow.classList.remove("hidden");
  };

  window.editWorkflow = function (workflowId, versionId) {
    currentWorkflowId = workflowId;
    currentVersionId = versionId;
    
    listView.classList.add("hidden");
    editorView.classList.remove("hidden");
    
    loadVersionDetails(versionId);
  };

  // --- Modal actions ---
  const hideModal = () => {
    modalCreateWorkflow.classList.add("hidden");
    formCreateWorkflow.reset();
  };
  btnCloseWorkflowModal.onclick = hideModal;
  btnCancelWorkflowModal.onclick = hideModal;

  formCreateWorkflow.onsubmit = async (e) => {
    e.preventDefault();
    const name = document.getElementById("new-workflow-name").value.trim();
    const code = document.getElementById("new-workflow-code").value.trim().toUpperCase().replace(/\s+/g, "_");

    // Client-side check to prevent duplicate workflow creation
    const existing = workflows.find(w => w.code === code);
    if (existing) {
      showToast(`Workflow with code '${code}' already exists.`, "error");
      return;
    }

    const submitBtn = formCreateWorkflow.querySelector("button[type='submit']");
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.textContent = "Creating...";

    try {
      const res = await fetch("/module/WFLWBLD/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, code })
      });
      const data = await res.json();
      if (res.ok) {
        showToast("Workflow created successfully!");
        hideModal();
        // Reload list, find new workflow, and open it
        const resList = await fetch("/module/WFLWBLD/api");
        const listData = await resList.json();
        const found = listData.find(x => x.code === code);
        if (found && found.latest_version_id) {
          editWorkflow(found.id, found.latest_version_id);
        } else {
          showList();
        }
      } else {
        showToast("Error: " + (data.error || "Unknown error occurred"), "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to create workflow.", "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
  };

  // --- Load Workflows ---
  async function loadWorkflows() {
    workflowsListBody.innerHTML = '<tr><td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">Loading workflows...</td></tr>';
    
    try {
      const res = await fetch("/module/WFLWBLD/api");
      const data = await res.json();
      workflows = data;
      workflowsListBody.innerHTML = "";

      if (data.length === 0) {
        workflowsListBody.innerHTML = `
          <tr>
            <td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">
              No workflows configured yet. Click "Create Workflow" to get started.
            </td>
          </tr>
        `;
        return;
      }

      data.forEach(item => {
        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50/50 transition-colors";

        let statusBadge = "";
        const status = item.latest_version_status || "Draft";
        if (status === "Published") {
          statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 uppercase">Published</span>';
        } else {
          statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 uppercase">Draft</span>';
        }

        let actions = [];
        if (item.latest_version_id) {
          actions.push(`<button onclick="editWorkflow(${item.id}, ${item.latest_version_id})" class="text-indigo-600 hover:text-indigo-900 font-bold hover:underline">Edit / Details</button>`);
        }

        tr.innerHTML = `
          <td class="px-6 py-4 font-bold text-slate-800">${item.name}</td>
          <td class="px-6 py-4 font-mono text-slate-500">${item.code}</td>
          <td class="px-6 py-4 text-slate-500 font-bold">${item.levels_count || 0} stages</td>
          <td class="px-6 py-4">${statusBadge}</td>
          <td class="px-6 py-4 text-right whitespace-nowrap">${actions.join("")}</td>
        `;
        workflowsListBody.appendChild(tr);
      });
    } catch (err) {
      console.error(err);
      showToast("Error loading workflows list.", "error");
    }
  }

  // --- Load Version Details ---
  async function loadVersionDetails(verId) {
    try {
      const res = await fetch(`/module/WFLWBLD/api/version/${verId}`);
      if (!res.ok) throw new Error("Failed to load details");
      const data = await res.json();

      currentVersionId = verId;
      currentVersion = data.version;
      levelsList = data.levels || [];
      availableUsers = data.available_users || [];
      permissions = data.permissions || {};
      hasUnsavedChanges = false;

      dfName.value = data.workflow.name;
      dfCode.value = data.workflow.code;
      dfCode.disabled = true;

      editorTitle.textContent = `Edit Workflow · ${data.workflow.name}`;
      
      let badgeClass = "bg-amber-100 text-amber-800";
      let statusLabel = "Draft";
      if (currentVersion.status === "Published") {
        badgeClass = "bg-emerald-100 text-emerald-800";
        statusLabel = "Published";
      }
      editorVersionBadge.textContent = `v${currentVersion.version_number} (${statusLabel})`;
      editorVersionBadge.className = `px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${badgeClass}`;

      renderWorkspace();
    } catch (err) {
      console.error(err);
      showToast("Error loading workflow version details.", "error");
    }
  }

  // --- Render workspace levels sequence ---
  function renderWorkspace() {
    // Render level node boxes
    levelsContainer.innerHTML = "";
    const isEditable = permissions.can_edit;

    if (levelsList.length === 0) {
      levelsContainer.innerHTML = `
        <div class="text-center py-12 border border-dashed border-slate-200 rounded-xl text-slate-400 text-xs italic">
          No approval stages configured yet. Click "+ Add Stage" to design your sequence.
        </div>
      `;
    } else {
      levelsList.forEach((lvl, levelIdx) => {
        const node = renderLevelNode(lvl, levelIdx, isEditable);
        levelsContainer.appendChild(node);
      });
    }

    // Render action buttons
    versionActions.innerHTML = "";
    if (permissions.can_publish) {
      const btnPub = document.createElement("button");
      btnPub.className = "inline-flex items-center justify-center px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow transition";
      btnPub.textContent = "Publish Workflow";
      btnPub.onclick = publishVersion;
      versionActions.appendChild(btnPub);
    }
    if (permissions.can_create_version) {
      const btnNew = document.createElement("button");
      btnNew.className = "inline-flex items-center justify-center px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow transition";
      btnNew.textContent = "Create Draft Version";
      btnNew.onclick = createNewVersionDraft;
      versionActions.appendChild(btnNew);
    }

    // Add delete workflow button
    const btnDel = document.createElement("button");
    btnDel.className = "p-1.5 border border-rose-200 hover:bg-rose-50 text-rose-600 rounded-lg transition-colors";
    btnDel.innerHTML = `
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    `;
    btnDel.title = "Delete Workflow";
    btnDel.onclick = deleteWorkflow;
    versionActions.appendChild(btnDel);

    if (isEditable) {
      btnAddLevel.removeAttribute("disabled");
      btnSaveDraft.removeAttribute("disabled");
    } else {
      btnAddLevel.setAttribute("disabled", "true");
      btnSaveDraft.setAttribute("disabled", "true");
    }

    runValidation();
  }

  function renderLevelNode(lvl, levelIdx, isEditable) {
    const div = document.createElement("div");
    div.className = "p-4 border border-slate-200 bg-white rounded-xl shadow-sm space-y-4 relative hover:border-slate-300 transition";

    // Header row
    const header = document.createElement("div");
    header.className = "flex items-center justify-between pb-2.5 border-b border-slate-100 gap-4";
    
    const leftHeader = document.createElement("div");
    leftHeader.className = "flex items-center space-x-3";
    leftHeader.innerHTML = `
      <span class="flex items-center justify-center h-6 w-6 rounded-full bg-indigo-50 text-indigo-600 text-xs font-bold">
        ${lvl.level_number}
      </span>
      <input type="text" value="${lvl.level_name}" ${!isEditable ? "disabled" : ""} 
        class="form-input text-xs font-bold text-slate-700 border-slate-200 focus:border-indigo-500 rounded-lg px-2 py-1 max-w-[200px]" />
    `;

    const rightHeader = document.createElement("div");
    rightHeader.className = "flex items-center space-x-3";
    rightHeader.innerHTML = `
      <div class="flex items-center space-x-1.5">
        <label class="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Mode:</label>
        <select ${!isEditable ? "disabled" : ""} class="form-select text-[11px] rounded-lg border-slate-200 py-1 bg-white focus:border-indigo-500">
          <option value="ANY_ONE" ${lvl.approval_mode === "ANY_ONE" ? "selected" : ""}>ANY_ONE</option>
          <option value="SEQUENTIAL" ${lvl.approval_mode === "SEQUENTIAL" ? "selected" : ""}>SEQUENTIAL</option>
        </select>
      </div>
    `;

    if (isEditable) {
      const btnDel = document.createElement("button");
      btnDel.type = "button";
      btnDel.className = "text-slate-400 hover:text-rose-500 transition";
      btnDel.innerHTML = `
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
      `;
      btnDel.title = "Delete Level";
      btnDel.onclick = () => {
        levelsList.splice(levelIdx, 1);
        levelsList.forEach((l, idx) => l.level_number = idx + 1);
        hasUnsavedChanges = true;
        renderWorkspace();
      };
      rightHeader.appendChild(btnDel);
    } else {
      // Show Final Badge if this is final level
      if (levelIdx === levelsList.length - 1) {
        const finalBadge = document.createElement("span");
        finalBadge.className = "inline-flex items-center space-x-1 text-indigo-600 font-bold text-xs";
        finalBadge.innerHTML = `
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12l5 5 9-11"/></svg>
          <span>Final</span>
        `;
        rightHeader.appendChild(finalBadge);
      }
    }

    header.appendChild(leftHeader);
    header.appendChild(rightHeader);
    div.appendChild(header);

    // Bind level name input change
    leftHeader.querySelector("input").addEventListener("change", (e) => {
      lvl.level_name = e.target.value.trim() || `Level ${lvl.level_number}`;
      hasUnsavedChanges = true;
      runValidation();
    });

    // Bind mode change
    header.querySelector("select").addEventListener("change", (e) => {
      lvl.approval_mode = e.target.value;
      if (lvl.approval_mode === "SEQUENTIAL") {
        lvl.approvers.forEach((app, idx) => app.sequence_number = idx + 1);
      } else {
        lvl.approvers.forEach(app => app.sequence_number = null);
      }
      hasUnsavedChanges = true;
      renderWorkspace();
    });

    // Approvers lists
    const approversArea = document.createElement("div");
    approversArea.className = "space-y-2";
    
    const approverLabel = document.createElement("h4");
    approverLabel.className = "text-[9px] font-bold text-slate-400 uppercase tracking-wider";
    approverLabel.textContent = "Approvers assigned:";
    approversArea.appendChild(approverLabel);

    const appGrid = document.createElement("div");
    appGrid.className = "grid grid-cols-1 sm:grid-cols-2 gap-2";

    if (lvl.approvers.length === 0) {
      appGrid.innerHTML = `
        <div class="sm:col-span-2 text-left py-2.5 px-3 border border-dashed border-slate-200 rounded-lg text-[10px] text-slate-400 italic">
          No approvers assigned to this level yet.
        </div>
      `;
    } else {
      lvl.approvers.forEach((app, appIdx) => {
        const row = document.createElement("div");
        row.className = "flex items-center justify-between p-2 bg-slate-50 border border-slate-100 rounded-lg text-xs hover:border-slate-200 transition";

        let seqLabel = "";
        if (lvl.approval_mode === "SEQUENTIAL") {
          seqLabel = `<span class="mr-1.5 flex items-center justify-center h-4 w-4 bg-slate-200 text-slate-700 text-[9px] font-bold rounded">${app.sequence_number}</span>`;
        }

        const info = document.createElement("div");
        info.className = "flex items-center truncate mr-2";
        info.innerHTML = `
          ${seqLabel}
          <div class="flex flex-col truncate">
            <span class="font-semibold text-slate-700 truncate">${app.full_name}</span>
            <span class="text-[10px] text-slate-400 truncate">${app.email}</span>
          </div>
        `;
        row.appendChild(info);

        const actions = document.createElement("div");
        actions.className = "flex items-center space-x-1";

        if (isEditable && lvl.approval_mode === "SEQUENTIAL") {
          const btnUp = document.createElement("button");
          btnUp.type = "button";
          btnUp.className = "p-0.5 text-slate-400 hover:text-indigo-600 disabled:opacity-30";
          btnUp.innerHTML = `<svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 15l7-7 7 7"/></svg>`;
          if (appIdx === 0) btnUp.disabled = true;
          btnUp.onclick = () => {
            const temp = lvl.approvers[appIdx - 1];
            lvl.approvers[appIdx - 1] = app;
            lvl.approvers[appIdx] = temp;
            lvl.approvers.forEach((a, i) => a.sequence_number = i + 1);
            hasUnsavedChanges = true;
            renderWorkspace();
          };
          actions.appendChild(btnUp);

          const btnDown = document.createElement("button");
          btnDown.type = "button";
          btnDown.className = "p-0.5 text-slate-400 hover:text-indigo-600 disabled:opacity-30";
          btnDown.innerHTML = `<svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 9l-7 7-7-7"/></svg>`;
          if (appIdx === lvl.approvers.length - 1) btnDown.disabled = true;
          btnDown.onclick = () => {
            const temp = lvl.approvers[appIdx + 1];
            lvl.approvers[appIdx + 1] = app;
            lvl.approvers[appIdx] = temp;
            lvl.approvers.forEach((a, i) => a.sequence_number = i + 1);
            hasUnsavedChanges = true;
            renderWorkspace();
          };
          actions.appendChild(btnDown);
        }

        if (isEditable) {
          const btnDelete = document.createElement("button");
          btnDelete.type = "button";
          btnDelete.className = "p-0.5 text-slate-400 hover:text-rose-500";
          btnDelete.innerHTML = `<svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`;
          btnDelete.onclick = () => {
            lvl.approvers.splice(appIdx, 1);
            if (lvl.approval_mode === "SEQUENTIAL") {
              lvl.approvers.forEach((a, i) => a.sequence_number = i + 1);
            }
            hasUnsavedChanges = true;
            renderWorkspace();
          };
          actions.appendChild(btnDelete);
        }

        row.appendChild(actions);
        appGrid.appendChild(row);
      });
    }
    approversArea.appendChild(appGrid);

    // Add Approver selection form
    if (isEditable) {
      const selectForm = document.createElement("div");
      selectForm.className = "flex items-center space-x-2 pt-2 max-w-sm";
      
      const select = document.createElement("select");
      select.className = "form-select text-[11px] rounded-lg border-slate-200 py-1 bg-white focus:border-indigo-500 flex-1";

      const currentIds = new Set(lvl.approvers.map(a => a.user_id));
      const filtered = availableUsers.filter(u => !currentIds.has(u.id));

      if (filtered.length === 0) {
        select.innerHTML = '<option value="">All active users assigned</option>';
        select.disabled = true;
      } else {
        select.innerHTML = '<option value="">-- Assign Approver --</option>';
        filtered.forEach(u => {
          const opt = document.createElement("option");
          opt.value = u.id;
          opt.textContent = `${u.full_name} (${u.email})`;
          select.appendChild(opt);
        });
      }

      const btnAdd = document.createElement("button");
      btnAdd.type = "button";
      btnAdd.className = "px-3 py-1 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-600 text-[11px] font-bold rounded-lg transition disabled:opacity-50";
      btnAdd.textContent = "Add";
      if (filtered.length === 0) btnAdd.disabled = true;

      btnAdd.onclick = () => {
        const uId = parseInt(select.value);
        if (!uId) return;
        const user = availableUsers.find(u => u.id === uId);
        if (!user) return;

        lvl.approvers.push({
          user_id: user.id,
          full_name: user.full_name,
          email: user.email,
          sequence_number: lvl.approval_mode === "SEQUENTIAL" ? lvl.approvers.length + 1 : null
        });

        hasUnsavedChanges = true;
        renderWorkspace();
      };

      selectForm.appendChild(select);
      selectForm.appendChild(btnAdd);
      approversArea.appendChild(selectForm);
    }

    div.appendChild(approversArea);
    return div;
  }

  // --- Add level button ---
  btnAddLevel.onclick = () => {
    const nextNum = levelsList.length + 1;
    levelsList.push({
      level_number: nextNum,
      level_name: `Level ${nextNum}`,
      approval_mode: "ANY_ONE",
      approvers: []
    });
    hasUnsavedChanges = true;
    renderWorkspace();
  };

  // --- Checklist validation checker ---
  function runValidation() {
    const checks = [];
    
    // Check 1: At least one stage
    checks.push({
      label: "At least one approval level",
      status: levelsList.length > 0
    });

    // Check 2: Every level has approver
    let everyLevelHasApprover = levelsList.length > 0;
    levelsList.forEach(l => {
      if (l.approvers.length === 0) everyLevelHasApprover = false;
    });
    checks.push({
      label: "Every level has an active approver",
      status: everyLevelHasApprover
    });

    // Check 3: Final level has approvers
    let finalLevelCheck = levelsList.length > 0 && levelsList[levelsList.length - 1].approvers.length > 0;
    checks.push({
      label: "Final approver explicitly configured",
      status: finalLevelCheck
    });

    // Render checklist
    validationErrors.innerHTML = "";
    checks.forEach(check => {
      const item = document.createElement("div");
      item.className = "flex items-center space-x-1.5 font-medium";
      if (check.status) {
        item.innerHTML = `<span class="text-emerald-600 font-bold text-xs">✓</span> <span class="text-slate-700">${check.label}</span>`;
      } else {
        item.innerHTML = `<span class="text-rose-500 font-bold text-xs">✕</span> <span class="text-slate-500">${check.label}</span>`;
      }
      validationErrors.appendChild(item);
    });

    // Toggle save button
    const failedCheck = checks.some(c => !c.status);
    if (permissions.can_edit && !failedCheck) {
      btnSaveDraft.disabled = false;
    } else {
      btnSaveDraft.disabled = true;
    }
  }

  // --- Save Draft Sequence ---
  async function saveDraft() {
    if (!permissions.can_edit) return;

    // Check name
    const name = dfName.value.trim();
    if (!name) {
      showToast("Workflow name cannot be empty.", "error");
      return;
    }

    const payload = {
      levels: levelsList.map(lvl => ({
        level_number: lvl.level_number,
        level_name: lvl.level_name,
        approval_mode: lvl.approval_mode,
        approvers: lvl.approvers.map(a => ({
          user_id: a.user_id,
          sequence_number: a.sequence_number
        }))
      }))
    };

    try {
      // First save name details via PUT
      await fetch(`/module/WFLWBLD/api/${currentWorkflowId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });

      // Save levels sequence details via POST
      const res = await fetch(`/module/WFLWBLD/api/version/${currentVersionId}/levels`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      
      if (res.ok) {
        showToast("Workflow draft sequence saved successfully.");
        hasUnsavedChanges = false;
        loadVersionDetails(currentVersionId);
      } else {
        showToast("Save failed: " + (data.error || "Unknown error occurred"), "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to save draft.", "error");
    }
  }

  btnSaveDraft.onclick = saveDraft;

  // --- Publish version ---
  async function publishVersion() {
    if (!permissions.can_publish) return;
    if (!confirm("Are you sure you want to publish this workflow? It will become active immediately.")) {
      return;
    }

    try {
      const res = await fetch(`/module/WFLWBLD/api/version/${currentVersionId}/publish`, {
        method: "POST"
      });
      const data = await res.json();
      if (res.ok) {
        showToast("Workflow version published successfully!");
        showList();
      } else {
        showToast("Publish failed: " + (data.error || "Unknown error occurred"), "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to publish workflow.", "error");
    }
  }

  // --- Create draft version ---
  async function createNewVersionDraft() {
    if (!permissions.can_create_version) return;
    if (!confirm("Create a new draft version starting from this published version?")) return;

    try {
      const res = await fetch(`/module/WFLWBLD/api/${currentWorkflowId}/new-version`, {
        method: "POST"
      });
      const data = await res.json();
      if (res.ok) {
        showToast("New draft version created.");
        editWorkflow(currentWorkflowId, data.data.version_id);
      } else {
        showToast(data.error || "Unknown error occurred", "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to create new draft version.", "error");
    }
  }

  // --- Delete workflow ---
  async function deleteWorkflow() {
    if (!confirm("Are you sure you want to delete this entire workflow?")) return;

    try {
      const res = await fetch(`/module/WFLWBLD/api/${currentWorkflowId}`, {
        method: "DELETE"
      });
      const data = await res.json();
      if (res.ok) {
        showToast("Workflow deleted successfully.");
        showList();
      } else {
        showToast(data.error || "Unknown error occurred", "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Failed to delete workflow.", "error");
    }
  }

  // Initial load
  loadWorkflows();
});
