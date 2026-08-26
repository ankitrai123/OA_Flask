(function () {
  // The chat itself is wired by agent.js (wireChat), shared with the
  // floating panel so both surfaces share one conversation history. This
  // module just focuses the input when the slide becomes active.
  Slides.onActivate((index) => {
    if (index === 10) {
      const input = document.getElementById("page-chat-input");
      if (input) input.focus();
    }
  });
})();
