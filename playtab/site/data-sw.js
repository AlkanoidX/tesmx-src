// data-sw.js: the page's service worker for Morrowind (OpenMW engine). OpenMW's StreamFS reads each game file with
// Range requests on mwdata/<path> and lists them from mwdata-manifest.json. The files are on GitHub laid end to end
// in 8 MiB chunks (cNNNN.bin, chunk k = bytes k * 8 MiB of the stream; disc/disc.json gives each file's offset and
// size, and the chunks' base). This worker answers both from those chunks and keeps every chunk it downloads in
// Cache Storage (raw.githubusercontent.com's own caching is 5 minutes). The page asks it to fetch chunks ahead of the
// game ({ prefetch: k }), so the game finds them on the device (rule: never load at the moment of need). A game read
// whose chunk is not kept fetches only its own bytes, and background downloads are stopped while the game waits.
// Model: Dead Space 2's disc-sw.js (captures/ds2/deliver/site).
const STORE = 'tesm-data-v1';
const flying = new Map();     // chunk url -> Promise<ArrayBuffer>
const background = new Map(); // chunk url -> AbortController of a background download
const recent = new Map();     // chunk url -> ArrayBuffer, the last few used
const RECENT_MAX = 12;
let lastGameRead = 0, info = null, full = false, waiting = 0, downloaded = 0;
const order = [];             // chunk numbers in the order the game first asked for them (tests)

function disc() {
  if (!info) {
    info = fetch(new URL('disc/disc.json', self.registration.scope).href, { cache: 'no-cache' }).then((r) => r.json()).then((j) => {
      const files = new Map();
      for (const f of j.files) files.set(f.p.toLowerCase(), f);
      return { base: new URL(j.base || 'disc/', self.registration.scope).href, chunk: j.chunk, size: j.size, list: j.files, files };
    });
    info.catch(() => { info = null; });
  }
  return info;
}

const chunkUrl = (d, k) => d.base + 'c' + String(k).padStart(4, '0') + '.bin';

function remember(url, buf) {
  recent.delete(url);
  recent.set(url, buf);
  while (recent.size > RECENT_MAX) recent.delete(recent.keys().next().value);
}

async function quiet() {
  while (waiting > 0 || performance.now() - lastGameRead < 400) await new Promise((r) => setTimeout(r, 100));
}

async function chunkIfKept(url) {
  const hit = recent.get(url);
  if (hit) { remember(url, hit); return hit; }
  const job = flying.get(url);
  if (job) { try { const b = await job; remember(url, b); return b; } catch (e) { return null; } }
  const kept = await (await caches.open(STORE)).match(url);
  if (!kept) return null;
  const buf = await kept.arrayBuffer();
  remember(url, buf);
  return buf;
}

async function gameRange(url, from, to) {
  waiting++;
  try {
    for (const [u, c] of background) if (u !== url) c.abort();
    for (let attempt = 0; ; attempt++) {
      lastGameRead = performance.now();
      try {
        const r = await fetch(url, { mode: 'cors', credentials: 'omit', headers: { Range: 'bytes=' + from + '-' + (to - 1) } });
        if (r.status !== 206 && r.status !== 200) throw new Error('HTTP ' + r.status);
        let buf = new Uint8Array(await r.arrayBuffer());
        downloaded += buf.length;
        if (r.status === 200) buf = buf.subarray(from, to);
        if (buf.length !== to - from) throw new Error('short read');
        return buf;
      } catch (e) {
        if (attempt >= 4) throw e;
        await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
      }
    }
  } finally {
    waiting--;
    lastGameRead = performance.now();
  }
}

function chunkBuf(url, signal) {
  let job = flying.get(url);
  if (!job) {
    job = (async () => {
      const cache = await caches.open(STORE);
      const kept = await cache.match(url);
      if (kept) return kept.arrayBuffer();
      for (let attempt = 0; ; attempt++) {
        try {
          const r = await fetch(url, { mode: 'cors', credentials: 'omit', signal });
          if (!r.ok) throw new Error('HTTP ' + r.status);
          const buf = await r.arrayBuffer();
          downloaded += buf.byteLength;
          if (!full) await cache.put(url, new Response(buf.slice(0))).catch((e) => { if (e && e.name === 'QuotaExceededError') full = true; });
          return buf;
        } catch (e) {
          if (attempt >= 4 || (signal && signal.aborted)) throw e;
          await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
        }
      }
    })();
    flying.set(url, job);
    job.then(() => flying.delete(url), () => flying.delete(url));
  }
  return job;
}

async function answer(request, path) {
  const d = await disc();
  const f = d.files.get(path.toLowerCase());
  if (!f) return new Response('not found', { status: 404 });
  const m = /bytes=(\d+)-(\d*)/.exec(request.headers.get('range') || '');
  let start = 0, end = f.s - 1;
  if (m) { start = Number(m[1]); if (m[2]) end = Math.min(end, Number(m[2])); }
  if (f.s === 0) return new Response(new Uint8Array(0), { status: 200, headers: { 'Content-Length': '0' } });
  if (start > end || start >= f.s) return new Response('', { status: 416, headers: { 'Content-Range': 'bytes */' + f.s } });
  const out = new Uint8Array(end - start + 1);
  const a = f.o + start, b = f.o + end + 1;  // [a, b) in the stream
  for (let k = Math.floor(a / d.chunk); k <= Math.floor((b - 1) / d.chunk); k++) {
    if (!order.includes(k)) order.push(k);
    const url = chunkUrl(d, k), base = k * d.chunk;
    const from = Math.max(a, base), to = Math.min(b, base + d.chunk);
    const kept = await chunkIfKept(url);
    if (kept) out.set(new Uint8Array(kept).subarray(from - base, to - base), from - a);
    else out.set(await gameRange(url, from - base, to - base), from - a);
  }
  return new Response(out, { status: m ? 206 : 200, headers: {
    'Content-Type': 'application/octet-stream', 'Content-Length': String(out.length), 'Accept-Ranges': 'bytes',
    'Content-Range': 'bytes ' + start + '-' + end + '/' + f.s } });
}

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET' && e.request.method !== 'HEAD') return;
  const scope = self.registration.scope, url = e.request.url.replace(/[?#].*$/, '');
  if (url === scope + 'mwdata-manifest.json') {
    e.respondWith(disc().then((d) => new Response(JSON.stringify(d.list.map((f) => ({ p: f.p, s: f.s }))),
      { headers: { 'Content-Type': 'application/json' } })));
  } else if (url.startsWith(scope + 'mwdata/')) {
    const path = decodeURIComponent(url.slice((scope + 'mwdata/').length));
    e.respondWith(answer(e.request, path).catch((err) => new Response(String(err), { status: 503 })));
  }
});
self.addEventListener('message', (e) => {
  const port = e.ports[0], m = e.data || {};
  const reply = (o) => port && port.postMessage(Object.assign({ waiting, downloaded, full }, o));
  if (typeof m.prefetch === 'number') {
    e.waitUntil(disc().then(async (d) => {
      const url = chunkUrl(d, m.prefetch);
      if (await (await caches.open(STORE)).match(url)) return reply({ ok: true, had: true });
      if (full) return reply({ ok: false });
      await quiet();
      const control = new AbortController();
      background.set(url, control);
      try { await chunkBuf(url, control.signal); reply({ ok: true }); }
      catch (err) { reply({ ok: false, aborted: control.signal.aborted }); }
      finally { if (background.get(url) === control) background.delete(url); }
    }).catch(() => reply({ ok: false })));
  } else if (m.info) {
    e.waitUntil(disc().then((d) => reply({ chunks: Math.ceil(d.size / d.chunk), chunk: d.chunk })));
  } else if (m.order) {
    reply({ order });
  } else if (m.waiting) {
    reply({});
  } else if (m.forget) {
    e.waitUntil(caches.delete(STORE).then(() => { recent.clear(); full = false; reply({ ok: true }); }));
  }
});
