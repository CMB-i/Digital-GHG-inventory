document.addEventListener("DOMContentLoaded", function () {
  let formulasList = [];
  let selectedFormulaId = null;
  let selectedVersionId = null;
  let isPublished = false;
  // Track value set entry codes inserted via palette — used when building tokens for save/validate
  const insertedValsetCodes = new Set();

  // View elements
  const listView = document.getElementById("list-view");
  const editorView = document.getElementById("editor-view");
  const formulasListBody = document.getElementById("formulas-list-body");

  // Editor headers
  const editorTitle = document.getElementById("editor-title");
  const editorStatusBadge = document.getElementById("editor-status-badge");
  const btnSaveFormula = document.getElementById("btn-save-formula");
  const btnPublishFormula = document.getElementById("btn-publish-formula");

  // Editor inputs
  const dfName = document.getElementById("df-name");
  const dfCode = document.getElementById("df-code");
  const expressionTextarea = document.getElementById("expression");
  const btnValidate = document.getElementById("btn-validate-formula");
  const validationResultContainer = document.getElementById("validation-result-container");
  const validationResult = document.getElementById("validation-result");

  // Dynamic preview elements
  const previewInputsGrid = document.getElementById("preview-inputs-grid");
  const previewResultValue = document.getElementById("preview-result-value");
  const formVersionSelect = document.getElementById("form-version-select");

  // Create Formula modal elements
  const modalCreate = document.getElementById("modal-create");
  const btnCreateFormula = document.getElementById("btn-create-formula");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnCancelModal = document.getElementById("btn-cancel-modal");
  const formCreateFormula = document.getElementById("form-create-formula");

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
    editorView.classList.add("hidden");
    listView.classList.remove("hidden");
    loadFormulas();
  };

  window.startNewFormula = function () {
    // Open the create formula modal
    modalCreate.classList.remove("hidden");
    document.getElementById("formula-name").value = "";
    document.getElementById("formula-code").value = "";
    document.getElementById("formula-expression").value = "";
  };

  window.editFormula = function (formulaId, versionId) {
    selectedFormulaId = formulaId;
    selectedVersionId = versionId;

    listView.classList.add("hidden");
    editorView.classList.remove("hidden");
    validationResultContainer.classList.add("hidden");

    loadVersionDetails(versionId);
  };

  // --- Load formulas list ---
  function loadFormulas() {
    formulasListBody.innerHTML = '<tr><td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">Loading formulas...</td></tr>';
    
    fetch("/module/FRMULA/api")
      .then(res => res.json())
      .then(data => {
        formulasList = data;
        formulasListBody.innerHTML = "";

        if (data.length === 0) {
          formulasListBody.innerHTML = `
            <tr>
              <td colspan="5" class="px-6 py-12 text-center text-slate-400 italic">
                No formulas configured yet. Click "Create Formula" to get started.
              </td>
            </tr>
          `;
          return;
        }

        data.forEach(item => {
          const tr = document.createElement("tr");
          tr.className = "hover:bg-slate-50/50 transition-colors";

          let statusBadge = "";
          if (item.is_published) {
            statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 uppercase">Published</span>';
          } else {
            statusBadge = '<span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 uppercase">Draft</span>';
          }

          let actions = [];
          if (item.latest_version_id) {
            actions.push(`<button onclick="editFormula(${item.id}, ${item.latest_version_id})" class="text-indigo-600 hover:text-indigo-900 font-bold hover:underline">Edit / Details</button>`);
          }

          tr.innerHTML = `
            <td class="px-6 py-4 font-bold text-slate-800">${item.name}</td>
            <td class="px-6 py-4 font-mono text-slate-500">${item.code}</td>
            <td class="px-6 py-4">${statusBadge}</td>
            <td class="px-6 py-4 text-slate-500 font-semibold">v${item.latest_version_num || 1}</td>
            <td class="px-6 py-4 text-right whitespace-nowrap">${actions.join("")}</td>
          `;
          formulasListBody.appendChild(tr);
        });
      })
      .catch(err => {
        console.error("Error loading formulas:", err);
        showToast("Error fetching formulas list.", "error");
      });
  }

  // --- Load details of formula version ---
  function loadVersionDetails(versionId) {
    fetch(`/module/FRMULA/api/version/${versionId}`)
      .then(res => res.json())
      .then(data => {
        selectedVersionId = data.version.id;
        selectedFormulaId = data.formula.id;
        isPublished = data.version.published_at !== null;

        dfName.value = data.formula.name;
        dfCode.value = data.formula.code;
        dfCode.disabled = true;
        expressionTextarea.value = data.version.expression;

        editorTitle.textContent = `Edit Formula · ${data.formula.name}`;
        
        let badgeClass = "bg-amber-100 text-amber-800";
        let statusLabel = "Draft";
        if (isPublished) {
          badgeClass = "bg-emerald-100 text-emerald-800";
          statusLabel = "Published";
        }
        editorStatusBadge.textContent = `v${data.version.version_number} (${statusLabel})`;
        editorStatusBadge.className = `px-2 py-0.5 rounded-full font-bold uppercase text-[9px] ${badgeClass}`;

        if (isPublished) {
          expressionTextarea.disabled = true;
          expressionTextarea.classList.add("bg-slate-50", "text-slate-500", "cursor-not-allowed");
          dfName.disabled = true;
          btnSaveFormula.classList.add("hidden");
          btnPublishFormula.classList.add("hidden");
        } else {
          expressionTextarea.disabled = false;
          expressionTextarea.classList.remove("bg-slate-50", "text-slate-500", "cursor-not-allowed");
          dfName.disabled = false;
          btnSaveFormula.classList.remove("hidden");
          btnSaveFormula.textContent = "Save Draft";
          btnPublishFormula.classList.remove("hidden");
        }

        scanVariablesAndInitPreview();
      })
      .catch(err => {
        console.error("Error loading version details:", err);
        showToast("Error loading formula details.", "error");
      });
  }

  // --- Operand insertion and Operator controls ---
  window.insertToken = function (token) {
    if (isPublished) return;
    const start = expressionTextarea.selectionStart;
    const end = expressionTextarea.selectionEnd;
    const text = expressionTextarea.value;
    const before = text.substring(0, start);
    const after = text.substring(end);

    const spacer = (text.trim() && start > 0 && text[start - 1] !== " ") ? " " : "";
    const spacerAfter = (after.trim() && after[0] !== " ") ? " " : "";

    expressionTextarea.value = before + spacer + token + spacerAfter + after;
    const pos = start + spacer.length + token.length + spacerAfter.length;
    expressionTextarea.setSelectionRange(pos, pos);
    expressionTextarea.focus();
    scanVariablesAndInitPreview();
  };

  window.insertOperator = function (op) {
    if (isPublished) return;
    const start = expressionTextarea.selectionStart;
    const end = expressionTextarea.selectionEnd;
    const text = expressionTextarea.value;
    const before = text.substring(0, start);
    const after = text.substring(end);

    expressionTextarea.value = before + op + after;
    const pos = start + op.length;
    expressionTextarea.setSelectionRange(pos, pos);
    expressionTextarea.focus();
    scanVariablesAndInitPreview();
  };

  // Bind palette constants click — also record the code so it's included in field_codes during validate/save
  document.querySelectorAll(".palette-btn-valset").forEach(btn => {
    btn.onclick = () => {
      insertedValsetCodes.add(btn.dataset.code);
      insertToken(btn.dataset.code);
    };
  });

  // Load fields dynamically on form context select change
  formVersionSelect.onchange = function () {
    const formVerId = formVersionSelect.value;
    if (!formVerId) return;

    fetch(`/module/FORMBLD/api/version/${formVerId}`)
      .then(res => res.json())
      .then(data => {
        const fieldsPalette = document.getElementById("fields-palette");
        fieldsPalette.innerHTML = "";
        
        const numericTypes = ["number", "integer", "decimal", "float", "numeric", "calculated"];
        const filtered = (data.fields || []).filter(f => numericTypes.includes(f.field_type.toLowerCase()));
        
        if (filtered.length === 0) {
          fieldsPalette.innerHTML = '<p class="text-xs text-slate-400 italic">No compatible numeric fields in this form.</p>';
          return;
        }

        filtered.forEach(field => {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "flex items-center justify-between p-2.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-left transition text-xs font-medium w-full";
          btn.dataset.code = field.field_code;
          btn.innerHTML = `
            <span class="font-semibold text-slate-700 truncate mr-2">${field.field_name}</span>
            <span class="font-mono bg-slate-50 text-slate-500 border border-slate-100 px-1.5 py-0.5 rounded-md truncate max-w-[120px]">${field.field_code}</span>
          `;
          btn.onclick = () => insertToken(field.field_code);
          fieldsPalette.appendChild(btn);
        });
      })
      .catch(err => {
        console.error("Error loading fields:", err);
      });
  };

  // Trigger form select load initially
  formVersionSelect.dispatchEvent(new Event("change"));

  // --- Real-time preview calculation ---
  function scanVariables() {
    const expr = expressionTextarea.value || "";
    const matches = expr.match(/[a-zA-Z_][a-zA-Z0-9_]*/g) || [];
    const forbidden = ["min", "max"];
    const unique = [];
    matches.forEach(m => {
      if (!forbidden.includes(m.toLowerCase()) && !unique.includes(m)) {
        unique.push(m);
      }
    });
    return unique;
  }

  function scanVariablesAndInitPreview() {
    const variables = scanVariables();
    // Cache current input values
    const prevValues = {};
    previewInputsGrid.querySelectorAll(".preview-var-input").forEach(inp => {
      prevValues[inp.dataset.var] = inp.value;
    });

    previewInputsGrid.innerHTML = "";

    if (variables.length === 0) {
      previewInputsGrid.innerHTML = '<p class="col-span-2 text-xs text-slate-400 italic">No variables detected in the formula expression yet.</p>';
      previewResultValue.textContent = "—";
      return;
    }

    variables.forEach(v => {
      const wrapper = document.createElement("div");
      wrapper.className = "flex flex-col space-y-1";
      const val = prevValues[v] !== undefined ? prevValues[v] : "1.0";
      wrapper.innerHTML = `
        <label class="text-[10px] font-bold text-slate-500 font-mono">${v}</label>
        <input type="number" step="any" value="${val}" data-var="${v}" class="preview-var-input block w-full rounded-lg border-slate-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-xs h-9 px-3 border">
      `;
      previewInputsGrid.appendChild(wrapper);
    });

    previewInputsGrid.querySelectorAll(".preview-var-input").forEach(input => {
      input.oninput = runLivePreview;
    });

    runLivePreview();
  }

  function runLivePreview() {
    const expr = expressionTextarea.value;
    if (!expr) {
      previewResultValue.textContent = "—";
      return;
    }

    const values = {};
    previewInputsGrid.querySelectorAll(".preview-var-input").forEach(input => {
      values[input.dataset.var] = input.value.trim();
    });

    if (window.FormulaRuntime) {
      const result = window.FormulaRuntime.evaluate(expr, values);
      if (result !== null && result !== undefined && !isNaN(result)) {
        previewResultValue.textContent = parseFloat(result.toFixed(6));
        previewResultValue.className = "text-lg font-black text-indigo-900";
      } else {
        previewResultValue.textContent = "Error / Incomplete";
        previewResultValue.className = "text-xs font-bold text-rose-600";
      }
    }
  }

  expressionTextarea.oninput = () => {
    scanVariablesAndInitPreview();
  };

  // --- Validate syntax ---
  btnValidate.onclick = function () {
    const expression = expressionTextarea.value.trim();
    if (!expression) {
      showToast("Formula expression is empty.", "error");
      return;
    }
    const variables = scanVariables();

    fetch("/module/FRMULA/api/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expression, field_codes: variables })
    })
      .then(res => res.json())
      .then(data => {
        validationResultContainer.classList.remove("hidden");
        if (data.valid) {
          validationResult.className = "p-3 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100";
          validationResult.textContent = "✓ Formula Syntax is Valid.";
        } else {
          validationResult.className = "p-3 rounded-lg text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-100";
          validationResult.textContent = `⚠ Syntax Error: ${data.error || "Invalid expression syntax."}`;
        }
      })
      .catch(err => {
        console.error("Error validating formula:", err);
        showToast("Error checking syntax.", "error");
      });
  };

  // --- Save Draft (async/await to fix broken promise chain) ---
  btnSaveFormula.onclick = async function () {
    const expression = expressionTextarea.value.trim();
    if (!expression) {
      showToast("Formula expression is empty.", "error");
      return;
    }
    const name = dfName.value.trim();
    if (!name) {
      showToast("Formula name is required.", "error");
      return;
    }

    // Build tokens from all detected variables (form fields + any valset codes used)
    const variables = scanVariables();
    const tokens = {};
    variables.forEach(v => tokens[v] = v);
    // Merge in any explicitly inserted valset codes (in case they overlap with variable scan)
    insertedValsetCodes.forEach(c => {
      if (variables.includes(c)) tokens[c] = c;
    });

    // All field codes to pass to validation = form variables + inserted valset codes
    const field_codes = [...new Set([...variables, ...insertedValsetCodes])];

    // Disable button to prevent double-clicks
    btnSaveFormula.disabled = true;
    const originalText = btnSaveFormula.textContent;
    btnSaveFormula.textContent = "Saving...";

    try {
      // Step 1: Validate expression
      const validateRes = await fetch("/module/FRMULA/api/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expression, field_codes })
      });
      const validateData = await validateRes.json();

      if (!validateData.valid) {
        showToast(`Syntax error: ${validateData.error}`, "error");
        return;
      }

      if (selectedFormulaId === null) {
        // Creating a new formula directly from the editor
        const code = dfCode.value.trim().toUpperCase().replace(/\s+/g, "_");
        if (!code) {
          showToast("Formula code is required.", "error");
          return;
        }
        const createRes = await fetch("/module/FRMULA/api", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, code, expression, tokens })
        });
        const createData = await createRes.json();
        if (createData.error) {
          showToast(createData.error, "error");
        } else {
          showToast("Formula created successfully!");
          showList();
        }
      } else {
        // Step 2: Update the formula name via PUT
        const putRes = await fetch(`/module/FRMULA/api/${selectedFormulaId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name })
        });
        const putData = await putRes.json();
        if (putData.error) {
          showToast(putData.error, "error");
          return;
        }

        // Step 3: Save the expression as a new draft version via POST
        const draftRes = await fetch(`/module/FRMULA/api/${selectedFormulaId}/new-version`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expression, tokens })
        });
        const draftData = await draftRes.json();
        if (draftData.error) {
          showToast(draftData.error, "error");
        } else {
          showToast("Formula draft saved successfully!");
          // Reload version to reflect new version id
          if (draftData.data && draftData.data.version_id) {
            selectedVersionId = draftData.data.version_id;
          }
          loadVersionDetails(selectedVersionId);
        }
      }
    } catch (err) {
      console.error("Error saving formula:", err);
      showToast("Failed to save formula. Check console for details.", "error");
    } finally {
      btnSaveFormula.disabled = false;
      btnSaveFormula.textContent = originalText;
    }
  };

  // --- Publish Version ---
  btnPublishFormula.onclick = async function () {
    if (!selectedVersionId) return;

    if (!confirm("Are you sure you want to publish this formula version? It will become active and immutable.")) {
      return;
    }

    btnPublishFormula.disabled = true;
    const originalText = btnPublishFormula.textContent;
    btnPublishFormula.textContent = "Publishing...";

    try {
      const res = await fetch(`/module/FRMULA/api/version/${selectedVersionId}/publish`, {
        method: "POST"
      });
      const resData = await res.json();
      if (resData.error) {
        showToast(resData.error, "error");
      } else {
        showToast("Formula published successfully!");
        showList();
      }
    } catch (err) {
      console.error("Error publishing formula:", err);
      showToast("Failed to publish formula.", "error");
    } finally {
      btnPublishFormula.disabled = false;
      btnPublishFormula.textContent = originalText;
    }
  };

  // Modal actions
  if (document.getElementById("btn-create-formula")) {
    document.getElementById("btn-create-formula").onclick = () => modalCreate.classList.remove("hidden");
  }
  btnCloseModal.onclick = () => modalCreate.classList.add("hidden");
  btnCancelModal.onclick = () => modalCreate.classList.add("hidden");

  formCreateFormula.onsubmit = function (e) {
    e.preventDefault();
    const name = document.getElementById("formula-name").value.trim();
    const code = document.getElementById("formula-code").value.trim().toUpperCase().replace(/\s+/g, "_");
    const expression = document.getElementById("formula-expression").value.trim();
    
    const variables = [];
    const matches = expression.match(/[a-zA-Z_][a-zA-Z0-9_]*/g) || [];
    matches.forEach(m => {
      if (m !== "min" && m !== "max" && !variables.includes(m)) variables.push(m);
    });
    const tokens = {};
    variables.forEach(v => tokens[v] = v);

    fetch("/module/FRMULA/api", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, code, expression, tokens })
    })
      .then(res => res.json())
      .then(resData => {
        if (resData.error) {
          showToast(resData.error, "error");
        } else {
          modalCreate.classList.add("hidden");
          document.getElementById("formula-name").value = "";
          document.getElementById("formula-code").value = "";
          document.getElementById("formula-expression").value = "";
          showToast("Formula created successfully!");
          
          // Refresh the formula list; user can click Edit to open editor
          loadFormulas();
          showList();
        }
      })
      .catch(err => {
        console.error("Error creating formula:", err);
        showToast("Failed to create formula.", "error");
      });
  };

  // Initial load
  loadFormulas();
});
