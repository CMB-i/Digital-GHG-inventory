(function () {
  const allowedModes = [
    "builder_preview",
    "spoc_entry",
    "readonly_review",
    "report_view",
  ];

  window.renderForm = function renderForm(config, targetElement, mode, values = {}, options = {}) {
    if (!allowedModes.includes(mode)) {
      throw new Error("Unsupported form render mode: " + mode);
    }

    if (!targetElement) {
      throw new Error("targetElement is required");
    }

    // Clear existing content
    targetElement.innerHTML = "";

    // Normalize config to fields array
    let fields = [];
    if (Array.isArray(config)) {
      fields = config;
    } else if (config && Array.isArray(config.fields)) {
      fields = config.fields;
    }

    // Sort fields by display_order if present
    fields = [...fields].sort((a, b) => (a.display_order || 0) - (b.display_order || 0));

    if (fields.length === 0) {
      const emptyState = document.createElement("div");
      emptyState.className = "text-center py-8 text-slate-400 italic text-sm";
      emptyState.textContent = "No fields configured for this form.";
      targetElement.appendChild(emptyState);
      return;
    }

    // Form Container
    const formContainer = document.createElement("div");
    formContainer.className = "space-y-5 bg-white p-6 rounded-xl border border-slate-200/80 shadow-sm";

    // Recalculate function to run client-side previews
    function recalculate() {
      let changed = true;
      let passes = 0;
      // Loop until values stabilize or we hit limit (handles chaining)
      while (changed && passes < 10) {
        changed = false;
        passes++;
        fields.forEach(field => {
          if (field.field_type === "calculated" && field.field_config && field.field_config.expression) {
            const oldVal = values[field.field_code];
            const newVal = window.FormulaRuntime ? window.FormulaRuntime.evaluate(field.field_config.expression, values) : null;

            const oldNumeric = oldVal !== undefined && oldVal !== null && oldVal !== "" ? parseFloat(oldVal) : null;
            const newNumeric = newVal !== null && newVal !== undefined ? parseFloat(newVal) : null;

            if (oldNumeric !== newNumeric) {
              if (newNumeric === null) {
                values[field.field_code] = "";
              } else {
                values[field.field_code] = newNumeric;
              }
              changed = true;

              // Update input in DOM
              const inputEl = targetElement.querySelector(`[name="${field.field_code}"]`);
              if (inputEl) {
                inputEl.value = newNumeric !== null ? parseFloat(newNumeric.toFixed(6)) : "";
              }
            }
          }
        });
      }
    }

    // Render each field
    fields.forEach(field => {
      const fieldConfig = field.field_config || {};
      
      const row = document.createElement("div");
      row.className = "flex flex-col md:flex-row md:items-start space-y-2 md:space-y-0 md:space-x-6 border-b border-slate-100 pb-5 last:border-b-0 last:pb-0";
      row.dataset.fieldCode = field.field_code;
      row.dataset.fieldType = field.field_type;

      // 1. Label Column
      const labelCol = document.createElement("div");
      labelCol.className = "w-full md:w-1/3 flex flex-col justify-start pt-1.5";

      const label = document.createElement("label");
      label.className = "text-sm font-semibold text-slate-700 flex items-center";
      label.textContent = field.field_name || field.field_code;

      // Add required asterisk
      if (fieldConfig.is_required) {
        const asterisk = document.createElement("span");
        asterisk.className = "text-rose-500 ml-1";
        asterisk.textContent = "*";
        label.appendChild(asterisk);
      }
      labelCol.appendChild(label);

      // Add help text/description
      if (fieldConfig.help_text) {
        const helpText = document.createElement("p");
        helpText.className = "text-xs text-slate-500 mt-1 leading-relaxed";
        helpText.textContent = fieldConfig.help_text;
        labelCol.appendChild(helpText);
      }

      // 2. Input Column
      const inputCol = document.createElement("div");
      inputCol.className = "w-full md:w-2/3 flex flex-col";

      const inputWrapper = document.createElement("div");
      inputWrapper.className = "relative flex rounded-lg shadow-sm w-full transition-all duration-200";

      // Input field element
      let inputEl;

      if (field.field_type === "dropdown") {
        // Dropdown Element
        inputEl = document.createElement("select");
        inputEl.className = "form-select block w-full rounded-lg border-slate-300 bg-white text-slate-800 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm h-10 px-3 transition-colors";
        
        const defaultOpt = document.createElement("option");
        defaultOpt.value = "";
        defaultOpt.textContent = "Select an option...";
        inputEl.appendChild(defaultOpt);

        if (Array.isArray(fieldConfig.options)) {
          fieldConfig.options.forEach(opt => {
            const optEl = document.createElement("option");
            optEl.value = opt.entry_code || opt.code;
            optEl.textContent = opt.entry_label || opt.label || opt.entry_code || opt.code;
            if (values[field.field_code] === optEl.value) {
              optEl.selected = true;
            }
            inputEl.appendChild(optEl);
          });
        }
      } else if (field.field_type === "date") {
        // Date Element
        inputEl = document.createElement("input");
        inputEl.type = "date";
        inputEl.className = "form-input block w-full rounded-lg border-slate-300 text-slate-800 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm h-10 px-3 transition-colors";
        inputEl.value = values[field.field_code] || "";
      } else if (field.field_type === "boolean") {
        // Boolean Checkbox Element
        inputEl = document.createElement("input");
        inputEl.type = "checkbox";
        inputEl.className = "form-checkbox rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-5 w-5 my-2.5 transition-colors";
        
        let val = values[field.field_code];
        if (val && typeof val === "object") {
          val = val.raw_value;
        }
        inputEl.checked = (val === true || val === "true" || val === "1" || val === 1 || val === "on");
      } else if (field.field_type === "file") {
        // File Element Container
        const fileContainer = document.createElement("div");
        fileContainer.className = "w-full";

        const currentFile = values[field.field_code];
        let fileKey = "";
        let fileName = "";
        if (currentFile) {
          if (typeof currentFile === "object") {
            fileKey = currentFile.storage_key || "";
            fileName = currentFile.original_name || "";
          } else {
            fileKey = currentFile;
            fileName = currentFile.split("/").pop();
          }
        }

        if (fileKey) {
          // File already uploaded
          const fileCard = document.createElement("div");
          fileCard.className = "flex items-center justify-between p-3 rounded-lg border border-slate-200 bg-slate-50 shadow-sm";

          const fileInfo = document.createElement("div");
          fileInfo.className = "flex items-center space-x-2.5 overflow-hidden";

          const fileIcon = document.createElement("span");
          fileIcon.className = "text-slate-400 flex-shrink-0";
          fileIcon.innerHTML = `
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          `;

          const fileLink = document.createElement("a");
          fileLink.href = `/spoc/submissions/download/${fileKey}`;
          fileLink.className = "text-sm font-semibold text-indigo-600 hover:text-indigo-700 underline truncate";
          fileLink.textContent = fileName || "Download Uploaded File";
          fileLink.target = "_blank";

          fileInfo.appendChild(fileIcon);
          fileInfo.appendChild(fileLink);
          fileCard.appendChild(fileInfo);

          if (mode === "spoc_entry") {
            const removeBtn = document.createElement("button");
            removeBtn.type = "button";
            removeBtn.className = "text-xs font-semibold text-rose-600 hover:text-rose-700 focus:outline-none transition-colors ml-4 flex-shrink-0";
            removeBtn.textContent = "Remove";
            removeBtn.onclick = function () {
              delete values[field.field_code];
              renderForm(config, targetElement, mode, values, options);
              if (options.onValueChange) {
                options.onValueChange(field.field_code, null, values);
              }
            };
            fileCard.appendChild(removeBtn);
          }

          fileContainer.appendChild(fileCard);
        } else {
          // File upload UI
          if (mode === "spoc_entry") {
            const dropzone = document.createElement("div");
            dropzone.className = "relative border-2 border-dashed border-slate-300 hover:border-indigo-500 rounded-xl p-4 text-center cursor-pointer bg-slate-50/50 hover:bg-slate-50 transition-all flex flex-col items-center justify-center group";

            const uploadIcon = document.createElement("span");
            uploadIcon.className = "text-slate-400 group-hover:text-indigo-500 transition-colors";
            uploadIcon.innerHTML = `
              <svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            `;

            const labelTxt = document.createElement("span");
            labelTxt.className = "mt-2 block text-xs font-bold text-slate-700 group-hover:text-indigo-600 transition-colors";
            labelTxt.textContent = "Click or drag file here to upload proof";

            const subTxt = document.createElement("span");
            subTxt.className = "block text-[10px] text-slate-400 mt-1";
            let formats = "Any file format";
            if (Array.isArray(fieldConfig.accepted_mime_types)) {
              formats = fieldConfig.accepted_mime_types.join(", ");
            }
            subTxt.textContent = formats;

            const fileInput = document.createElement("input");
            fileInput.type = "file";
            fileInput.className = "hidden";
            fileInput.id = "file_" + field.field_code;
            if (Array.isArray(fieldConfig.accepted_mime_types)) {
              fileInput.accept = fieldConfig.accepted_mime_types.join(",");
            }

            // Upload handler
            fileInput.onchange = function (e) {
              const file = e.target.files[0];
              if (!file) return;

              labelTxt.textContent = "Uploading " + file.name + "...";
              labelTxt.className = "mt-2 block text-xs font-bold text-indigo-600 animate-pulse";

              if (options.onFileUpload) {
                options.onFileUpload(field.field_code, file, function (err, result) {
                  if (err) {
                    alert("Upload failed: " + err);
                    renderForm(config, targetElement, mode, values, options);
                  } else {
                    values[field.field_code] = result;
                    renderForm(config, targetElement, mode, values, options);
                    if (options.onValueChange) {
                      options.onValueChange(field.field_code, result, values);
                    }
                  }
                });
              } else {
                // Mock direct upload
                setTimeout(() => {
                  const mockResult = {
                    storage_key: "proofs/" + Date.now() + "_" + file.name,
                    original_name: file.name
                  };
                  values[field.field_code] = mockResult;
                  renderForm(config, targetElement, mode, values, options);
                  if (options.onValueChange) {
                    options.onValueChange(field.field_code, mockResult, values);
                  }
                }, 800);
              }
            };

            // Drag and drop event listeners
            dropzone.addEventListener("dragover", (e) => {
              e.preventDefault();
              dropzone.classList.remove("border-slate-300");
              dropzone.classList.add("border-indigo-500", "bg-indigo-50/50");
            });

            dropzone.addEventListener("dragleave", () => {
              dropzone.classList.remove("border-indigo-500", "bg-indigo-50/50");
              dropzone.classList.add("border-slate-300");
            });

            dropzone.addEventListener("drop", (e) => {
              e.preventDefault();
              dropzone.classList.remove("border-indigo-500", "bg-indigo-50/50");
              dropzone.classList.add("border-slate-300");
              if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                fileInput.dispatchEvent(new Event("change"));
              }
            });

            dropzone.onclick = () => fileInput.click();
            dropzone.appendChild(uploadIcon);
            dropzone.appendChild(labelTxt);
            dropzone.appendChild(subTxt);
            dropzone.appendChild(fileInput);
            fileContainer.appendChild(dropzone);
          } else {
            // Readonly/builder mode without file
            const emptyFile = document.createElement("div");
            emptyFile.className = "text-sm text-slate-400 italic py-2";
            emptyFile.textContent = "No proof file uploaded";
            fileContainer.appendChild(emptyFile);
          }
        }

        inputWrapper.appendChild(fileContainer);
      } else {
        // Standard inputs: text, number, calculated
        inputEl = document.createElement("input");
        inputEl.id = "field_" + field.field_code;
        inputEl.name = field.field_code;

        if (field.field_type === "calculated") {
          inputEl.type = "number";
          inputEl.className = "form-input block w-full rounded-lg border-indigo-200 bg-indigo-50/40 text-indigo-950 font-bold focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm h-10 px-3 transition-colors select-all";
          inputEl.readOnly = true;
          inputEl.disabled = true;

          // Fetch precalculated or calculate value
          let val = values[field.field_code] || "";
          if (val && typeof val === "object") {
            val = val.calculated_value !== undefined ? val.calculated_value : (val.raw_value || "");
          }
          inputEl.value = val;
        } else {
          // text or number input
          inputEl.type = field.field_type === "number" ? "number" : "text";
          inputEl.className = "form-input block w-full rounded-lg border-slate-300 text-slate-800 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm h-10 px-3 transition-colors";
          
          if (field.field_type === "number") {
            if (fieldConfig.min !== undefined) inputEl.min = fieldConfig.min;
            if (fieldConfig.max !== undefined) inputEl.max = fieldConfig.max;
            inputEl.step = "any";
          }
          
          let val = values[field.field_code] || "";
          if (val && typeof val === "object") {
            val = val.raw_value || "";
          }
          inputEl.value = val;
        }
      }

      // For interactive fields (dropdown, date, text, number, boolean), apply disabled/readonly depending on mode
      if (inputEl && field.field_type !== "calculated") {
        if (mode !== "spoc_entry") {
          inputEl.disabled = true;
          if (field.field_type !== "boolean") {
            inputEl.classList.add("bg-slate-50", "text-slate-500", "border-slate-200", "cursor-not-allowed");
          } else {
            inputEl.classList.add("cursor-not-allowed");
          }
        } else {
          // Listeners for SPOC Entry (dynamic recalculation)
          const handler = function () {
            if (field.field_type === "boolean") {
              values[field.field_code] = inputEl.checked;
            } else {
              values[field.field_code] = inputEl.value;
            }
            recalculate();
            if (options.onValueChange) {
              options.onValueChange(field.field_code, values[field.field_code], values);
            }
          };

          if (field.field_type === "boolean") {
            inputEl.addEventListener("change", handler);
          } else {
            inputEl.addEventListener("input", handler);
            inputEl.addEventListener("change", handler);
          }
        }

        // Handle Unit styling
        if (fieldConfig.unit) {
          inputEl.classList.remove("rounded-lg");
          inputEl.classList.add("rounded-l-lg");
          inputWrapper.appendChild(inputEl);

          const unitBadge = document.createElement("span");
          unitBadge.className = `inline-flex items-center px-3.5 rounded-r-lg border border-l-0 ${
            field.field_type === "calculated"
              ? "border-indigo-200 bg-indigo-50 text-indigo-600"
              : "border-slate-300 bg-slate-50 text-slate-500"
          } text-xs font-semibold sm:text-sm h-10 whitespace-nowrap`;
          unitBadge.textContent = fieldConfig.unit;
          inputWrapper.appendChild(unitBadge);
        } else {
          inputWrapper.appendChild(inputEl);
        }
      }

      // Calculated Field Badge
      if (field.field_type === "calculated" && inputWrapper) {
        const calcBadge = document.createElement("span");
        calcBadge.className = "absolute right-3.5 top-2.5 bg-indigo-100 text-indigo-700 text-[10px] px-2 py-0.5 rounded-md font-bold pointer-events-none tracking-wider uppercase";
        if (fieldConfig.unit) {
          calcBadge.style.right = "4.2rem";
        }
        calcBadge.textContent = "Calculated";
        inputWrapper.appendChild(calcBadge);
      }

      inputCol.appendChild(inputWrapper);

      // 3. Error container
      const errorMsg = document.createElement("p");
      errorMsg.className = "mt-1.5 text-xs font-medium text-rose-600 hidden";
      errorMsg.id = "error_" + field.field_code;
      
      // Inject validation errors if present
      if (options.validationErrors && options.validationErrors[field.field_code]) {
        errorMsg.textContent = options.validationErrors[field.field_code];
        errorMsg.classList.remove("hidden");
      }
      
      inputCol.appendChild(errorMsg);

      // Append columns to row
      row.appendChild(labelCol);
      row.appendChild(inputCol);

      formContainer.appendChild(row);
    });

    targetElement.appendChild(formContainer);

    // Initial recalculation pass in case formulas depend on loaded values
    recalculate();
  };
})();
