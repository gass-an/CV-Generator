document.addEventListener("click", async (event) => {
  const toggle = event.target.closest("[data-toggle-secret]");
  if (toggle) {
    const input = document.getElementById(toggle.dataset.toggleSecret);
    input.type = input.type === "password" ? "text" : "password";
    toggle.textContent = input.type === "password" ? "Afficher" : "Masquer";
  }
  const copy = event.target.closest("[data-copy-secret]");
  if (copy) {
    const input = document.getElementById(copy.dataset.copySecret);
    await navigator.clipboard.writeText(input.value);
    copy.textContent = "Copiée";
  }
});

document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
    return;
  }
  if (event.target.hasAttribute("data-single-submit")) {
    const button = event.target.querySelector("button[type='submit']");
    button.disabled = true;
    button.textContent = "Création…";
  }
});
