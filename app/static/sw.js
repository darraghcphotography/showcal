// Minimal app-shell service worker - just enough to satisfy Chrome/Android's
// "installable" checklist (a registered SW with a fetch handler). Not full
// offline support: only the unchanging static assets are cached; every page
// request (HTML) always goes to the network so shows/results are never stale.
const CACHE_NAME = "shell-v1";
// Relative (no leading slash) so these resolve against this script's own
// URL - correct both at the site root locally and under a URL_PREFIX
// sub-path in production (e.g. /showcal/static/...), with no prefix-parsing
// needed here.
const SHELL_URLS = [
  "static/style.css",
  "static/favicon.svg",
  "static/icons/icon-192.png",
  "static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const isStaticAsset = event.request.method === "GET" && url.origin === self.location.origin
    && url.pathname.includes("/static/");

  if (!isStaticAsset) return; // let the browser handle everything else normally

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      });
    })
  );
});
