(function () {
  const slides = Array.from(document.querySelectorAll(".slide"));
  const navContainer = document.getElementById("sidebar-nav");
  const progressEl = document.getElementById("sidebar-progress");
  const prevBtn = document.getElementById("nav-prev");
  const nextBtn = document.getElementById("nav-next");

  let current = 0;
  const onActivate = [];

  slides.forEach((slide, i) => {
    const li = document.createElement("li");
    const btn = document.createElement("button");
    btn.className = "sidebar-nav-item";
    btn.textContent = slide.dataset.slideTitle || `Slide ${i + 1}`;
    btn.addEventListener("click", () => goTo(i));
    li.appendChild(btn);
    navContainer.appendChild(li);
  });
  const navItems = Array.from(navContainer.querySelectorAll(".sidebar-nav-item"));

  function render() {
    slides.forEach((s, i) => s.classList.toggle("active", i === current));
    navItems.forEach((item, i) => item.classList.toggle("active", i === current));
    progressEl.textContent = `${current + 1} / ${slides.length}`;
    prevBtn.disabled = current === 0;
    nextBtn.disabled = current === slides.length - 1;
    onActivate.forEach((fn) => {
      try {
        fn(current);
      } catch (err) {
        console.error("A slide-activate callback threw", err);
      }
    });
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

  // Deferred until DOMContentLoaded so the per-slide modules (loaded after
  // this file) have already registered their onActivate callbacks —
  // otherwise this first render fires before anything is listening and
  // slide 0 loads blank.
  document.addEventListener("DOMContentLoaded", render);
})();
