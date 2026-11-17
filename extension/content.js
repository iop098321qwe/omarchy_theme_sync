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
  let appliedRoot = null;
  let applied = null;

  function reset() {
    pending = { type: "unavailable" };
    const root = document.documentElement;
    applied = null;
    if (root !== appliedRoot) return;
    appliedRoot = null;
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
      if (root !== appliedRoot ||
          applied?.colors[name] !== message.colors[name]) {
        root.style.setProperty(`--ctp-${name}`, message.colors[name]);
      }
    }
    if (root !== appliedRoot || applied?.scheme !== message.scheme) {
      root.style.setProperty("color-scheme", message.scheme);
    }
    if (root !== appliedRoot) root.dataset.omarchyTheme = "active";
    appliedRoot = root;
    applied = { colors: { ...message.colors }, scheme: message.scheme };
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

  document.addEventListener("DOMContentLoaded", () => {
    // DOM readiness is not a host heartbeat and must not extend expiry.
    if (document.documentElement !== appliedRoot) apply(pending);
  }, {
    once: true,
  });
  // document_start can precede <html>; apply as soon as it appears instead
  // of waiting for every deferred script and stylesheet to finish loading.
  if (!document.documentElement) {
    const observer = new MutationObserver(() => {
      if (!document.documentElement) return;
      observer.disconnect();
      apply(pending);
    });
    observer.observe(document, { childList: true });
  }
  connect();
})();
