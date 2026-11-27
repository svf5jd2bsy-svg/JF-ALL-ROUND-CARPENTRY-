// JF LIFE Library: cache only the shell and the app's generated index.
const CACHE = "jf-life-library-v3";
const OLD_CACHES = new Set(["jf-life-v2"]);
const ROOT = new URL(self.registration.scope);
const SHELL = ["Library-Index.html", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/apple-touch-icon.png"];
const SHELL_URLS = new Set(SHELL.map((name) => new URL(name, ROOT).href));
const INDEX_URLS = new Set([
  new URL("../Organisation/latest/File-Library-Manifest.json", ROOT).href,
  new URL("Organisation/latest/File-Library-Manifest.json", ROOT).href,
]);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE)
    .then((cache) => cache.addAll([...SHELL_URLS]))
    .then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => OLD_CACHES.has(key)
      || (key.startsWith("jf-life-library-") && key !== CACHE))
      .map((key) => caches.delete(key))
  )).then(() => self.clients.claim()));
});

async function networkFirstIndex(request) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    // An explicit server refusal or removal must not resurrect an old index.
    if ([401, 403, 404, 410].includes(response.status)) {
      await cache.delete(request);
      return response;
    }
    if (response.ok && !response.redirected
      && (response.headers.get("content-type") || "").includes("application/json")) {
      if (/\bno-store\b/i.test(response.headers.get("cache-control") || "")) {
        await cache.delete(request);
      } else {
        try { await cache.put(request, response.clone()); } catch (_) {
          // A full cache must not break an online response.
        }
      }
    }
    return response;
  } catch (_) {
    return (await cache.match(request)) || Response.error();
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== ROOT.origin || url.search || url.hash) return;
  if (INDEX_URLS.has(url.href)) {
    event.respondWith(networkFirstIndex(request));
  } else if (SHELL_URLS.has(url.href)) {
    event.respondWith(caches.open(CACHE)
      .then(async (cache) => (await cache.match(request)) || fetch(request)));
  }
  // Never cache other pages, documents, or third-party requests.
});
