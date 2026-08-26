(function () {
  const KEY = "peyala-pulse-mode";

  function apply(mode) {
    document.body.classList.toggle("mode-analyst", mode === "analyst");
    document.body.classList.toggle("mode-executive", mode !== "analyst");
    document.querySelectorAll(".mode-toggle-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mode === mode);
    });
  }

  function get() {
    return localStorage.getItem(KEY) || "executive";
  }

  const listeners = [];

  function set(mode) {
    localStorage.setItem(KEY, mode);
    apply(mode);
    listeners.forEach((fn) => fn(mode));
  }

  document.addEventListener("DOMContentLoaded", () => {
    apply(get());
    document.querySelectorAll(".mode-toggle-btn").forEach((btn) =>
      btn.addEventListener("click", () => set(btn.dataset.mode))
    );
  });

  window.Mode = { get, set, onChange: (fn) => listeners.push(fn) };
})();
