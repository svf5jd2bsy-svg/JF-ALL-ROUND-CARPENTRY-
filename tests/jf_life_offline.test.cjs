// Run with node --test tests/jf_life_offline.test.cjs
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");
const code = fs.readFileSync(path.join(__dirname, "../App/sw.js"), "utf8");
const root = "https://local.example/jf/App/";
const index = "https://local.example/jf/Organisation/latest/File-Library-Manifest.json";
const json = (n, headers = {}) => Response.json({ files: [n] }, { headers });
function harness() {
  const map = new Map();
  const deleted = [];
  const hooks = {};
  const scope = { registration: { scope: root }, addEventListener: (k, f) => hooks[k] = f,
    skipWaiting: async () => {}, clients: { claim: async () => {} } };
  let net = () => { throw new Error("offline"); };
  const cache = {
    addAll: async (urls) => urls.forEach((u) => map.set(u, new Response("shell"))),
    match: async (request) => map.get(request.url)?.clone(),
    put: async (request, response) => { map.set(request.url, response); },
    delete: async (request) => map.delete(request.url),
  };
  const caches = { open: async () => cache, keys: async () => ["jf-life-v2",
    "jf-life-library-v2", "jf-life-library-v3", "unrelated-app"],
    delete: async (key) => deleted.push(key) };
  vm.runInNewContext(code, { self: scope, URL, Response, caches, fetch: (...a) => net(...a) });
  const fire = (event) => { let pending; hooks[event]({ waitUntil: (p) => pending = p }); return pending; };
  const request = (url, method = "GET") => {
    let answer; hooks.fetch({ request: new Request(url, { method }),
      respondWith: (r) => answer = r }); return answer;
  };
  return { set: (fn) => net = fn, fire, request, deleted };
}
test("latest index survives offline after an online read", async () => {
  const h = harness();
  h.set(() => json("first")); assert.deepEqual(await (await h.request(index)).json(), { files: ["first"] });
  h.set(() => json("latest")); await h.request(index);
  h.set(() => { throw new Error("offline"); });
  assert.deepEqual(await (await h.request(index)).json(), { files: ["latest"] });
});
test("denial and explicit no-store evict prior index", async () => {
  for (const reply of [() => new Response("", { status: 403 }),
    () => json("private", { "cache-control": "private, no-store" })]) {
    const h = harness(); h.set(() => json("old")); await h.request(index);
    h.set(reply); await h.request(index);
    h.set(() => { throw new Error("offline"); });
    assert.equal((await h.request(index)).type, "error");
  }
});
test("does not intercept documents, other origins, queries or writes", () => {
  const h = harness();
  for (const [url, method] of [[root + "receipt.pdf"], ["https://other.example/a.json"],
    [index + "?token=x"], [index, "POST"]]) assert.equal(h.request(url, method), undefined);
});
test("shell installs and works offline; activation preserves unrelated caches", async () => {
  const h = harness(); await h.fire("install"); await h.fire("activate");
  assert.equal(await (await h.request(root + "Library-Index.html")).text(), "shell");
  assert.deepEqual(h.deleted, ["jf-life-v2", "jf-life-library-v2"]);
});
