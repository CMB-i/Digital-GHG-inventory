document.addEventListener("DOMContentLoaded", function () {
  let formsList = [];
  let currentFields = [];
  let availableValueSets = [];
  let availableFormulas = [];
  let availableWorkflows = [];
  let activeSites = [];
  let sitesMap = {};
  let workflowsMap = {};
  
  let selectedFormId = null;
  let selectedVersionId = null;
  let selectedFieldCode = null;
  let isUnsaved = false;

  // View containers
  const listView = document.getElementById("list-view");
  const step1View = document.getElementById("step1-view");
  const step2View = document.getElementById("step2-view");
  
  // Table body in list-view
  const formsListBody = document.getElementById("forms-list-body");

  // Step 2 elements
  const builderFormTitle = document.getElementById("builder-form-title");
  const builderVersionBadge = document.getElementById("builder-version-badge");
  const formWorkspace = document.getElementById("form-workspace");
  const saveStatusText = document.getElementById("save-status-text");
  const btnSaveLayout = document.getElementById("btn-save-layout");
  const btnPublishForm = document.getElementById("btn-publish-form");
  const publishErrors = document.getElementById("publish-errors");
  const publishErrorsList = document.getElementById("publish-errors-list");

  // Inspector elements
  const inspectorPanel = document.getElementById("inspector-panel");
  const inspectorEmpty = document.getElementById("inspector-empty-state");
  const formFieldProperties = document.getElementById("form-field-properties");
  const btnDeleteField = document.getElementById("btn-delete-field");
  const btnMoveUp = document.getElementById("btn-move-up");
  const btnMoveDown = document.getElementById("btn-move-down");

  // Step 1 Details elements
  const formDetailsSubmit = document.getElementById("form-details-submit");
  const dfCode = document.getElementById("df-code");
  const dfName = document.getElementById("df-name");
  const dfGri = document.getElementById("df-gri");
  const dfSitesList = document.getElementById("df-sites-list");
  const dfFrequency = document.getElementById("df-frequency");
  const dfWorkflow = document.getElementById("df-workflow");
  const dfDesc = document.getElementById("df-desc");
  const step1Title = document.getElementById("step1-title");

  // SPOC Preview elements
  const previewOverlay = document.getElementById("preview-overlay");
  const pvTitle = document.getElementById("pv-title");
  const pvMeta = document.getElementById("pv-meta");
  const previewWorkspaceEl = document.getElementById("preview-workspace-el");

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
    
    // Animate in
    setTimeout(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
    }, 10);
    
    // Auto remove
    setTimeout(() => {
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // --- View Switching ---
  window.showList = function () {
    step1View.classList.add("hidden");
    step2View.classList.add("hidden");
    listView.classList.remove("hidden");
    loadForms();
  };

  window.startNew = function () {
    listView.classList.add("hidden");
    step2View.classList.add("hidden");
    step1View.classList.remove("hidden");

    step1Title.textContent = "New Form · Step 1 — Form Details";
    selectedFormId = null;
    selectedVersionId = null;

    // Reset fields
    dfCode.value = "";
    dfCode.disabled = false;
    dfName.value = "";
    dfGri.value = "";
    dfFrequency.value = "Monthly";
    dfWorkflow.value = "";
    dfDesc.value = "";

    // Uncheck all sites
    const checkboxes = dfSitesList.querySelectorAll("input[type='checkbox']");
    checkboxes.forEach(cb => cb.checked = false);
  };

  window.editFormDetails = function (formId) {
    const form = formsList.find(x => x.id === formId);
    if (!form) return;

    listView.classList.add("hidden");
    step2View.classList.add("hidden");
    step1View.classList.remove("hidden");

    step1Title.textContent = `Edit Form Details · ${form.display_name || form.name}`;
    selectedFormId = formId;
    selectedVersionId = form.latest_version_id;

    dfCode.value = form.code;
    dfCode.disabled = true; // Code cannot change once created
    dfName.value = form.display_name || form.name;
    dfGri.value = form.gri_code || "";
    dfFrequency.value = form.frequency || "Monthly";
    dfWorkflow.value = form.workflow_id || "";
    dfDesc.value = form.description || "";

    // Check sites
    const checkboxes = dfSitesList.querySelectorAll("input[type='checkbox']");
    checkboxes.forEach(cb => {
      const siteId = parseInt(cb.value);
      cb.checked = (form.sites || []).includes(siteId);
    });
  };

  window.editFormLayout = function (formId, versionId) {
    selectedFormId = formId;
    selectedVersionId = versionId;

    listView.classList.add("hidden");
    step1View.classList.add("hidden");
    step2View.classList.remove("hidden");

    const form = formsList.find(x => x.id === formId);
    if (form) {
      builderFormTitle.textContent = form.display_name || form.name;
    }

    loadVersionDetails(versionId);
  };

  // --- Initial Setup & Data Fetching ---
  function init() {
    // 1. Fetch sites
    fetch("/module/SITEMST/api")
      .then(res => res.json())
      .then(sites => {
        activeSites = sites;
        sitesMap = {};
        sites.forEach(s => {
          sitesMap[s.id] = s.name;
        });
        renderSitesCheckboxes();
        
        // 2. Fetch workflows
        return fetch("/module/WFLWBLD/api");
      })
      .then(res => res.json())
      .then(workflows => {
        availableWorkflows = workflows;
        workflowsMap = {};
        workflows.forEach(w => {
          workflowsMap[w.id] = w.name;
        });
        renderWorkflowsDropdown();

        // 3. Load Forms List
        loadForms();
      })
      .catch(err => {
        console.error("Error initializing data:", err);
        showToast("Error loading startup data.", "error");
      });
  }

  function renderSitesCheckboxes() {
    dfSitesList.innerHTML = "";
    if (activeSites.length === 0) {
      dfSitesList.innerHTML = '<span class="text-slate-400 italic">No active sites found.</span>';
      return;
    }
    activeSites.forEach(s => {
      const label = document.createElement("label");
      label.className = "flex items-center space-x-2 text-xs font-semibold text-slate-700 cursor-pointer hover:bg-slate-100 p-1 rounded transition";
      label.innerHTML = `
        <input type="checkbox" name="df-sites" value="${s.id}" class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500">
        <span>${s.name} (${s.code})</span>
      `;
      dfSitesList.appendChild(label);
    });
  }

  function renderWorkflowsDropdown() {
    dfWorkflow.innerHTML = '<option value="">Select workflow...</option>';
    availableWorkflows.forEach(w => {
      const opt = document.createElement("option");
      opt.value = w.id;
      opt.textContent = `${w.name} (${w.code})`;
      dfWorkflow.appendChild(opt);
    });
  }

  // Fetch all forms on load or refresh
  function loadForms() {
    formsListBody.innerHTML = '<tr><td colspan="7" class="px-6 py-12 text-center text-slate-400 italic">Loading forms...</td></tr>';
    
    fetch("/module/FORMBLD/api")
      .then(res => res.json())
      .then(data => {
        formsList = data;
        formsListBody.innerHTML = "";

        if (data.length === 0) {
          formsListBody.innerHTML = `
            <tr>
              <td colspan="7" class="px-6 py-12 text-center text-slate-400 italic">
                No forms created yet. Click "Create New Form" to get started.
              </td>
            </tr>
          `;
          return;
        }

        data.forEach(form => {
          const tr = document.createElement("tr");
          tr.className = "hover:bg-slate-50/50 transition-colors";
          
          // Map site IDs to names
          let sitesText = "None";
          if (form.sites && form.sites.length > 0) {
            sitesText = form.sites.map(sid => sitesMap[sid] || sid).join(", ");
          }

          // Build status badge
          let statusBadge = "";
          const status = form.latest_version_status || "Draft";
          if (status === "Published") {
            statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 uppercase">Published</span>';
          } else if (status === "Archived") {
            statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-800 uppercase">Archived</span>';
          } else {
            statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 uppercase">Draft</span>';
          }

          // Actions
          let actions = [];
          if (status === "Draft" && form.latest_version_id) {
            actions.push(`<button onclick="editFormDetails(${form.id})" class="text-indigo-600 hover:text-indigo-900 font-bold hover:underline mr-3">Edit Details</button>`);
            actions.push(`<button onclick="editFormLayout(${form.id}, ${form.latest_version_id})" class="text-indigo-600 hover:text-indigo-900 font-bold hover:underline mr-3">Edit Layout</button>`);
          } else if (status === "Published") {
            actions.push(`<button onclick="createNewDraft(${form.id})" class="text-indigo-600 hover:text-indigo-900 font-bold hover:underline mr-3">New Draft Version</button>`);
          }
          
          if (form.latest_version_id) {
            actions.push(`<button onclick="openPreview(${form.id}, ${form.latest_version_id})" class="text-slate-600 hover:text-slate-900 font-bold hover:underline">Preview</button>`);
          }

          tr.innerHTML = `
            <td class="px-6 py-4 font-bold text-slate-800">${form.display_name || form.name}</td>
            <td class="px-6 py-4 font-mono text-slate-500">${form.gri_code || "—"}</td>
            <td class="px-6 py-4 text-slate-500 truncate max-w-xs" title="${sitesText}">${sitesText}</td>
            <td class="px-6 py-4 text-slate-500">${form.frequency || "Monthly"}</td>
            <td class="px-6 py-4">${statusBadge}</td>
            <td class="px-6 py-4 text-slate-500 font-semibold">v${form.latest_version_num || 1}</td>
            <td class="px-6 py-4 text-right whitespace-nowrap">${actions.join("")}</td>
          `;
          formsListBody.appendChild(tr);
        });
      })
      .catch(err => {
        console.error("Error loading forms:", err);
        showToast("Error loading forms list.", "error");
      });
  }

  // --- Step 1 Details Form Submit ---
  formDetailsSubmit.onsubmit = function (e) {
    e.preventDefault();

    const name = dfName.value.trim();
    const code = dfCode.value.trim().toUpperCase().replace(/\s+/g, "_");
    const gri_code = dfGri.value.trim();
    const frequency = dfFrequency.value;
    const workflow_id = dfWorkflow.value ? parseInt(dfWorkflow.value) : null;
    const description = dfDesc.value.trim();

    // Collect checked sites
    const sites = [];
    dfSitesList.querySelectorAll("input[name='df-sites']:checked").forEach(cb => {
      sites.push(parseInt(cb.value));
    });

    if (sites.length === 0) {
      showToast("Please select at least one site applicability.", "error");
      return;
    }

    if (!workflow_id) {
      showToast("Please select an approval workflow.", "error");
      return;
    }

    const payload = {
      name: name,
      code: code,
      display_name: name,
      gri_code: gri_code,
      frequency: frequency,
      workflow_id: workflow_id,
      sites: sites,
      description: description,
      description_text: description
    };

    if (selectedFormId === null) {
      // Create new form
      fetch("/module/FORMBLD/api", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(res => res.json())
        .then(resData => {
          if (resData.error) {
            showToast(resData.error, "error");
          } else {
            showToast("Form details saved successfully.");
            
            // Reload list, find the form and open Step 2
            fetch("/module/FORMBLD/api")
              .then(res => res.json())
              .then(data => {
                formsList = data;
                const newForm = data.find(x => x.code === code);
                if (newForm && newForm.latest_version_id) {
                  editFormLayout(newForm.id, newForm.latest_version_id);
                } else {
                  showList();
                }
              });
          }
        })
        .catch(err => {
          console.error("Error creating form:", err);
          showToast("Failed to create form.", "error");
        });
    } else {
      // Update form details
      fetch(`/module/FORMBLD/api/${selectedFormId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      })
        .then(res => res.json())
        .then(resData => {
          if (resData.error) {
            showToast(resData.error, "error");
          } else {
            showToast("Form details updated successfully.");
            
            // Go directly to layout canvas
            editFormLayout(selectedFormId, selectedVersionId);
          }
        })
        .catch(err => {
          console.error("Error updating form details:", err);
          showToast("Failed to update form details.", "error");
        });
    }
  };

  // --- Step 2 Layout Canvas Logic ---
  function loadVersionDetails(versionId) {
    closeInspector();
    publishErrors.classList.add("hidden");
    
    fetch(`/module/FORMBLD/api/version/${versionId}`)
      .then(res => res.json())
      .then(data => {
        selectedVersionId = data.version.id;
        currentFields = data.fields || [];
        availableValueSets = data.available_value_sets || [];
        availableFormulas = data.available_formulas || [];
        isUnsaved = false;

        // Set status badge and name
        builderFormTitle.textContent = data.form.display_name || data.form.name;
        builderVersionBadge.textContent = `v${data.version.version_number} (${data.version.status})`;
        
        let badgeClass = "bg-amber-100 text-amber-800";
        if (data.version.status === "Published") badgeClass = "bg-emerald-100 text-emerald-800";
        else if (data.version.status === "Archived") badgeClass = "bg-slate-100 text-slate-800";
        builderVersionBadge.className = `px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${badgeClass}`;

        // Populate dropdown options inside inspectors
        populateInspectorDropdowns();

        // Render Canvas Preview
        renderWorkspace();

        // Save status styling
        updateSaveStatusText();

        // Setup actions depending on status
        if (data.version.status !== "Draft") {
          btnSaveLayout.classList.add("hidden");
          btnPublishForm.classList.add("hidden");
        } else {
          btnSaveLayout.classList.remove("hidden");
          btnPublishForm.classList.remove("hidden");
        }
      })
      .catch(err => {
        console.error("Error loading version details:", err);
        showToast("Error loading version layout.", "error");
      });
  }

  function populateInspectorDropdowns() {
    const vsSelect = document.getElementById("prop-valueset");
    vsSelect.innerHTML = '<option value="">Select Value Set...</option>';
    availableValueSets.forEach(vs => {
      const opt = document.createElement("option");
      opt.value = vs.current_version_id;
      opt.textContent = `${vs.name} (${vs.code})`;
      vsSelect.appendChild(opt);
    });

    const fSelect = document.getElementById("prop-formula");
    fSelect.innerHTML = '<option value="">Select Formula...</option>';
    availableFormulas.forEach(f => {
      const opt = document.createElement("option");
      opt.value = f.current_version_id;
      opt.textContent = `${f.name} (${f.code})`;
      fSelect.appendChild(opt);
    });
  }

  function updateSaveStatusText() {
    if (isUnsaved) {
      saveStatusText.textContent = "Unsaved changes *";
      saveStatusText.className = "text-xs text-amber-600 font-bold animate-pulse";
      btnSaveLayout.disabled = false;
      btnSaveLayout.className = "inline-flex items-center justify-center px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-sm transition";
    } else {
      saveStatusText.textContent = "All changes saved";
      saveStatusText.className = "text-xs text-slate-400 font-medium";
      btnSaveLayout.disabled = true;
      btnSaveLayout.className = "inline-flex items-center justify-center px-4 py-1.5 bg-slate-100 text-slate-400 text-xs font-bold rounded-lg cursor-not-allowed";
    }
  }

  function renderWorkspace() {
    window.renderForm(currentFields, formWorkspace, "builder_preview");
    
    // Attach selection clicks to preview rows
    const rows = formWorkspace.querySelectorAll("[data-field-code]");
    rows.forEach(row => {
      row.style.cursor = "pointer";
      row.classList.add("hover:bg-slate-50/80", "transition-colors", "rounded-lg", "p-2", "my-1");
      
      row.onclick = function (e) {
        if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") {
          return;
        }
        selectedFieldCode = row.dataset.fieldCode;
        highlightRow(row);
        openInspector(selectedFieldCode);
      };

      if (row.dataset.fieldCode === selectedFieldCode) {
        highlightRow(row);
      }
    });
  }

  function highlightRow(rowElement) {
    const rows = formWorkspace.querySelectorAll("[data-field-code]");
    rows.forEach(r => {
      r.classList.remove("border-2", "border-indigo-400/80", "bg-indigo-50/10", "shadow-sm");
      r.style.borderStyle = "";
    });
    
    rowElement.classList.add("border-2", "border-indigo-400/80", "bg-indigo-50/10", "shadow-sm");
    rowElement.style.borderStyle = "solid";
  }

  function openInspector(fieldCode) {
    const field = currentFields.find(x => x.field_code === fieldCode);
    if (!field) return;

    inspectorEmpty.classList.add("hidden");
    inspectorPanel.classList.remove("hidden");

    // Common fields
    document.getElementById("prop-code").value = field.field_code;
    document.getElementById("prop-name").value = field.field_name;
    document.getElementById("prop-required").checked = field.field_config.is_required || false;
    document.getElementById("prop-remarks-req").checked = field.field_config.remarks_required || false;
    document.getElementById("prop-proof-req").checked = field.field_config.proof_required || false;
    document.getElementById("prop-help").value = field.field_config.help_text || "";

    // Toggle specific type options
    document.getElementById("prop-section-numeric").classList.add("hidden");
    document.getElementById("prop-section-dropdown").classList.add("hidden");
    document.getElementById("prop-section-calculated").classList.add("hidden");
    document.getElementById("prop-section-file").classList.add("hidden");

    const config = field.field_config || {};

    if (field.field_type === "number" || field.field_type === "integer" || field.field_type === "calculated") {
      document.getElementById("prop-section-numeric").classList.remove("hidden");
      document.getElementById("prop-unit").value = config.unit || "";
      document.getElementById("prop-min").value = config.min !== undefined ? config.min : "";
      document.getElementById("prop-max").value = config.max !== undefined ? config.max : "";
      document.getElementById("prop-anomaly").value = config.anomaly_threshold !== undefined ? config.anomaly_threshold : "";
    }

    if (field.field_type === "dropdown") {
      document.getElementById("prop-section-dropdown").classList.remove("hidden");
      document.getElementById("prop-valueset").value = config.value_set_version_id || "";
    }

    if (field.field_type === "calculated") {
      document.getElementById("prop-section-calculated").classList.remove("hidden");
      document.getElementById("prop-formula").value = config.formula_version_id || "";
    }

    if (field.field_type === "file") {
      document.getElementById("prop-section-file").classList.remove("hidden");
      const mimeCheckboxes = document.getElementsByName("mime-types");
      const acceptedList = config.accepted_mime_types || [];
      mimeCheckboxes.forEach(cb => {
        cb.checked = acceptedList.includes(cb.value);
      });
    }
  }

  function closeInspector() {
    selectedFieldCode = null;
    inspectorPanel.classList.add("hidden");
    inspectorEmpty.classList.remove("hidden");
  }

  // Apply Changes from properties form
  formFieldProperties.onsubmit = function (e) {
    e.preventDefault();
    if (!selectedFieldCode) return;

    const fieldIdx = currentFields.findIndex(x => x.field_code === selectedFieldCode);
    if (fieldIdx === -1) return;

    const field = currentFields[fieldIdx];
    const newCode = document.getElementById("prop-code").value.trim().toLowerCase().replace(/\s+/g, "_");

    // Validate code duplicate
    const dup = currentFields.find((x, idx) => x.field_code === newCode && idx !== fieldIdx);
    if (dup) {
      showToast(`Field code '${newCode}' is already used.`, "error");
      return;
    }

    field.field_code = newCode;
    field.field_name = document.getElementById("prop-name").value.trim();
    field.field_config.is_required = document.getElementById("prop-required").checked;
    field.field_config.remarks_required = document.getElementById("prop-remarks-req").checked;
    field.field_config.proof_required = document.getElementById("prop-proof-req").checked;
    field.field_config.help_text = document.getElementById("prop-help").value.trim();

    if (field.field_type === "number" || field.field_type === "integer" || field.field_type === "calculated") {
      field.field_config.unit = document.getElementById("prop-unit").value.trim();
      
      const minVal = document.getElementById("prop-min").value;
      field.field_config.min = minVal !== "" ? parseFloat(minVal) : undefined;
      
      const maxVal = document.getElementById("prop-max").value;
      field.field_config.max = maxVal !== "" ? parseFloat(maxVal) : undefined;

      const anomalyVal = document.getElementById("prop-anomaly").value;
      field.field_config.anomaly_threshold = anomalyVal !== "" ? parseFloat(anomalyVal) : undefined;
    }

    if (field.field_type === "dropdown") {
      const vsVal = document.getElementById("prop-valueset").value;
      field.field_config.value_set_version_id = vsVal ? parseInt(vsVal) : undefined;

      // Populate options for rendering preview dropdowns
      if (vsVal) {
        fetch(`/module/VALSET/api/version/${vsVal}`)
          .then(res => res.json())
          .then(resData => {
            field.field_config.options = resData.entries;
            renderWorkspace();
          });
      } else {
        field.field_config.options = [];
      }
    }

    if (field.field_type === "calculated") {
      const formulaVal = document.getElementById("prop-formula").value;
      field.field_config.formula_version_id = formulaVal ? parseInt(formulaVal) : undefined;

      if (formulaVal) {
        fetch(`/module/FRMULA/api/version/${formulaVal}`)
          .then(res => res.json())
          .then(resData => {
            field.field_config.expression = resData.version.expression;
            field.field_config.tokens = resData.version.tokens;
            renderWorkspace();
          });
      } else {
        field.field_config.expression = "";
        field.field_config.tokens = [];
      }
    }

    if (field.field_type === "file") {
      const checkedMimes = [];
      document.getElementsByName("mime-types").forEach(cb => {
        if (cb.checked) checkedMimes.push(cb.value);
      });
      field.field_config.accepted_mime_types = checkedMimes;
    }

    selectedFieldCode = newCode;
    isUnsaved = true;
    updateSaveStatusText();
    renderWorkspace();
    showToast("Field updated in workspace.");
  };

  // Palette item clicks
  document.querySelectorAll(".palette-btn").forEach(btn => {
    btn.onclick = function () {
      const type = btn.dataset.type;
      const displayOrder = currentFields.length + 1;
      const code = `field_${Date.now()}`;
      const name = `New ${type.charAt(0).toUpperCase() + type.slice(1)}`;

      const newField = {
        field_code: code,
        field_name: name,
        field_type: type,
        display_order: displayOrder,
        field_config: {
          is_required: false,
          help_text: ""
        }
      };

      currentFields.push(newField);
      isUnsaved = true;
      selectedFieldCode = code;

      updateSaveStatusText();
      renderWorkspace();
      openInspector(code);
    };
  });

  // Delete field
  btnDeleteField.onclick = function () {
    if (!selectedFieldCode) return;
    if (!confirm("Are you sure you want to delete this field from the form layout?")) return;

    currentFields = currentFields.filter(x => x.field_code !== selectedFieldCode);
    
    // Normalize display order numbers
    currentFields.forEach((f, idx) => f.display_order = idx + 1);

    isUnsaved = true;
    closeInspector();
    updateSaveStatusText();
    renderWorkspace();
    showToast("Field deleted.");
  };

  // Move Field Up
  btnMoveUp.onclick = function () {
    if (!selectedFieldCode) return;
    const idx = currentFields.findIndex(x => x.field_code === selectedFieldCode);
    if (idx <= 0) return;

    const tempOrder = currentFields[idx].display_order;
    currentFields[idx].display_order = currentFields[idx - 1].display_order;
    currentFields[idx - 1].display_order = tempOrder;

    // Swap elements in array
    const item = currentFields[idx];
    currentFields[idx] = currentFields[idx - 1];
    currentFields[idx - 1] = item;

    isUnsaved = true;
    updateSaveStatusText();
    renderWorkspace();
  };

  // Move Field Down
  btnMoveDown.onclick = function () {
    if (!selectedFieldCode) return;
    const idx = currentFields.findIndex(x => x.field_code === selectedFieldCode);
    if (idx === -1 || idx >= currentFields.length - 1) return;

    const tempOrder = currentFields[idx].display_order;
    currentFields[idx].display_order = currentFields[idx + 1].display_order;
    currentFields[idx + 1].display_order = tempOrder;

    // Swap elements in array
    const item = currentFields[idx];
    currentFields[idx] = currentFields[idx + 1];
    currentFields[idx + 1] = item;

    isUnsaved = true;
    updateSaveStatusText();
    renderWorkspace();
  };

  // Save Layout Draft
  btnSaveLayout.onclick = function () {
    if (!selectedVersionId) return;

    fetch(`/module/FORMBLD/api/version/${selectedVersionId}/fields`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fields: currentFields })
    })
      .then(res => res.json())
      .then(resData => {
        if (resData.error) {
          showToast(resData.error, "error");
        } else {
          showToast("Form fields draft saved successfully.");
          isUnsaved = false;
          loadVersionDetails(selectedVersionId);
        }
      })
      .catch(err => {
        console.error("Error saving form fields:", err);
        showToast("Failed to save draft.", "error");
      });
  };

  // Publish validation & submit
  btnPublishForm.onclick = function () {
    if (!selectedVersionId) return;

    // 1. Perform client side validations
    const errors = [];
    const formObj = formsList.find(x => x.id === selectedFormId);

    if (currentFields.length === 0) {
      errors.push("Form must contain at least one field.");
    }

    currentFields.forEach(f => {
      if (f.field_type === "calculated" && (!f.field_config || !f.field_config.formula_version_id)) {
        errors.push(`Calculated field "${f.field_name}" must reference a published formula.`);
      }
      if (f.field_type === "dropdown" && (!f.field_config || !f.field_config.value_set_version_id)) {
        errors.push(`Dropdown field "${f.field_name}" must reference an approved value set.`);
      }
    });

    if (!formObj || !formObj.workflow_id) {
      errors.push("An approval workflow must be assigned to the form.");
    }
    if (!formObj || !formObj.sites || formObj.sites.length === 0) {
      errors.push("Form must be applicable to at least one site.");
    }

    if (errors.length > 0) {
      publishErrorsList.innerHTML = errors.map(e => `<li>${e}</li>`).join("");
      publishErrors.classList.remove("hidden");
      showToast("Please resolve all errors before publishing.", "error");
      return;
    }

    publishErrors.classList.add("hidden");

    if (!confirm("Are you sure you want to publish this form version? It will become active immediately.")) {
      return;
    }

    // Call publish API
    fetch(`/module/FORMBLD/api/version/${selectedVersionId}/publish`, {
      method: "POST"
    })
      .then(res => res.json())
      .then(resData => {
        if (resData.error) {
          showToast(resData.error, "error");
        } else {
          showToast("Form version published successfully!");
          isUnsaved = false;
          showList();
        }
      })
      .catch(err => {
        console.error("Error publishing form:", err);
        showToast("Failed to publish form.", "error");
      });
  };

  // Create new version draft for published form
  window.createNewDraft = function (formId) {
    if (!confirm("Create a new draft version based on the current published fields?")) return;

    fetch(`/module/FORMBLD/api/${formId}/new-version`, {
      method: "POST"
    })
      .then(res => res.json())
      .then(resData => {
        if (resData.error) {
          showToast(resData.error, "error");
        } else {
          showToast("New draft version created.");
          // Refresh list and open layout for editing
          fetch("/module/FORMBLD/api")
            .then(res => res.json())
            .then(data => {
              formsList = data;
              editFormLayout(formId, resData.data.version_id);
            });
        }
      })
      .catch(err => {
        console.error("Error creating new draft version:", err);
        showToast("Failed to create draft version.", "error");
      });
  };

  // --- SPOC Preview Overlay Modal ---
  window.openPreview = function (formId, versionId) {
    // If we're previewing from Step 2 with unsaved changes, we alert first
    if (isUnsaved && !step2View.classList.contains("hidden")) {
      if (!confirm("You have unsaved changes in Step 2. Preview will show the last saved draft. Continue?")) {
        return;
      }
    }

    const form = formsList.find(x => x.id === formId);
    if (!form) return;

    pvTitle.textContent = form.display_name || form.name;
    
    let sitesText = "All Sites";
    if (form.sites && form.sites.length > 0) {
      sitesText = form.sites.map(sid => sitesMap[sid] || sid).join(", ");
    }
    pvMeta.textContent = `${sitesText} · Frequency: ${form.frequency || "Monthly"} · Version: v${form.latest_version_num || 1}`;

    fetch(`/module/FORMBLD/api/version/${versionId}`)
      .then(res => res.json())
      .then(data => {
        const fields = data.fields || [];
        window.renderForm(fields, previewWorkspaceEl, "spoc_entry", {}, {
          onValueChange: function (code, val, allValues) {
            console.log(`Preview value change: ${code} = ${val}`, allValues);
          }
        });
        previewOverlay.classList.remove("hidden");
      })
      .catch(err => {
        console.error("Error loading preview fields:", err);
        showToast("Error loading form preview fields.", "error");
      });
  };

  // Wrapper for calling preview from builder context (uses active state variables)
  window.openPreviewFromBuilder = function () {
    if (selectedFormId && selectedVersionId) {
      openPreview(selectedFormId, selectedVersionId);
    } else {
      showToast("No form is currently loaded for preview.", "error");
    }
  };

  window.closePreview = function () {
    previewOverlay.classList.add("hidden");
  };

  previewOverlay.onclick = function (e) {
    if (e.target === previewOverlay) {
      closePreview();
    }
  };

  // Run initial setup
  init();
});
