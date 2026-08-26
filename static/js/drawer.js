(function () {
  function wire(root = document) {
    root.querySelectorAll("[data-drawer]:not([data-drawer-wired])").forEach((el) => {
      el.setAttribute("data-drawer-wired", "1");
      const trigger = el.querySelector(".drawer-trigger");
      if (trigger) trigger.addEventListener("click", () => el.classList.toggle("open"));
    });
  }

  window.Drawer = { wire };
  document.addEventListener("DOMContentLoaded", () => wire());
})();
