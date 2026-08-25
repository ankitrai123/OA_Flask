(function () {
  const slides = Array.from(document.querySelectorAll(".slide"));
  const dotsContainer = document.getElementById("nav-dots");
  const prevBtn = document.getElementById("nav-prev");
  const nextBtn = document.getElementById("nav-next");

  let current = 0;
  const onActivate = [];

  slides.forEach((_, i) => {
    const dot = document.createElement("button");
    dot.className = "dot";
    dot.setAttribute("aria-label", `Go to slide ${i + 1}`);
    dot.addEventListener("click", () => goTo(i));
    dotsContainer.appendChild(dot);
  });
  const dots = Array.from(dotsContainer.children);

  function render() {
    slides.forEach((s, i) => s.classList.toggle("active", i === current));
    dots.forEach((d, i) => d.classList.toggle("active", i === current));
    prevBtn.disabled = current === 0;
    nextBtn.disabled = current === slides.length - 1;
    onActivate.forEach((fn) => fn(current));
  }

  function goTo(i) {
    if (i < 0 || i >= slides.length) return;
    current = i;
    render();
  }

  prevBtn.addEventListener("click", () => goTo(current - 1));
  nextBtn.addEventListener("click", () => goTo(current + 1));

  document.addEventListener("keydown", (e) => {
    if (document.getElementById("chat-input") === document.activeElement) return;
    if (e.key === "ArrowRight") goTo(current + 1);
    if (e.key === "ArrowLeft") goTo(current - 1);
  });

  let touchStartX = null;
  document.addEventListener("touchstart", (e) => { touchStartX = e.touches[0].clientX; });
  document.addEventListener("touchend", (e) => {
    if (touchStartX === null) return;
    const dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 60) goTo(current + (dx < 0 ? 1 : -1));
    touchStartX = null;
  });

  window.Slides = {
    onActivate: (fn) => onActivate.push(fn),
    current: () => current,
  };

  // Deferred until DOMContentLoaded so dashboard.js/agent.js (loaded after
  // this file) have already registered their onActivate callbacks — otherwise
  // this first render fires before anything is listening and slide 0 loads blank.
  document.addEventListener("DOMContentLoaded", render);
})();
