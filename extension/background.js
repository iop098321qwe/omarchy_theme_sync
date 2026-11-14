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
}

function connectNative() {
  if (nativePort || !clients.size) return;
  const port = chrome.runtime.connectNative(
    "io.github.iop098321qwe.omarchy_theme"
  );
  nativePort = port;
  port.onMessage.addListener(broadcast);
  port.onDisconnect.addListener(() => {
    // Read lastError so missing hosts do not produce unchecked API errors.
    void chrome.runtime.lastError;
    if (nativePort !== port) return;
    nativePort = null;
    broadcast({ type: "unavailable" });
    if (clients.size) retry = setTimeout(connectNative, 5000);
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
  client.postMessage(current);
  connectNative();
  client.onDisconnect.addListener(() => {
    clients.delete(client);
    if (clients.size) return;
    clearTimeout(retry);
    const port = nativePort;
    nativePort = null;
    current = { type: "unavailable" };
    port?.disconnect();
  });
});
