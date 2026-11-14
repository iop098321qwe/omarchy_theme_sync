(() => {
  const names = [
    "rosewater", "flamingo", "pink", "mauve", "red", "maroon",
    "peach", "yellow", "green", "teal", "sky", "sapphire", "blue",
    "lavender", "text", "subtext1", "subtext0", "overlay2", "overlay1",
    "overlay0", "surface2", "surface1", "surface0", "base", "mantle",
    "crust",
  ];
  let watchdog;
  let pending = { type: "unavailable" };

  function reset() {
    const root = document.documentElement;
    if (!root) return;
    for (const name of names) root.style.removeProperty(`--ctp-${name}`);
    root.style.removeProperty("color-scheme");
    delete root.dataset.omarchyTheme;
  }

  function apply(message) {
    clearTimeout(watchdog);
    pending = message;
    if (!document.documentElement) return;
    const valid = message?.type === "palette" &&
      ["light", "dark"].includes(message.scheme) &&
      names.every((name) => /^#[0-9a-f]{6}$/i.test(
        message.colors?.[name] || ""
      ));
    if (!valid) {
      reset();
      return;
    }
    const root = document.documentElement;
    for (const name of names) {
      root.style.setProperty(`--ctp-${name}`, message.colors[name]);
    }
    root.style.setProperty("color-scheme", message.scheme);
    root.dataset.omarchyTheme = "active";
    // Fall back if the native process hangs without closing its connection.
    watchdog = setTimeout(reset, 25000);
  }

  function connect() {
    try {
      const port = chrome.runtime.connect({ name: "omarchy-theme" });
      port.onMessage.addListener(apply);
      port.onDisconnect.addListener(() => {
        void chrome.runtime.lastError;
        apply({ type: "unavailable" });
        setTimeout(connect, 5000);
      });
    } catch {
      // An extension update invalidates old content contexts. Reload the page
      // to attach the new context; never leave a stale palette behind.
      apply({ type: "unavailable" });
    }
  }

  document.addEventListener("DOMContentLoaded", () => apply(pending), {
    once: true,
  });
  connect();
})();
