/* Native ports keep MV3 workers alive on Chromium 105 and newer. */
const clients = new Set();
let nativePort = null;
let retry = null;
let current = { type: "unavailable" };

function broadcast(message) {
  current = message;
  for (const client of clients) {
    try {
      client.postMessage(message);
    } catch {
      clients.delete(client);
    }
  }
  if (!clients.size) stopNative();
}

function stopNative() {
  clearTimeout(retry);
  retry = null;
  const port = nativePort;
  nativePort = null;
  current = { type: "unavailable" };
  port?.disconnect();
}

function scheduleRetry() {
  if (retry !== null || !clients.size) return;
  retry = setTimeout(() => {
    retry = null;
    connectNative();
  }, 5000);
}

function connectNative() {
  if (nativePort || !clients.size) return;
  clearTimeout(retry);
  retry = null;
  let port;
  try {
    port = chrome.runtime.connectNative(
      "io.github.iop098321qwe.omarchy_theme"
    );
  } catch {
    broadcast({ type: "unavailable" });
    scheduleRetry();
    return;
  }
  nativePort = port;
  port.onMessage.addListener((message) => {
    if (nativePort === port) broadcast(message);
  });
  port.onDisconnect.addListener(() => {
    // Read lastError so missing hosts do not produce unchecked API errors.
    void chrome.runtime.lastError;
    if (nativePort !== port) return;
    nativePort = null;
    broadcast({ type: "unavailable" });
    scheduleRetry();
  });
}

chrome.runtime.onConnect.addListener((client) => {
  const url = client.sender?.url || "";
  if (client.name !== "omarchy-theme" || !url.startsWith(
    "https://iop098321qwe.github.io/main_page/"
  )) {
    client.disconnect();
    return;
  }
  clients.add(client);
  client.onDisconnect.addListener(() => {
    clients.delete(client);
    if (clients.size) return;
    stopNative();
  });
  try {
    client.postMessage(current);
  } catch {
    clients.delete(client);
    if (!clients.size) stopNative();
    return;
  }
  // Joining tabs use the pending retry, rather than spawning more attempts.
  if (retry === null) connectNative();
});
