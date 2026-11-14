const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const directory = path.join(__dirname, "../extension");

function event() {
  const listeners = [];
  return {
    addListener: (fn) => listeners.push(fn),
    fire: (...args) => listeners.forEach((fn) => fn(...args)),
  };
}

test("content applies complete palettes and restores CSS defaults", () => {
  const properties = new Map();
  const root = {
    style: {
      setProperty: (name, value) => properties.set(name, value),
      removeProperty: (name) => properties.delete(name),
    },
    dataset: {},
  };
  const port = { onMessage: event(), onDisconnect: event() };
  const timers = new Map();
  let timerID = 0;
  const domReady = event();
  vm.runInNewContext(fs.readFileSync(
    path.join(directory, "content.js"), "utf8"
  ), {
    document: {
      documentElement: root,
      addEventListener: (_, fn) => domReady.addListener(fn),
    },
    chrome: { runtime: { connect: () => port } },
    setTimeout: (fn) => { timers.set(++timerID, fn); return timerID; },
    clearTimeout: (id) => timers.delete(id),
  });
  const css = fs.readFileSync(path.join(__dirname, "fixtures/palette.css"), "utf8");
  const colors = Object.fromEntries([...css.matchAll(
    /--ctp-([a-z0-9]+): (#[0-9a-f]{6});/g
  )].map((match) => [match[1], match[2]]));
  const palette = { type: "palette", colors, scheme: "dark" };
  port.onMessage.fire(palette);
  assert.equal(properties.get("--ctp-base"), "#1e1e2e");
  assert.equal(root.dataset.omarchyTheme, "active");
  domReady.fire();
  port.onMessage.fire({
    ...palette, scheme: "light", colors: { ...colors, base: "#ffffff" },
  });
  assert.equal(properties.get("--ctp-base"), "#ffffff");
  assert.equal(properties.get("color-scheme"), "light");
  port.onMessage.fire({ ...palette, colors: { base: "url(evil)" } });
  assert.equal(properties.size, 0);
  assert.equal(root.dataset.omarchyTheme, undefined);
  port.onMessage.fire(palette);
  [...timers.values()][0]();
  assert.equal(properties.size, 0, "Stalled host must expire");
  port.onMessage.fire(palette);
  port.onDisconnect.fire();
  assert.equal(properties.size, 0, "Disconnect must restore Catppuccin");
});

test("background shares one host, updates new tabs, and reconnects", () => {
  const onConnect = event();
  const nativePorts = [];
  const retries = [];
  const context = {
    chrome: {
      runtime: {
        onConnect,
        connectNative: () => {
          const port = {
            onMessage: event(), onDisconnect: event(), closed: false,
            disconnect() { this.closed = true; },
          };
          nativePorts.push(port);
          return port;
        },
      },
    },
    setTimeout: (fn) => { retries.push(fn); return retries.length; },
    clearTimeout: () => {},
  };
  vm.runInNewContext(fs.readFileSync(
    path.join(directory, "background.js"), "utf8"
  ), context);
  function client(url = "https://iop098321qwe.github.io/main_page/") {
    return {
      name: "omarchy-theme", sender: { url }, onDisconnect: event(),
      messages: [], closed: false,
      postMessage(message) { this.messages.push(message); },
      disconnect() { this.closed = true; },
    };
  }
  const rejected = client("https://example.com/");
  onConnect.fire(rejected);
  assert.equal(rejected.closed, true);
  const first = client();
  onConnect.fire(first);
  const palette = { type: "palette", colors: { base: "#123456" } };
  nativePorts[0].onMessage.fire(palette);
  const second = client();
  onConnect.fire(second);
  assert.equal(nativePorts.length, 1);
  assert.equal(second.messages.at(-1), palette);
  nativePorts[0].onDisconnect.fire();
  assert.equal(first.messages.at(-1).type, "unavailable");
  retries[0]();
  assert.equal(nativePorts.length, 2);
  first.onDisconnect.fire();
  assert.equal(nativePorts[1].closed, false);
  second.onDisconnect.fire();
  assert.equal(nativePorts[1].closed, true);
});
