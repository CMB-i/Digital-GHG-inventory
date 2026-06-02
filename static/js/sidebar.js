(function () {
  const links = document.querySelectorAll(".nav-link");
  const currentPath = window.location.pathname;

  links.forEach(function (link) {
    if (link.getAttribute("href") === currentPath) {
      link.classList.add("bg-slate-100", "text-slate-950", "font-medium");
    }
  });
})();
