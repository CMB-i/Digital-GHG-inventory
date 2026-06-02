(function () {
  const allowedModes = [
    "builder_preview",
    "spoc_entry",
    "readonly_review",
    "report_view",
  ];

  window.renderForm = function renderForm(config, targetElement, mode) {
    if (!allowedModes.includes(mode)) {
      throw new Error("Unsupported form render mode: " + mode);
    }

    if (!targetElement) {
      throw new Error("targetElement is required");
    }

    targetElement.innerHTML = "";
    const placeholder = document.createElement("div");
    placeholder.className = "rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600";
    placeholder.textContent = "Form renderer placeholder for " + mode + ".";
    targetElement.appendChild(placeholder);
  };
})();
