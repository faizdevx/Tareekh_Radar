// Case Clock service worker: makes the site open and work offline (court buildings often have no signal).
// App files: network first (always fresh when online), cache as fallback.
// Statistics JSON and fonts: cached copy first, refreshed in the background.
// Sign-in / database traffic (Firebase, Google APIs) is never cached.
const CACHE = "cc-v4";
const SHELL = ["./", "index.html", "css/style.css", "js/app.js", "js/i18n.js", "js/art.js", "js/logic.js", "js/help.js",
  "js/diary.js", "js/ai.js", "js/prep.js", "js/layer2.js", "js/voice.js", "js/ocr.js", "manifest.webmanifest", "assets/icon-192.png",
  "data/meta.json", "data/national.json", "data/purposes.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

const NEVER = /firebase|googleapis\.com\/(identitytoolkit|securetoken)|firestore\.googleapis|gstatic\.com\/firebasejs|chatgpt|claude\.ai/;

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || NEVER.test(req.url)) return;
  const url = new URL(req.url);
  const isData = url.origin === location.origin && url.pathname.includes("/data/");
  const isFont = /fonts\.(googleapis|gstatic)\.com/.test(url.host);
  const isOcr = /cdn\.jsdelivr\.net\/npm\/(tesseract|@tesseract)/.test(req.url);
  if (isData || isFont || isOcr) {
    // stale-while-revalidate
    e.respondWith(caches.open(CACHE).then(async (c) => {
      const hit = await c.match(req);
      const net = fetch(req).then((r) => { if (r.ok || r.type === "opaque") c.put(req, r.clone()); return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  if (url.origin !== location.origin) return;
  // network first for the app itself
  e.respondWith(fetch(req).then((r) => {
    if (r.ok) { const copy = r.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
    return r;
  }).catch(async () => (await caches.match(req)) || (req.mode === "navigate" ? caches.match("index.html") : Response.error())));
});
