# page_keeper.py: the game data kept on the device and fetched ahead of the game (exec'd by make_page.py).
# Rule: never load at the moment the game needs the data, preload ahead, in chunks. data-sw.js (the service worker)
# answers OpenMW's reads of mwdata/<path> from disc.json's 8 MiB chunks (GitHub) and keeps every chunk in Cache
# Storage. From the moment the page opens this block asks it for every chunk, three at a time, in the stream's order
# (the ESM, the title music and splash screens, the BSA, sounds, music, films: pack_data.py), holding back while the
# game itself waits for a read. Start waits for the engine files and for the worker to hold the page.
# Test switch (address only): ?nokeep (no background fetching), ?fresh (forget the kept chunks first).

swap("var saveLocked = false, tesFrame = null", r"""const keeper = { sw: null, chunks: 0, chunk: 0, kept: 0, downloaded: 0, waiting: 0, done: false };
let engineLoaded = false, swReady = false;
function tesMaybeReady() {
  if (engineLoaded && swReady && Module.tesReady) tesPreRun().then(() => Module.tesReady());
}
// The page's own preRun hooks (the cloud block's: it reads the stored package and asks the cloud, which may give a
// newer one) run before Start is offered, with the page's own run dependencies
let preRunDone = null;
function tesPreRun() {
  if (preRunDone) return preRunDone;
  preRunDone = new Promise((done) => {
    let deps = 0;
    const left = () => { if (deps <= 0) done(); };
    Module.addRunDependency = () => { deps++; };
    Module.removeRunDependency = () => { deps--; left(); };
    for (const hook of Module.preRun.splice(0)) { try { hook(); } catch (e) { console.warn('preRun', e); } }
    left();
  });
  return preRunDone;
}
function swAsk(message) {
  return new Promise((ok) => {
    const sw = navigator.serviceWorker.controller;
    if (!sw) return ok({});
    const ch = new MessageChannel();
    ch.port1.onmessage = (e) => ok(e.data || {});
    sw.postMessage(message, [ch.port2]);
  });
}
async function startKeeper() {
  const where = await fetch('disc/disc.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  if (!where || !where.files || !('serviceWorker' in navigator)) {
    showHelp('noDiscHelp', { url: new URL('disc/disc.json', location.href).href });
    return;
  }
  Module.discSize = where.size;
  info.disc = () => t('discInfo', { gb: num(where.size / 1073741824, 2) });
  await navigator.serviceWorker.register(withBuild('data-sw.js'));
  if (!navigator.serviceWorker.controller) await new Promise((ok) => navigator.serviceWorker.addEventListener('controllerchange', ok, { once: true }));
  if (params.has('fresh')) await swAsk({ forget: 1 });
  swReady = true;
  tesMaybeReady();
  const count = Math.ceil(where.size / where.chunk);
  keeper.chunks = count;
  setInterval(async () => { const s = await swAsk({ waiting: 1 }); keeper.downloaded = s.downloaded || 0; keeper.waiting = s.waiting || 0; }, 500);
  if (params.has('nokeep')) return;
  const queue = [...Array(count).keys()];
  let running = 0, had = 0;
  const next = () => {
    while (running < 3 && queue.length) {
      const k = queue.shift();
      running++;
      swAsk({ prefetch: k }).then((r) => {
        running--;
        if (r.ok) { keeper.kept++; if (r.had) had++; }
        else if (!r.full) setTimeout(() => queue.push(k), 3000);  // a failed download goes to the end of the list
        if (keeper.kept === count && !keeper.done) { keeper.done = true; console.log('[disc] every chunk kept on this device (' + had + ' from an earlier visit)'); }
        next();
      });
    }
  };
  next();
}
const keeperCalls = {  // (on the Module: tesAttach)
  // downloaded this visit (the start window's figures), and whether the game waits for a read (the loading notice)
  _ps2web_disc_fetched: () => keeper.downloaded,
  _ps2web_disc_loading: () => (keeper.waiting ? 1 : 0),
};
var saveLocked = false, tesFrame = null""")
swap("uiReady = true;\n", "uiReady = true;\ntesAttach();\nstartKeeper();\n")

# the start window closes as soon as the game has shown BOOT_PICTURES pictures, whatever its speed
swap("      if (fast >= 4 || steady >= 12 || performance.now() - begun > 60000) {\n",
     "      if (count >= BOOT_PICTURES || performance.now() - begun > 90000) {\n")
