# page_engine.py: the part of make_page.py that joins the PlayTab page to OpenMW (exec'd by make_page.py, which has
# swap/cut and c). See make_page.py's head.
#
# OpenMW runs in its own page (engine.html = openmw-web's play/index.html, make_engine.py) in a same-origin frame
# laid over the stage. Before that page runs anything it calls ptEngineHook(window) here, which gives it:
#  - the engine files this page downloaded and keeps (engineFile: openmw.wasm, openmw.data, gzipped on the host);
#  - one standard gamepad, player 1 of this page (every real pad, the keyboard's page keys and the touch pad merged:
#    single-player game); the browser's real pads are hidden from it;
#  - its AudioContext wrapped so the game's sound goes through this page's volume and level meter;
#  - the resolution (openmw-web's pixel budget window.__maxPixels: 720p, 1080p, 1440p);
#  - no mouse capture (rule): requestPointerLock does nothing.
# The game data comes through data-sw.js (the service worker, page_keeper.py). The saves are OpenMW's IDBFS
# database "/userdata" (same origin): this page reads and writes it directly for the saves package and the cloud.

# no engine canvas on this page: the frame takes the stage
swap("""  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
    if (Module.running && Module._ps2web_resize) Module._ps2web_resize(width, height);
  }""", """  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }""")
swap("  canvas { width: 100%; height: 100%; display: block; background: #000; outline: none; touch-action: none; }\n",
     "  canvas { width: 100%; height: 100%; display: block; background: #000; outline: none; touch-action: none; }\n"
     "  #stage { position: relative; } #engine-frame { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; display: block; background: #000; }\n"
     "  body.running #canvas { visibility: hidden; }\n"
     "  body.touch #engine-frame { pointer-events: none; }  /* on a touch screen the page's controls take every touch */\n")

# remote play: copies of the frame's canvas for the stream, drawn at the stream's rate
swap("""    const frame = new VideoFrame(pixels.slice(), { format: 'RGBA', codedWidth: width, codedHeight: height, timestamp: Math.round(performance.now() * 1000) });
""", "")
swap("Module.onStreamFrame = (pixels, width, height) => {\n    if (busy) return;", "Module.onStreamFrame = (frame) => {\n    if (busy) return frame.close();")
swap("  Module._ps2web_stream(1);\n", "  tesStream(true);\n")

# saves: the memory card rows carry the saves package (a stored ZIP of OpenMW's saves and settings.cfg)
cut("function storeCard(then, now) {", "// The player can be closed at any time", """function storeCard(then, now) {
  if (Module.xboxSave) Module.xboxSave.flush();
  if (then) setTimeout(then, 800);
}
""")
cut("function exportCard() {", "const importInput = ", """function exportCard() {
  Module.xboxSave.load().then((rec) => (rec && rec.zip ? download('morrowind-xbox-saves.zip', rec.zip) : note(t('cardEmpty'))), () => note(t('cardEmpty')));
}
""")
cut("  if (file.size !== CARD_BYTES) return note(t('cardSize'));", "const statsEl = ", """  if (file.size > 60000000) return note(t('cardSize'));
  const data = new Uint8Array(await file.arrayBuffer());
  if (data[0] !== 0x50 || data[1] !== 0x4B || !tesUnzip(data)) return note(t('cardFormat'));
  // Picking the file is the confirmation: no confirm() box, it breaks pad play.
  saveLocked = true;  // the running game's saves no longer replace it
  try {
    await Module.xboxSave.put(data, Date.now());
  } catch (e) {
    saveLocked = false;
    return note(t('importFail', { e: e.message }));
  }
  note(t('cardDone'));
  setTimeout(() => location.reload(), 600);
});

""")
swap('accept=".ps2"', 'accept=".zip"')

# sound: the game's own (Emscripten's OpenAL on a WebAudio context in the frame); startAudio only resumes it
cut("async function startAudio() {", "const keys = new Set();", """async function startAudio() {
  if (audio && audio.state !== 'running') audio.resume().catch(() => {});
}

""")

# the keyboard plays through the game's own controls (OpenMW: WASD, E, Space...): the page does not also turn keys
# into player 1's pad; M still opens the page's menu (the frame passes it on, ptEngineHook)
swap("    for (const k of keys) if (k in keyMap) buttons |= 1 << keyMap[k];\n", "")
swap("    if (keys.has('KeyJ')) lx = 0;\n    if (keys.has('KeyL')) lx = 255;\n    if (keys.has('KeyI')) ly = 0;\n    if (keys.has('KeyK')) ly = 255;\n", "")
swap("  if (layer || !(e.code in keyMap || stickKeys.has(e.code))) return;\n", "  if (layer || !(e.code in keyMap || stickKeys.has(e.code))) return;\n  setInput('key');\n  return;  // (the game reads the keys itself)\n")

swap("var Module = {\n", r"""// ---------- OpenMW under the page's PS2-shaped calls
var saveLocked = false, tesFrame = null, tesWin = null, tesFrames = 0, tesPaused = false;
// one standard gamepad for the game: the page's four players merged (single player)
const tesPad = { id: 'PlayTab pad (STANDARD GAMEPAD Vendor: 0000 Product: 0000)', index: 0, connected: true, mapping: 'standard', timestamp: 0,
  axes: [0, 0, 0, 0], buttons: Array.from({ length: 17 }, () => ({ pressed: false, touched: false, value: 0 })), vibrationActuator: null };
const tesPorts = [0, 1, 2, 3].map(() => ({ buttons: 0, pressure: new Array(16).fill(255), sticks: [128, 128, 128, 128] }));
// PS2 bit -> standard gamepad button: cross A, circle B, square X, triangle Y, L1/R1 white/black (LB/RB), L2/R2
// triggers, Select Back, Start, L3, R3, the d-pad
const STD_BUTTON = { 14: 0, 13: 1, 15: 2, 12: 3, 10: 4, 11: 5, 8: 6, 9: 7, 0: 8, 3: 9, 1: 10, 2: 11, 4: 12, 6: 13, 7: 14, 5: 15 };
function tesWritePad() {
  let bits = 0;
  const value = new Array(17).fill(0), axes = [0, 0, 0, 0];
  for (const p of tesPorts) {
    bits |= p.buttons;
    for (let a = 0; a < 4; a++) { const v = p.sticks[a] === 128 ? 0 : (p.sticks[a] - 128) / 127.5; if (Math.abs(v) > Math.abs(axes[a])) axes[a] = Math.max(-1, Math.min(1, v)); }
    for (const bit of [8, 9]) if (p.buttons & (1 << bit)) value[STD_BUTTON[bit]] = Math.max(value[STD_BUTTON[bit]], (p.pressure[bit] || 255) / 255);
  }
  for (const bit in STD_BUTTON) {
    const i = STD_BUTTON[bit], on = (bits & (1 << bit)) !== 0;
    const v = on ? (value[i] || 1) : 0;
    tesPad.buttons[i] = { pressed: on, touched: on, value: v };
  }
  tesPad.axes = axes;
  tesPad.timestamp = performance.now();
}
// The game's AudioContext (OpenAL's): its destination is the page's chain, gain (volume) and a meter, then the speakers.
function tesWrapAudio(win) {
  const FrameAudioContext = win.AudioContext;
  if (!FrameAudioContext) return;
  win.AudioContext = win.webkitAudioContext = class extends FrameAudioContext {
    constructor(options) {
      super(options);
      if (!audio) {
        audio = this;
        node = super.createGain();          // what the game connects to (the stream's sound comes from here too)
        gain = super.createGain();          // the volume row
        const meter = super.createAnalyser();
        meter.fftSize = 2048;
        node.connect(gain).connect(super.destination);
        gain.connect(meter);
        applyVolume();
        // level once a second (?statslog): rms and peak of what reaches the speakers, sampled every 50 ms
        const samples = new Float32Array(meter.fftSize);
        let sum = 0, count = 0, peak = 0, played = 0;
        setInterval(() => {
          meter.getFloatTimeDomainData(samples);
          for (const v of samples) { sum += v * v; count++; peak = Math.max(peak, Math.abs(v)); }
        }, 50);
        setInterval(() => {
          played += 375;
          Module.audioStats = { played, starved: 0 };
          Module.audioLevel = { rms: count ? Math.sqrt(sum / count) : 0, peak, state: this.state };
          if (statsLog) console.log('[audio] rms ' + Module.audioLevel.rms.toFixed(4) + ' peak ' + peak.toFixed(3) + ' ' + this.state);
          sum = count = peak = 0;
        }, 1000);
      }
    }
    get destination() { return this === audio ? node : super.destination; }
  };
}
// The resolution: openmw-web renders the canvas at the window's pixels, capped by window.__maxPixels
const TES_PIXELS = { 1: 1280 * 720, 2: 1920 * 1080, 3: 2560 * 1440 };
const tesEngine = {};  // name -> Promise<Response> (engineFile), started at page open
window.ptEngineHook = (win) => {
  tesWin = win;
  win.__maxPixels = TES_PIXELS[Number(started.scale || scale)] || TES_PIXELS[1];
  try { win.HTMLCanvasElement.prototype.requestPointerLock = function () { return Promise.resolve(); }; } catch (e) {}  // no mouse capture
  win.navigator.getGamepads = () => [tesPad, null, null, null];
  tesWrapAudio(win);
  const pageFetch = win.fetch.bind(win);
  win.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    const engine = /(?:^|\/)openmw\.(wasm|data)(?:\?|$)/.exec(url);
    if (engine && tesEngine[engine[1]]) return tesEngine[engine[1]].then((r) => r.clone());
    if (/\/clientlog(?:\?|$)/.test(url)) return Promise.resolve(new Response(null, { status: 204 }));  // openmw-web's telemetry: not here
    return pageFetch(input, init);
  };
  // the page's menu key from inside the frame (M; Escape is the game's own menu)
  win.addEventListener('keydown', (e) => {
    if (e.code === 'KeyM' && !e.repeat && !layer && !(e.target && /INPUT|TEXTAREA/.test(e.target.tagName))) { e.preventDefault(); e.stopImmediatePropagation(); setInput('key'); openMenu(); }
  }, true);
  win.addEventListener('pointerdown', () => setInput('mouse'), true);
  win.addEventListener('message', () => {});
};
// the engine's frames: openmw-web calls Module._omw_pump_frame once a frame; wrapped so the page counts them and
// holds the game while its menu is open (a real pause: no frame runs)
function tesWatchPump() {
  const M = tesWin && tesWin.Module;
  if (!M || !M._omw_pump_frame || M._omw_pump_frame.ptWrapped) return;
  const pump = M._omw_pump_frame;
  M._omw_pump_frame = function () {
    if (tesPaused) return 0;
    const r = pump.apply(this, arguments);
    if (M.__omwRunning !== undefined) tesFrames++;
    return r;
  };
  M._omw_pump_frame.ptWrapped = true;
}
function tesAttach() {  // after the page made its Module
// the stats line reads the engine's memory size
Object.defineProperty(Module, 'HEAPU8', { configurable: true, get: () => (tesWin && tesWin.Module && tesWin.Module.HEAPU8) || new Uint8Array(0) });
Object.assign(Module, {
  _ps2web_pad_ports: () => 4,
  _ps2web_pad_connected: () => {},
  _ps2web_pad: (port, buttons, lx, ly, rx, ry) => {
    if (port > 3) return;
    tesPorts[port].buttons = buttons;
    tesPorts[port].sticks = [lx, ly, rx, ry];
    tesWritePad();
  },
  _ps2web_pressure: (port, a, b, c, d) => {
    if (port > 3) return;
    [a, b, c, d].forEach((word, i) => { for (let k = 0; k < 4; k++) tesPorts[port].pressure[i * 4 + k] = (word >>> (8 * k)) & 255; });
    tesWritePad();
  },
  _ps2web_rumble: () => 0,
  _ps2web_frames: () => tesFrames,
  _ps2web_pause: (on) => {
    tesPaused = !!on;
    if (audio) (on ? audio.suspend() : audio.resume()).catch(() => {});
    if (!on && tesFrame) tesFrame.focus();
  },
  _ps2web_gpu_ms: () => 0, _ps2web_idle_ms: () => 0, _ps2web_vu_interpreted: () => 0, _ps2web_audio_queued_ms: () => 0,
  _ps2web_quick_state: () => 0,
});
Module.xboxSave = {
  key: SAVE_KEY,
  load: () => saveDb('readonly', (s) => s.get(SAVE_KEY)),  // { zip, t } or undefined
  put: (zip, t) => saveDb('readwrite', (s) => s.put({ zip, t }, SAVE_KEY)),
  flush: () => tesPack(),
};
Object.assign(Module, keeperCalls);
}
// a stored ZIP (no compression, sorted names, no dates: equal saves give equal bytes) and its reader
const crcTable = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(d) { let c = 0xFFFFFFFF; for (let i = 0; i < d.length; i++) c = crcTable[(c ^ d[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
function tesZip(entries) {
  entries.sort((a, b) => (a.name < b.name ? -1 : 1));
  const enc = new TextEncoder(), parts = [], central = [];
  let offset = 0;
  for (const e of entries) {
    const name = enc.encode(e.name), crc = crc32(e.data), head = new DataView(new ArrayBuffer(30));
    head.setUint32(0, 0x04034b50, true); head.setUint16(4, 20, true); head.setUint32(14, crc, true);
    head.setUint32(18, e.data.length, true); head.setUint32(22, e.data.length, true); head.setUint16(26, name.length, true);
    parts.push(new Uint8Array(head.buffer), name, e.data);
    const cd = new DataView(new ArrayBuffer(46));
    cd.setUint32(0, 0x02014b50, true); cd.setUint16(4, 20, true); cd.setUint16(6, 20, true); cd.setUint32(16, crc, true);
    cd.setUint32(20, e.data.length, true); cd.setUint32(24, e.data.length, true); cd.setUint16(28, name.length, true); cd.setUint32(42, offset, true);
    central.push(new Uint8Array(cd.buffer), name);
    offset += 30 + name.length + e.data.length;
  }
  const size = central.reduce((n, p) => n + p.length, 0), end = new DataView(new ArrayBuffer(22));
  end.setUint32(0, 0x06054b50, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true);
  end.setUint32(12, size, true); end.setUint32(16, offset, true);
  const out = new Uint8Array(offset + size + 22);
  let at = 0;
  for (const p of [...parts, ...central, new Uint8Array(end.buffer)]) { out.set(p, at); at += p.length; }
  return out;
}
// what a package may hold: OpenMW's saves and its settings (paths under /userdata); every name checked (a package is untrusted input)
const TES_SAVED = /^(data-home\/openmw\/saves\/[^\/]+\/[^\/]+|config\/openmw\/settings\.cfg)$/;
function tesUnzip(zip) {  // [{name, data}] of a stored ZIP, or null
  try {
    const v = new DataView(zip.buffer, zip.byteOffset, zip.byteLength), out = [], dec = new TextDecoder();
    let at = 0;
    while (at + 30 <= zip.length && v.getUint32(at, true) === 0x04034b50) {
      const method = v.getUint16(at + 8, true), size = v.getUint32(at + 18, true), n = v.getUint16(at + 26, true), extra = v.getUint16(at + 28, true);
      const name = dec.decode(zip.subarray(at + 30, at + 30 + n)), start = at + 30 + n + extra;
      if (method !== 0 || start + size > zip.length) return null;
      if (!TES_SAVED.test(name) || name.includes('..')) return null;
      out.push({ name, data: zip.slice(start, start + size) });
      at = start + size;
    }
    return out;
  } catch (e) { return null; }
}
// OpenMW's IDBFS database (Emscripten: database "/userdata", store FILE_DATA, version 21, an index on timestamp;
// key = the full path, value = { timestamp: Date, mode, contents } for a file, { timestamp, mode } for a folder)
function userDb(mode, fn) {
  return new Promise((ok, no) => {
    const r = indexedDB.open('/userdata', 21);
    r.onupgradeneeded = () => {
      const db = r.result;
      const store = db.objectStoreNames.contains('FILE_DATA') ? r.transaction.objectStore('FILE_DATA') : db.createObjectStore('FILE_DATA');
      if (!store.indexNames.contains('timestamp')) store.createIndex('timestamp', 'timestamp', { unique: false });
    };
    r.onerror = () => no(r.error);
    r.onsuccess = () => {
      const tx = r.result.transaction('FILE_DATA', mode), out = fn(tx.objectStore('FILE_DATA'));
      tx.oncomplete = () => { r.result.close(); ok(out && 'result' in out ? out.result : out); };
      tx.onerror = tx.onabort = () => { r.result.close(); no(tx.error); };
    };
  });
}
async function tesCollect() {  // [{name, data, t}] of the saves and settings in the browser's storage
  const entries = [];
  await userDb('readonly', (store) => {
    const cursor = store.openCursor();
    cursor.onsuccess = () => {
      const c = cursor.result;
      if (!c) return;
      const name = String(c.key).replace(/^\/userdata\//, '');
      if (TES_SAVED.test(name) && c.value && c.value.contents) entries.push({ name, data: new Uint8Array(c.value.contents), t: +c.value.timestamp || 0 });
      c.continue();
    };
  });
  return entries;
}
async function tesSpread(entries) {  // a package back into the browser's storage before the game starts
  const DIR = 16877, FILE = 33188, when = new Date();
  await userDb('readwrite', (store) => {
    const old = store.openCursor();
    old.onsuccess = () => {
      const c = old.result;
      if (!c) {
        const dirs = new Set(['/userdata', '/userdata/config', '/userdata/config/openmw', '/userdata/data-home', '/userdata/data-home/openmw', '/userdata/data-home/openmw/saves']);
        for (const e of entries) { const parts = ('/userdata/' + e.name).split('/'); for (let i = 3; i < parts.length; i++) dirs.add(parts.slice(0, i).join('/')); }
        for (const d of dirs) store.put({ timestamp: when, mode: DIR }, d);
        for (const e of entries) store.put({ timestamp: when, mode: FILE, contents: e.data }, '/userdata/' + e.name);
        return;
      }
      const name = String(c.key).replace(/^\/userdata\//, '');
      if (/^data-home\/openmw\/saves\//.test(name) || name === 'config/openmw/settings.cfg') c.delete();
      c.continue();
    };
  });
}
function saveDb(mode, fn) {
  return new Promise((ok, no) => {
    const r = indexedDB.open('xbox-saves', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('saves');
    r.onerror = () => no(r.error);
    r.onsuccess = () => {
      const tx = r.result.transaction('saves', mode), rq = fn(tx.objectStore('saves'));
      tx.oncomplete = () => { r.result.close(); ok(rq.result); };
      tx.onerror = tx.onabort = () => { r.result.close(); no(tx.error); };
    };
  });
}
const SAVE_KEY = location.pathname.replace(/[^\/]*$/, '');  // one saves package per page folder
let packing = null, packAgain = false, packSign = '';
async function tesPack() {  // the saves as they are in the browser's storage, to the package store (and the cloud)
  if (packing) { packAgain = true; return packing; }
  packing = (async () => {
    try {
      const entries = await tesCollect();
      const sign = entries.map((e) => e.name + ':' + e.data.length + ':' + e.t).sort().join('|');
      if (sign === packSign) return;
      const zip = tesZip(entries.map((e) => ({ name: e.name, data: e.data }))), old = await Module.xboxSave.load();
      if (saveLocked || Module.noCard) return;
      packSign = sign;
      if (old && old.zip && old.zip.length === zip.length && old.zip.every((b, i) => b === zip[i])) return;
      const rec = { zip, t: Date.now() };
      await Module.xboxSave.put(rec.zip, rec.t);
      Module.saveStored = rec;
      if (Module.xboxSaved) Module.xboxSaved(rec);
    } catch (e) {
      console.warn('saves: not stored', e);
    }
  })();
  await packing;
  packing = null;
  if (packAgain) { packAgain = false; return tesPack(); }
}
// before the game starts: the stored package (this device's, or one the cloud block took) is the saves the game finds,
// unless the browser's storage already holds the same saves, or newer ones (a page closed before its last package)
async function xboxRestoreSaves() {
  if (Module.noCard) return;
  try {
    const rec = await Module.xboxSave.load();
    const entries = rec && rec.zip && tesUnzip(rec.zip);
    if (!entries) return;
    const here = await tesCollect();
    const zip = tesZip(here.map((e) => ({ name: e.name, data: e.data })));
    if (zip.length === rec.zip.length && zip.every((b, i) => b === rec.zip[i])) return;
    const newest = here.reduce((n, e) => Math.max(n, e.t), 0);
    if (here.length && rec.t && newest > rec.t) {
      console.log('saves: the browser storage is newer than the stored package, kept');
      return;
    }
    await tesSpread(entries);
    Module.saveGiven = rec.zip.length;
    console.log('saves: ' + entries.length + ' files restored from the page (' + rec.zip.length + ' bytes)');
  } catch (e) {
    console.warn('saves: browser storage is not available', e);
  }
}
// after the start: OpenMW writes its saves to the database after each save (IDBFS sync); the page looks every 5 s
// and packs what changed, at once when the page is hidden
function tesWatchSaves() {
  setInterval(() => { if (Module.running && !tesPaused) tesPack(); }, 5000);
  document.addEventListener('visibilitychange', () => { if (document.hidden && Module.running) tesPack(); });
}
// remote play: a copy of the frame's canvas for each picture of the stream
function tesStream(on) {
  if (!on) return;
  let last = 0;
  const grab = (now) => {
    requestAnimationFrame(grab);
    const c = tesWin && tesWin.document.getElementById('canvas');
    if (!c || !Module.onStreamFrame || now - last < 1000 / 30) return;
    last = now;
    try { Module.onStreamFrame(new VideoFrame(c, { timestamp: Math.round(now * 1000) })); } catch (e) {}
  };
  requestAnimationFrame(grab);
}
// the PS2 engine called Module.onFrame from its own loop; here the page's frames do
function xboxFrameLoop() {
  requestAnimationFrame(xboxFrameLoop);
  tesWatchPump();
  if (Module.running) Module.onFrame();
}
// openmw-web's own address options that a test may pass through (never in the delivered page's address)
const TES_PASS = ['hud', 'debug', 'skipintro', 'novid', 'perfstats'];
async function tesStart() {
  await xboxRestoreSaves();
  const q = new URLSearchParams({ src: 'hosted' });
  for (const k of TES_PASS) if (params.has(k)) q.set(k, params.get(k));
  tesFrame = document.createElement('iframe');
  tesFrame.id = 'engine-frame';
  tesFrame.allow = 'autoplay; fullscreen; gamepad';
  tesFrame.src = 'engine.html?' + q.toString().replace(/=(&|$)/g, '$1');
  document.getElementById('stage').appendChild(tesFrame);
  document.body.classList.add('running');
  tesFrame.addEventListener('load', () => tesFrame.focus());
  console.log('[tesm] start, ' + (TES_PIXELS[Number(started.scale || scale)] / 1e6).toFixed(2) + ' MP');
  tesWatchSaves();
  setInterval(() => {}, 1);  // Windows rounds the game threads' timed waits to 15.6 ms without a fast timer on the page
}

var Module = {
""")
# OpenMW's module options are its own page's; this page's Module only carries the page's calls
swap("  arguments: ['/game/core.elf'].concat(params.has('arg') ? ['--arg', params.get('arg')] : [], params.getAll('press').flatMap((p) => p.split(',').flatMap((x) => ['--press', x]))),\n",
     "  arguments: [],\n"
     "  preRun: [],  // (the cloud block checks the page by it)\n")
# ready to start once the engine files are downloaded and the data service worker holds the page
cut("  onRuntimeInitialized: () => {\n    if (missing.length) return;\n", "  preRun: [() => {", """  onRuntimeInitialized: () => {},
  tesReady: () => {
    if (missing.length) return;
    document.getElementById('loading').hidden = true;
    startButton.disabled = false;
    live(startButton, 'play');
    if (layer === 'start') setFocus(startButton);
  },
""")
cut("  preRun: [() => {", "  audioQueuedMs: () =>", "")
swap("  noInitialRun: true,\n", "")
swap("  Module.arguments = Module.arguments.concat(aspect === '16:9' ? ['--widescreen'] : []);\n", "")
swap("  Module.callMain(Module.arguments);\n", "  await tesStart();\n  xboxFrameLoop();\n")
swap("  if (Module._ps2web_set_scale) Module._ps2web_set_scale(Number(scale));\n", "")
swap("  const wasm = engineFile('ps2web.wasm').then((response) => WebAssembly.compileStreaming(response));\n  wasm.catch(failed);\n  Module.instantiateWasm = (imports, done) => {\n    wasm.then((module) => WebAssembly.instantiate(module, imports).then((instance) => done(instance, module))).catch(failed);\n    return {};\n  };\n",
     "  tesEngine.wasm = engineFile('openmw.wasm');\n  tesEngine.data = engineFile('openmw.data');\n")
swap("""  engineFile('ps2web.data').then((response) => response.arrayBuffer()).then((data) => {
    Module.getPreloadedPackage = () => data;
    const engine = document.createElement('script');
    engine.src = withBuild(document.getElementById('engine').content.querySelector('script').getAttribute('src'));
    engine.async = true;
    document.body.appendChild(engine);
  }).catch(failed);""", """  Promise.all([tesEngine.wasm, tesEngine.data]).then(() => { engineLoaded = true; tesMaybeReady(); }).catch(failed);""")
# the PlayTab cloud block: the Xbox one, one file for every Xbox page of the host
swap('<script src="/pt-cloud/cloud-ps2.js?v=20261110" data-pt-cloud></script>', '<script src="/pt-cloud-xbox/cloud-xbox.js?v=20261118" data-pt-cloud></script>')
# GPL-3.0: the engine's source (openmw-web with this port's changes) is named on the page's info line
swap("  if (!ENGINE_BUILD.startsWith(\x27__\x27)) parts.push(ENGINE_BUILD);\n", "  if (!ENGINE_BUILD.startsWith(\x27__\x27)) parts.push(ENGINE_BUILD);\n  parts.push(\x27OpenMW (openmw-web), GPL-3.0: github.com/AlkanoidX/tesmx-src\x27);\n")
