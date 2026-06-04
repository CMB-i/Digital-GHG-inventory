(function () {
  document.querySelectorAll("[data-indian-mobile]").forEach(function (input) {
    input.addEventListener("input", function () {
      input.value = input.value.replace(/\D/g, "").slice(0, 10);
    });
  });
})();
