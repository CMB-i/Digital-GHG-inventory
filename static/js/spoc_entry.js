document.addEventListener("DOMContentLoaded", function () {
  const submissionId = window.SUBMISSION_ID;
  if (!submissionId) {
    console.error("Submission ID is missing.");
    return;
  }

  const sheetTitle = document.getElementById("sheet-title");
  const sheetStatus = document.getElementById("sheet-status");
  const sheetSite = document.getElementById("sheet-site");
  const sheetPeriod = document.getElementById("sheet-period");

  const saveStatusDot = document.getElementById("save-status-dot");
  const saveStatusText = document.getElementById("save-status-text");

  const btnSaveDraft = document.getElementById("btn-save-draft");
  const btnSubmit = document.getElementById("btn-submit");
  const actionBar = document.getElementById("action-bar");

  const modalSubmitConfirm = document.getElementById("modal-submit-confirm");
  const btnConfirmSubmit = document.getElementById("btn-confirm-submit");
  const btnCancelSubmit = document.getElementById("btn-cancel-submit");

  const validationSummary = document.getElementById("validation-summary");
  const validationSummaryList = document.getElementById("validation-summary-list");

  let formConfig = [];
  let formValues = {};
  let currentStatus = "Draft";
  let isSaving = false;
  let autosaveTimeout = null;

  // Set visual indicator states
  function setSaveStatus(state, message) {
    saveStatusText.textContent = message;
    saveStatusDot.className = "h-2.5 w-2.5 rounded-full mr-2";
    
    if (state === "saving") {
      saveStatusDot.classList.add("bg-indigo-500", "animate-pulse");
    } else if (state === "success") {
      saveStatusDot.classList.add("bg-emerald-500");
    } else if (state === "error") {
      saveStatusDot.classList.add("bg-rose-500");
    } else if (state === "idle") {
      saveStatusDot.classList.add("bg-slate-300");
    }
  }

  // Format time for save messages
  function formatTime(date) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Load Submission Metadata, Fields and Saved Values
  function loadSubmissionData() {
    setSaveStatus("saving", "Loading sheet configuration...");
    fetch(`/module/SUBMIT/api/submissions/${submissionId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load sheet details.");
        return res.json();
      })
      .then((data) => {
        formConfig = data.fields;
        formValues = data.values;
        currentStatus = data.submission.status;

        // Set top meta details
        sheetTitle.textContent = data.submission.form_name;
        sheetSite.textContent = data.submission.site_name;
        sheetPeriod.textContent = data.submission.period_label;
        
        sheetStatus.textContent = currentStatus.toUpperCase();
        
        // Status Colors
        sheetStatus.className = "px-2.5 py-0.5 rounded-full text-xs font-bold ";
        if (currentStatus === "Approved") {
          sheetStatus.classList.add("bg-emerald-100", "text-emerald-800");
        } else if (currentStatus === "Submitted" || currentStatus === "Resubmitted" || currentStatus === "Under Review") {
          sheetStatus.classList.add("bg-blue-100", "text-blue-800");
        } else if (currentStatus === "Changes Requested") {
          sheetStatus.classList.add("bg-amber-100", "text-amber-800", "animate-pulse");
        } else {
          sheetStatus.classList.add("bg-slate-100", "text-slate-700");
        }

        const isEditable = ["Draft", "Changes Requested"].includes(currentStatus);
        const hasWorkflow = data.submission.workflow_id;
        
        if (isEditable) {
          actionBar.classList.remove("hidden");
          setSaveStatus("success", "Ready to edit");
        } else {
          actionBar.classList.add("hidden");
          setSaveStatus("idle", "View Only / Locked");
        }

        // Display workflow missing warning block
        if (isEditable && !hasWorkflow) {
          validationSummaryList.innerHTML = "<li>This form is not ready for submission because no approval workflow has been assigned.</li>";
          validationSummary.classList.remove("hidden");
          btnSubmit.disabled = true;
          btnSubmit.classList.add("cursor-not-allowed", "opacity-50");
        } else if (isEditable) {
          validationSummary.classList.add("hidden");
          btnSubmit.disabled = false;
          btnSubmit.classList.remove("cursor-not-allowed", "opacity-50");
        }

        // Render Form using shared renderer
        renderCurrentForm();
        
        // Render existing anomalies
        displayAnomalies(data.anomalies || {});
      })
      .catch((err) => {
        console.error("Load error:", err);
        setSaveStatus("error", `Error loading form: ${err.message}`);
      });
  }

  // Render form helper
  function renderCurrentForm(validationErrors = {}) {
    const isEditable = ["Draft", "Changes Requested"].includes(currentStatus);
    const mode = isEditable ? "spoc_entry" : "readonly_review";
    const targetEl = document.getElementById("form-renderer-target");

    window.renderForm(
      formConfig,
      targetEl,
      mode,
      formValues,
      {
        validationErrors: validationErrors,
        onValueChange: function (fieldCode, val) {
          formValues[fieldCode] = val;
          triggerAutosave();
        },
        onFileUpload: function (fieldCode, file, cb) {
          uploadProofFile(fieldCode, file, cb);
        }
      }
    );
  }

  // Upload file via FormData
  function uploadProofFile(fieldCode, file, cb) {
    setSaveStatus("saving", `Uploading ${file.name}...`);
    const formData = new FormData();
    formData.append("file", file);

    fetch(`/module/SUBMIT/api/submissions/${submissionId}/proof/${fieldCode}`, {
      method: "POST",
      body: formData
    })
      .then((res) => {
        if (!res.ok) return res.json().then(d => { throw new Error(d.error || "Upload failed"); });
        return res.json();
      })
      .then((data) => {
        setSaveStatus("success", `File uploaded at ${formatTime(new Date())}`);
        cb(null, data.data);
      })
      .catch((err) => {
        setSaveStatus("error", `Upload failed: ${err.message}`);
        cb(err.message, null);
      });
  }

  // Debounced Autosave Trigger
  function triggerAutosave() {
    setSaveStatus("saving", "Saving draft...");
    if (autosaveTimeout) {
      clearTimeout(autosaveTimeout);
    }
    autosaveTimeout = setTimeout(executeAutosave, 1500); // debounce 1.5 seconds
  }

  // Execute Autosave PUT Call
  function executeAutosave() {
    if (isSaving) return;
    isSaving = true;

    fetch(`/module/SUBMIT/api/submissions/${submissionId}/autosave`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: formValues })
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to save draft.");
        return res.json();
      })
      .then((data) => {
        isSaving = false;
        setSaveStatus("success", `Last saved: ${formatTime(new Date())}`);
        
        // Update calculations values returned from Flask backend
        Object.keys(data.data.values).forEach(code => {
          formValues[code] = data.data.values[code];
          
          // Dynamically update calculations input fields in DOM
          const inputEl = document.getElementById("field_" + code);
          if (inputEl && inputEl.readOnly) {
            const decAttr = inputEl.getAttribute("data-decimals");
            const decimals = decAttr ? parseInt(decAttr, 10) : 3;
            inputEl.value = data.data.values[code] !== null && data.data.values[code] !== undefined
              ? parseFloat(parseFloat(data.data.values[code]).toFixed(decimals))
              : "";
          }
        });

        // Display anomalies
        displayAnomalies(data.data.anomalies || {});
      })
      .catch((err) => {
        isSaving = false;
        setSaveStatus("error", `Failed to save: ${err.message}`);
      });
  }

  // Display Anomaly Warnings under corresponding fields
  function displayAnomalies(anomalies) {
    // Clear old anomaly warnings in DOM
    document.querySelectorAll(".anomaly-warning-block").forEach(el => el.remove());

    Object.keys(anomalies).forEach(fieldCode => {
      const fieldRow = document.querySelector(`[data-field-code="${fieldCode}"]`);
      if (fieldRow) {
        const inputCol = fieldRow.querySelector(".w-full.md\\:w-2\\/3.flex.flex-col");
        if (inputCol) {
          const warnBlock = document.createElement("div");
          warnBlock.className = "anomaly-warning-block mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-100 p-2.5 rounded-lg font-semibold flex items-start space-x-2";
          warnBlock.innerHTML = `
            <svg class="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>${anomalies[fieldCode]}</span>
          `;
          inputCol.appendChild(warnBlock);
        }
      }
    });
  }

  // Manual save trigger
  btnSaveDraft.onclick = function () {
    if (autosaveTimeout) {
      clearTimeout(autosaveTimeout);
    }
    executeAutosave();
  };

  // Submit trigger - open confirm modal
  btnSubmit.onclick = function () {
    // Run an immediate save first to make sure server has latest values
    if (autosaveTimeout) {
      clearTimeout(autosaveTimeout);
    }
    
    setSaveStatus("saving", "Saving final entries...");
    fetch(`/module/SUBMIT/api/submissions/${submissionId}/autosave`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values: formValues })
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to save entries.");
        return res.json();
      })
      .then((data) => {
        setSaveStatus("success", `Saved draft at ${formatTime(new Date())}`);
        displayAnomalies(data.data.anomalies || {});
        
        // Open confirmation modal
        modalSubmitConfirm.classList.remove("hidden");
      })
      .catch((err) => {
        setSaveStatus("error", `Failed to save final draft: ${err.message}`);
        alert("Please resolve connectivity/save errors before submitting.");
      });
  };

  // Close submit modal
  btnCancelSubmit.onclick = function () {
    modalSubmitConfirm.classList.add("hidden");
  };

  // Confirm submission click
  btnConfirmSubmit.onclick = function () {
    btnConfirmSubmit.disabled = true;
    btnConfirmSubmit.textContent = "Submitting...";

    fetch(`/module/SUBMIT/api/submissions/${submissionId}/submit`, {
      method: "POST"
    })
      .then(async (res) => {
        const data = await res.json();
        if (res.status === 422) {
          // Validation failed
          modalSubmitConfirm.classList.add("hidden");
          displayValidationErrors(data.validation_errors || {});
          return;
        }
        if (!res.ok) throw new Error(data.error || "Failed to submit sheet.");
        
        // Success
        modalSubmitConfirm.classList.add("hidden");
        alert("Sheet submitted successfully!");
        window.location.href = "/module/SUBMIT/";
      })
      .catch((err) => {
        alert("Submission failed: " + err.message);
      })
      .finally(() => {
        btnConfirmSubmit.disabled = false;
        btnConfirmSubmit.textContent = "Confirm Submit";
      });
  };

  // Handle display of validation errors
  function displayValidationErrors(errors) {
    validationSummaryList.innerHTML = "";
    validationSummary.classList.remove("hidden");

    Object.keys(errors).forEach(code => {
      const li = document.createElement("li");
      li.textContent = errors[code];
      validationSummaryList.appendChild(li);
    });

    // Re-render form passing validation error messages to highlight borders
    renderCurrentForm(errors);

    // Scroll to validation summary
    validationSummary.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Initial load
  loadSubmissionData();
});
