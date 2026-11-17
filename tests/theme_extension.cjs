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

function contentHarness(hasRoot = true) {
  const writes = [];
  const root = {
    style: {
      setProperty: (...args) => writes.push(args),
      removeProperty: (name) => writes.push([name]),
    },
    dataset: {},
  };
  const port = { onMessage: event(), onDisconnect: event() };
  const timers = new Map();
  let nextID = 0;
  let mutation;
  let disconnected = false;
  const domReady = event();
  const document = {
    documentElement: hasRoot ? root : null,
    addEventListener: (_, fn) => domReady.addListener(fn),
  };
  vm.runInNewContext(fs.readFileSync(
    path.join(directory, "content.js"), "utf8"
  ), {
    document,
    MutationObserver: class {
      constructor(callback) { mutation = callback; }
      observe() {}
      disconnect() { disconnected = true; }
    },
    chrome: { runtime: { connect: () => port } },
    setTimeout: (fn) => { timers.set(++nextID, fn); return nextID; },
    clearTimeout: (id) => timers.delete(id),
  });
  const css = fs.readFileSync(path.join(__dirname, "fixtures/palette.css"), "utf8");
  const colors = Object.fromEntries([...css.matchAll(
    /--ctp-([a-z0-9]+): (#[0-9a-f]{6});/g
  )].map((match) => [match[1], match[2]]));
  return {
    writes, root, port, timers, document, domReady,
    palette: { type: "palette", colors, scheme: "dark" },
    attachRoot() {
      document.documentElement = root;
      mutation();
      assert.equal(disconnected, true);
    },
  };
}

test("heartbeats refresh expiry without CSS writes; changes update one token",
  () => {
    const { port, timers, palette, writes, root } = contentHarness();
    port.onMessage.fire(palette);
    assert.equal(writes.length, 27);
    const firstWatchdog = [...timers.keys()][0];
    for (let i = 0; i < 20; i++) {
      port.onMessage.fire(JSON.parse(JSON.stringify(palette)));
    }
    assert.equal(writes.length, 27);
    assert.equal(timers.size, 1);
    assert.equal(timers.has(firstWatchdog), false);
    port.onMessage.fire({
      ...palette, colors: { ...palette.colors, base: "#123456" },
    });
    assert.deepEqual(writes.at(-1), ["--ctp-base", "#123456"]);
    assert.equal(writes.length, 28);
    [...timers.values()][0]();
    assert.equal(root.dataset.omarchyTheme, undefined);
    port.onMessage.fire(palette);
    assert.equal(writes.length, 82, "Expired palettes must fully reapply");
    port.onMessage.fire({ type: "unavailable" });
    const afterReset = writes.length;
    port.onMessage.fire({ type: "unavailable" });
    assert.equal(writes.length, afterReset, "Defaults need no repeated cleanup");
  });

test("pending palette applies when html appears before DOMContentLoaded", () => {
  const harness = contentHarness(false);
  harness.port.onMessage.fire(harness.palette);
  assert.equal(harness.writes.length, 0);
  harness.attachRoot();
  assert.equal(harness.writes.length, 27);
  assert.equal(harness.root.dataset.omarchyTheme, "active");
});

test("DOM readiness cannot extend expiry or revive an expired palette", () => {
  const { port, palette, timers, domReady, root, writes } = contentHarness();
  port.onMessage.fire(palette);
  const watchdog = [...timers.keys()][0];
  domReady.fire();
  assert.equal(timers.has(watchdog), true);
  timers.get(watchdog)();
  const afterReset = writes.length;
  domReady.fire();
  assert.equal(writes.length, afterReset);
  assert.equal(root.dataset.omarchyTheme, undefined);
});

test("background coalesces retries, ignores old ports, and closes failed clients",
  () => {
    const onConnect = event();
    const ports = [];
    const timers = new Map();
    let nextID = 0;
    let attempts = 0;
    let fail = false;
    vm.runInNewContext(fs.readFileSync(
      path.join(directory, "background.js"), "utf8"
    ), {
      chrome: { runtime: {
        onConnect,
        connectNative() {
          attempts++;
          if (fail) throw new Error("Host unavailable");
          const port = {
            onMessage: event(), onDisconnect: event(), closed: false,
            disconnect() { this.closed = true; this.onDisconnect.fire(); },
          };
          ports.push(port);
          return port;
        },
      } },
      setTimeout: (fn) => { timers.set(++nextID, fn); return nextID; },
      clearTimeout: (id) => timers.delete(id),
    });
    function client() {
      const client = {
        name: "omarchy-theme",
        sender: { url: "https://iop098321qwe.github.io/main_page/" },
        onDisconnect: event(), messages: [],
        postMessage(message) { this.messages.push(message); },
      };
      onConnect.fire(client);
      return client;
    }
    const first = client();
    ports[0].onDisconnect.fire();
    const second = client();
    assert.equal(attempts, 1, "New tabs must share pending retries");
    assert.equal(timers.size, 1);
    function retry() {
      const [id, fn] = [...timers][0];
      timers.delete(id);
      fn();
    }
    fail = true;
    retry();
    assert.equal(timers.size, 1, "Thrown connection errors must retry");
    fail = false;
    retry();
    assert.equal(attempts, 3);
    ports[1].onMessage.fire({ type: "palette" });
    ports[0].onMessage.fire({ type: "obsolete" });
    assert.equal(first.messages.at(-1).type, "palette");
    first.postMessage = second.postMessage = () => { throw new Error("Gone"); };
    ports[1].onMessage.fire({ type: "unavailable" });
    assert.equal(ports[1].closed, true);
    assert.equal(timers.size, 0);
    const third = client();
    ports[2].onDisconnect.fire();
    third.onDisconnect.fire();
    assert.equal(timers.size, 0, "Last tab must cancel pending retries");
  });
