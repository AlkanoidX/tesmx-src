#!/usr/bin/env python3
# make_page.py: builds Morrowind's page (web/index.html) from the PS2 project's page source, shell.html, which is the
# reference for the look and the menu (PAGE_DESIGN.md). The page's own code is kept; only what talks to the engine
# is swapped. The engine is OpenMW as built by openmw-web (github.com/Virtastic/openmw-web, GPL-3.0; this port's
# build and changes: ~/xbox-web/tesm, CLAUDE.md section 23). It runs in its own page (engine.html, make_engine.py)
# in a frame over the stage; page_engine.py joins the two (pads, sound, engine files, resolution, saves), and
# page_keeper.py keeps the game data (data-sw.js) on the device ahead of the game.
# Every replacement must match, so a change in shell.html that breaks one stops the build.
# usage: make_page.py [title]
import hashlib, os, re, sys

SHELL = "/mnt/d/PS2 RECOMP/ps2-web-recomp/web/shell.html"
WEB = os.path.expanduser("~/xbox-web/tesm/web/")
HERE = os.path.dirname(os.path.abspath(__file__))
TITLE = sys.argv[1] if len(sys.argv) > 1 else "The Elder Scrolls III: Morrowind"
# the page's own settings keep their names (PS2_SCALE: the recommended resolution). Nothing is skipped: the
# Bethesda logo and the intro film play, then the game's own menu.
ENV = "PS2_SCALE=2 PS2_ASPECT=16:9"

c = open(SHELL, encoding="utf-8").read().replace("\r\n", "\n")

def swap(old, new, count=1):
    global c
    assert c.count(old) >= 1, "not found: " + old[:70]
    c = c.replace(old, new, count)

def cut(start, end, new):  # from `start` up to (not including) `end`
    global c
    i = c.index(start)
    j = c.index(end, i)
    c = c[:i] + new + c[j:]

stamp = hashlib.sha1(open(WEB + "openmw.wasm", "rb").read()).hexdigest()[:12]
swap("<template id=\"engine\">{{{ SCRIPT }}}</template>", "<template id=\"engine\"></template>")
swap("'__GAME_TITLE__'", repr(TITLE))
swap("'__GAME_ENV__'", repr(ENV))
swap("'__ENGINE_BUILD__'", repr(stamp))
swap("<title>PS2</title>", "<title>" + TITLE + "</title>")

# wording: the console's name in the visible texts (the translations block only)
i, j = c.index("const LANGS = "), c.index("// ---------- size: 1rem")
c = c[:i] + c[i:j].replace("PlayStation 2", "Xbox").replace("PS2", "Xbox") + c[j:]

# the start window's first step names the PlayTab engine, not the console's system (user's wording, 2026-11-15)
BOOT = [("Starting the PlayTab engine", "The engine and the game’s modules"), ("Démarrage du moteur PlayTab", "Le moteur et les modules du jeu"),
        ("Arrancando el motor PlayTab", "El motor y los módulos del juego"), ("PlayTab-Engine startet", "Die Engine und die Module des Spiels"),
        ("Avvio del motore PlayTab", "Il motore e i moduli del gioco"), ("Iniciando o motor PlayTab", "O motor e os módulos do jogo"),
        ("Uruchamianie silnika PlayTab", "Silnik i moduły gry"), ("PlayTab motoru başlatılıyor", "Motor ve oyunun modülleri")]
found = re.findall(r"bootSystem: '[^']*', bootSystemD: '[^']*'", c)
assert len(found) == len(BOOT), found
for old, (title, detail) in zip(found, BOOT):
    swap(old, "bootSystem: '%s', bootSystemD: '%s'" % (title, detail))

# touch controls: the Xbox pad's names (same places and bits; L1/R1 are the white and black buttons, shown as LB/RB)
for old, new in (('data-btn="256">L2<', 'data-btn="256">LT<'), ('data-btn="1024">L1<', 'data-btn="1024">LB<'), ('data-btn="2048">R1<', 'data-btn="2048">RB<'),
                 ('data-btn="512">R2<', 'data-btn="512">RT<'), ('data-btn="1">Select<', 'data-btn="1">Back<'), ('data-btn="4096">△<', 'data-btn="4096">Y<'),
                 ('data-btn="32768">□<', 'data-btn="32768">X<'), ('data-btn="8192">○<', 'data-btn="8192">B<'), ('data-btn="16384">✕<', 'data-btn="16384">A<')):
    swap(old, new)

# The menu button can be dragged anywhere on a touch screen (user's request: it sat on the touch controls). A touch
# that moves more than 10 px drags it, a shorter one is the usual tap that opens the menu; its place is kept on the
# device (per screen shape, a phone turned the other way has its own) and brought back inside the screen when the
# screen changes. Mouse, pad and keyboard are untouched.
swap("const store = (key, value) => { try { localStorage.setItem('ps2web-' + key, value); } catch (e) {} };\n",
     """const store = (key, value) => { try { localStorage.setItem('ps2web-' + key, value); } catch (e) {} };
function floatButton(button, name) {
  const key = () => name + '-at-' + (innerWidth > innerHeight ? 'wide' : 'tall');
  let drag = null;
  function place(x, y) {
    const w = button.offsetWidth || 64, h = button.offsetHeight || 64;
    button.style.left = Math.max(0, Math.min(innerWidth - w, x)) + 'px';
    button.style.top = Math.max(0, Math.min(innerHeight - h, y)) + 'px';
  }
  function restore() {
    const at = (stored(key()) || '').split(',').map(Number);
    if (at.length === 2 && at.every(Number.isFinite)) place(at[0] * innerWidth, at[1] * innerHeight);
    else button.style.left = button.style.top = '';
  }
  button.addEventListener('touchstart', (e) => {
    const t = e.changedTouches[0], r = button.getBoundingClientRect();
    drag = { id: t.identifier, x: t.clientX, y: t.clientY, dx: t.clientX - r.left, dy: t.clientY - r.top, moved: false };
  }, { passive: true });
  button.addEventListener('touchmove', (e) => {
    const t = drag && [...e.changedTouches].find((t) => t.identifier === drag.id);
    if (!t) return;
    if (!drag.moved && Math.hypot(t.clientX - drag.x, t.clientY - drag.y) < 10) return;
    drag.moved = true;
    e.preventDefault();
    place(t.clientX - drag.dx, t.clientY - drag.dy);
  }, { passive: false });
  const end = (e) => {
    if (!drag || ![...e.changedTouches].some((t) => t.identifier === drag.id)) return;
    if (drag.moved) {
      e.preventDefault();  // no click after a drag: the menu stays closed
      const r = button.getBoundingClientRect();
      store(key(), (r.left / innerWidth).toFixed(4) + ',' + (r.top / innerHeight).toFixed(4));
    }
    drag = null;
  };
  button.addEventListener('touchend', end, { passive: false });
  button.addEventListener('touchcancel', end, { passive: false });
  addEventListener('resize', restore);
  restore();
}
floatButton(document.getElementById('menu-button'), 'menu');
// touch screens: a full screen button under the menu button, dragged the same way (its own place is kept)
const fsButton = document.createElement('button');
fsButton.id = 'fs-button'; fsButton.type = 'button'; fsButton.className = 'btn is-icon'; fsButton.hidden = true;
fsButton.setAttribute('aria-label', 'Fullscreen');
fsButton.innerHTML = '<svg viewBox="0 0 24 24" width="55%" height="55%" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg>';
fsButton.addEventListener('click', () => { toggleFullscreen(); refreshOptions(); });
document.getElementById('menu-button').after(fsButton);
floatButton(fsButton, 'fs');
// full screen is offered wherever the browser allows it, inside PlayTab's frame too (its frame carries allow="fullscreen")
const fsAllowed = () => !!(document.fullscreenEnabled || document.webkitFullscreenEnabled);
""")
# On a touch page the two buttons start side by side at the top centre, the one place of the landscape layout with no
# touch control under it (the shoulders are in the top corners, Back/Start at the bottom centre); the room badge goes
# under them. The top left corner, the shared page's place, lay on the LT button.
swap('  #menu-button.idle,', '  #fs-button { position: fixed; z-index: 4; top: calc(6rem + env(safe-area-inset-top)); left: calc(1.2rem + env(safe-area-inset-left)); width: 4rem; height: 4rem; display: none; opacity: .8; }\n'
     '  body.touch #fs-button:not([hidden]) { display: flex; align-items: center; justify-content: center; }\n'
     '  body.touch #menu-button { top: calc(.8rem + env(safe-area-inset-top)); left: calc(50% - 4.4rem); }\n'
     '  body.touch #fs-button { top: calc(.8rem + env(safe-area-inset-top)); left: calc(50% + .4rem); }\n'
     '  body.touch #room-badge { top: calc(5.6rem + env(safe-area-inset-top)); left: 50%; transform: translateX(-50%); }\n'
     '  #menu-button.idle,')
# a touch device starts in full screen (user's request): asked inside the tap on Start, where the browser allows it
swap("  document.getElementById('menu-button').hidden = false;\n",
     "  document.getElementById('menu-button').hidden = false;\n"
     "  fsButton.hidden = !fsAllowed();\n"
     "  if (document.body.classList.contains('touch') && !fullscreen && fsAllowed()) toggleFullscreen();\n")

# touch stick (user's request: moving was hard on a phone). The stick's centre is where the thumb lands (anywhere on
# the ring or a little around it), not the ring's middle; it is fully tilted after a short travel (45% of the ring's
# radius), the centre follows a thumb that goes further (turning back answers at once), and a small rest zone keeps
# a still thumb from drifting.
swap("""      const c = circleOf(f.el);
      let dx = (t.clientX - c.x) / c.r, dy = (t.clientY - c.y) / c.r;
      const len = Math.hypot(dx, dy);
      if (len > 1) { dx /= len; dy /= len; }
      if (f.right) { rx = dx; ry = dy; rstick = true; } else { sx = dx; sy = dy; stick = true; }
      (f.right ? knobR : knob).style.transform = 'translate(' + (dx * c.r * 0.6) + 'px,' + (dy * c.r * 0.6) + 'px)';
""", """      const c = circleOf(f.el), reach = c.r * 0.45;
      if (!f.at) f.at = { x: t.clientX, y: t.clientY };
      let dx = (t.clientX - f.at.x) / reach, dy = (t.clientY - f.at.y) / reach;
      const len = Math.hypot(dx, dy);
      if (len > 1) {
        f.at.x += (dx - dx / len) * reach; f.at.y += (dy - dy / len) * reach;  // the centre follows the thumb
        dx /= len; dy /= len;
      } else if (len < 0.15) dx = dy = 0;
      if (f.right) { rx = dx; ry = dy; rstick = true; } else { sx = dx; sy = dy; stick = true; }
      const kx = Math.max(-c.r, Math.min(c.r, f.at.x - c.x + dx * reach)), ky = Math.max(-c.r, Math.min(c.r, f.at.y - c.y + dy * reach));
      (f.right ? knobR : knob).style.transform = 'translate(' + kx + 'px,' + ky + 'px)';
""")
# and the usual phone-game stick: a thumb put down anywhere on the left half of the picture is the left stick, centred
# where it landed, with a ring and knob drawn under it; the right half stays the right stick (the shared page's rule)
swap("""    const t = e.changedTouches[0];
    touchLook = { id: t.identifier, x0: t.clientX, y0: t.clientY, x: 0, y: 0 };
""", """    const t = [...e.changedTouches].find((t) => t.clientX >= innerWidth / 2);
    if (t) touchLook = { id: t.identifier, x0: t.clientX, y0: t.clientY, x: 0, y: 0 };
""")
swap("for (const type of ['touchstart', 'touchmove', 'touchend', 'touchcancel']) document.getElementById('stage').addEventListener(type, onLook, { passive: true });",
     """const MOVE_REACH = 46;
let touchMove = { id: null, x0: 0, y0: 0, x: 0, y: 0 };
const moveMark = document.createElement('div');
moveMark.style.cssText = 'position:fixed;width:124px;height:124px;margin:-62px 0 0 -62px;border-radius:50%;border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.08);pointer-events:none;z-index:2;display:none';
moveMark.innerHTML = '<div style="position:absolute;left:50%;top:50%;width:54px;height:54px;margin:-27px 0 0 -27px;border-radius:50%;background:rgba(var(--acc-rgb),.5);border:1px solid rgba(255,255,255,.3)"></div>';
document.body.appendChild(moveMark);
function onMoveTouch(e) {
  if (!document.body.classList.contains('touch')) return;
  if (touchMove.id === null && e.type === 'touchstart') {
    const t = [...e.changedTouches].find((t) => t.clientX < innerWidth / 2);
    if (t) touchMove = { id: t.identifier, x0: t.clientX, y0: t.clientY, x: 0, y: 0 };
  }
  let held = false;
  for (const t of e.touches) {
    if (t.identifier !== touchMove.id) continue;
    held = true;
    let dx = (t.clientX - touchMove.x0) / MOVE_REACH, dy = (t.clientY - touchMove.y0) / MOVE_REACH;
    const len = Math.hypot(dx, dy);
    if (len > 1) {
      touchMove.x0 += (dx - dx / len) * MOVE_REACH; touchMove.y0 += (dy - dy / len) * MOVE_REACH;  // the centre follows the thumb
      dx /= len; dy /= len;
    } else if (len < 0.15) dx = dy = 0;
    touchMove.x = dx; touchMove.y = dy;
    moveMark.style.display = 'block';
    moveMark.style.left = touchMove.x0 + 'px'; moveMark.style.top = touchMove.y0 + 'px';
    moveMark.firstChild.style.transform = 'translate(' + dx * MOVE_REACH + 'px,' + dy * MOVE_REACH + 'px)';
  }
  if (!held) { touchMove = { id: null, x0: 0, y0: 0, x: 0, y: 0 }; moveMark.style.display = 'none'; }
}
for (const type of ['touchstart', 'touchmove', 'touchend', 'touchcancel']) document.getElementById('stage').addEventListener(type, onMoveTouch, { passive: true });
for (const type of ['touchstart', 'touchmove', 'touchend', 'touchcancel']) document.getElementById('stage').addEventListener(type, onLook, { passive: true });""")
swap("    if (touchPad.rstick) {\n      rx = axis(touchPad.rx);", "    if (touchMove.id !== null) {\n      lx = axis(touchMove.x);\n      ly = axis(touchMove.y);\n    }\n    if (touchPad.rstick) {\n      rx = axis(touchPad.rx);")
# a larger place to land the thumb than the ring itself
swap("  .knob { position: absolute;", "  .stick::before { content: ''; position: absolute; inset: calc(var(--cell) * -0.7); border-radius: 50%; }\n  .knob { position: absolute;")

# what the browser must have: no JSPI and no tail calls in this engine
swap("  if (typeof WebAssembly.Suspending !== 'function') missing.push('WebAssembly JSPI');\n", "")
swap("  if (!accepts([0, 0x12, 0, 0x0B])) missing.push('WebAssembly tail calls');\n", "")

# settings: OpenMW draws the frame's canvas at the window's pixels, capped by a pixel budget (page_engine.py):
# 720p, 1080p, 1440p worth of pixels
swap("{ 1: '640×512', 2: '1280×1024', 3: '1920×1536' }", "{ 1: '720p', 2: '1080p', 3: '1440p' }")
# the recommended resolution follows the player's screen (user's request): the smallest of 720p/1080p/1440p that has
# at least the screen's own lines; a phone stays at 720p
swap("scale: TOUCH_SCREEN ? '1' : (GAME_ENV.match(/PS2_SCALE=([123])/) || [0, '1'])[1],",
     "scale: TOUCH_SCREEN ? '1' : (() => { const lines = Math.min(screen.width, screen.height) * (window.devicePixelRatio || 1); return lines <= 720 ? '1' : lines <= 1080 ? '2' : '3'; })(),")

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "page_engine.py"), encoding="utf-8").read())

# ---- Start window: every one of its three steps has a progress bar and a percentage (user's rule, 2026-11-15, for
# every port; the first step, "Starting the PlayTab engine", above all). The figures are real counts, measured once
# per game and written here:
#   BOOT_KIB = (disc KiB downloaded when the first picture shows, disc KiB downloaded when the window closes)
#   BOOT_MS  = time from the first picture to the closing of the window on the PC (the game's own start-up work)
# The page logs them at the end of each start ("[boot] ..." console line): run the delivered page once without any
# test switch and copy the numbers. Step 1 = the engine start, which is the disc read up to the first picture (in
# Crash Nitro Kart 172 MB: online that is nearly all of the wait). Step 2 = disc read up to the end of the start.
# Step 3 = pictures shown out of the BOOT_PICTURES that close the window (see the films block). A percentage never goes back; 100 only when the
# step is over.
BOOT_KIB = (101179, 197310)  # measured 2026-11-21 from GitHub, cold start (X_TESM on a local server, data from AlkanoidX/tesmx)
BOOT_MS = 500
swap("  .boot-step .bar { margin-top: .6rem; }\n",
     "  .boot-step .bar { margin-top: .6rem; height: .5rem; } .boot-step .bar i { transition: width .5s linear; }\n"
     "  .boot-head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; }\n"
     "  .boot-pct { flex: none; font-weight: 650; color: var(--dim); } .boot-step.active .boot-pct, .boot-step.ok .boot-pct { color: var(--accent); }\n")
HEAD = '<span class="boot-head"><span data-tx="%s"></span><b class="boot-pct num">0%%</b></span>'
BAR = '<div class="bar"><i></i></div>'
swap('<span data-tx="bootSystem"></span><span class="boot-detail" data-tx="bootSystemD"></span></span>',
     HEAD % 'bootSystem' + '<span class="boot-detail" data-tx="bootSystemD"></span>' + BAR + '</span>')
swap('<span data-tx="bootDisc"></span><span class="boot-detail num" id="boot-disc"></span><div class="bar busy" id="boot-disc-bar" hidden><i></i></div></span>',
     HEAD % 'bootDisc' + '<span class="boot-detail num" id="boot-disc"></span>' + BAR + '</span>')
swap('<span data-tx="bootFrames"></span><span class="boot-detail" id="boot-frames"></span></span>',
     HEAD % 'bootFrames' + '<span class="boot-detail" id="boot-frames"></span>' + BAR + '</span>')
swap("  boot.hidden = false;\n  mark('runtime', 'active');\n",
     "  boot.hidden = false;\n  mark('runtime', 'active');\n"
     "  const BOOT_KIB = %s, BOOT_MS = %d, BOOT_PICTURES = 20;\n"
     "  const pct = (name, value) => {\n"
     "    const s = step(name), p = Math.max(Number(s.dataset.pct) || 0, Math.min(100, Math.floor(value)));\n"
     "    s.dataset.pct = p;\n"
     "    s.querySelector('.boot-pct').textContent = p + '%%';\n"
     "    s.querySelector('.bar i').style.width = p + '%%';\n"
     "  };\n"
     "  let firstAt = 0, firstKib = 0;\n" % (repr(list(BOOT_KIB)), BOOT_MS))
swap("      document.getElementById('boot-disc-bar').hidden = !loading;\n",
     "      if (count > 0 && !firstAt) firstAt = performance.now(), firstKib = bytes / 1024;\n"
     "      pct('runtime', count > 0 ? 100 : Math.min(99, bytes / 1024 / BOOT_KIB[0] * 100));\n"
     "      pct('disc', Math.min(99, bytes / 1024 / BOOT_KIB[1] * 100));\n")
swap("      steady = perSecond * 2 >= 15 ? steady + 1 : 0;\n",
     "      steady = perSecond * 2 >= 15 ? steady + 1 : 0;\n"
     "      pct('frames', Math.min(99, count / BOOT_PICTURES * 100));\n")
swap("        booting = false;\n        mark('frames', 'ok');\n",
     "        booting = false;\n        mark('disc', 'ok');\n        mark('frames', 'ok');\n"
     "        pct('disc', 100); pct('frames', 100);\n"
     "        console.log('[boot] first picture after ' + Math.round(firstAt - begun) + ' ms and ' + Math.round(firstKib) + ' KiB of disc, start over after '"
     " + Math.round(performance.now() - begun) + ' ms and ' + Math.round(bytes / 1024) + ' KiB');\n")
LAYOUT = "openworld"  # Morrowind: one in-game set of RPG buttons, built on the open-world block below

# ---- Touch layout (user's rules: fit the layout to the kind of game; "find the controls on the internet and follow
# them"; "keep the utility buttons apart from the action buttons: not one big pack"; "holding a control 3 seconds lets
# one move it"; icons from an existing pack, never emoji). Round buttons with an icon and one word.
# Controls: OpenMW's default gamepad bindings (apps/openmw/mwinput/bindingsmanager.cpp), which follow the Xbox
# game's (UESP, Morrowind:Controls, Xbox column: right stick look, left stick move, left stick click sneak, right
# stick click change view, white journal, black sleep/wait): RT use (attack, cast, use the item), LT jump,
# A activate (talk, open, take), B inventory and menus, X ready weapon, Y ready magic, white journal, black rest,
# L3 sneak, R3 first / third person, Start game menu, d-pad menus.
# One in-game set; the pad-shaped controls stay for the menus. In game or in a menu: OpenMW asks for relative mouse
# mode in play only (Module.__omwWantsMouseLock in its page), not a guess.
# Left thumb anywhere on the left half of the picture = the stick; the right half = the look (right stick).
# Moving the buttons: a finger kept 3 s on a button that is tapped in play (not on Attack or Sneak, held down in play)
# opens the move mode: every round button can then be dragged, "OK" closes it and "Reset" puts them back. Places are
# kept on the device per screen shape (ps2web-world-at-wide / -tall), as fractions of the screen.
# Icons: game-icons.net (Creative Commons BY 3.0), authors Lorc and Delapouite; files in icons/ beside this folder
# (<author>_<name>.svg as downloaded, CREDITS.txt); the credit line goes in the page and in LISEZMOI.txt.
WORLD_FILES = {"attack": "lorc_broadsword", "use": "lorc_hand", "jump": "delapouite_jump-across", "menu": "lorc_knapsack",
               "weapon": "lorc_crossed-swords", "magic": "lorc_magic-swirl", "journal": "lorc_scroll-unfurled",
               "rest": "delapouite_night-sleep", "sneak": "lorc_hood", "view": "delapouite_eye-target"}
def world_icon(what):
    text = open(os.path.join(HERE, "..", "icons", WORLD_FILES[what] + ".svg"), encoding="utf-8").read()
    shapes = [d for d in re.findall(r'<path[^>]*\sd="([^"]+)"', text) if not d.replace(" ", "").lower().startswith("m00h512v512h0z")]
    assert shapes, what
    return "".join('<path d="%s"/>' % d for d in shapes)
WORLD_ICON = {what: world_icon(what) for what in WORLD_FILES}
# each button: (pad button, icon, word, size, colour, held down in play, then for an action button the right and
# bottom of its box in button units)
TAG = {"RT": "RT", "LT": "LT", "A": "A", "B": "B", "X": "X", "Y": "Y", "white": "LB", "black": "RB", "L3": "L3", "R3": "R3", "up": "UP"}  # the touch pad's own names
BIT = {"RT": 512, "LT": 256, "A": 16384, "B": 8192, "X": 32768, "Y": 4096, "white": 1024, "black": 2048, "L3": 2, "R3": 4, "up": 16}
WORLD_FOOT = [("RT", "attack", "attack", "big", "red", 1, .1, 1.2), ("A", "use", "use", "med", "green", 0, 2.15, 0),
              ("B", "menu", "menu", "med", "yellow", 0, 2.15, 1.7), ("X", "weapon", "weapon", "med", "white", 0, 3.8, .55),
              ("Y", "magic", "magic", "med", "blue", 0, .25, 3.3), ("LT", "jump", "jump", "sml", "white", 0, 2.05, 3.5)]
WORLD_FOOT_UTIL = [("white", "journal", "journal", "sml", "white", 0), ("black", "rest", "rest", "sml", "white", 0),
                   ("L3", "sneak", "sneak", "sml", "white", 1), ("R3", "view", "view", "sml", "white", 0)]
WORLD_CAR = []
WORLD_CAR_UTIL = []
WORLD_KEYS = "attack use jump menu weapon magic journal rest sneak view done reset move tip".split()
WORLD_BUTTON_WORDS = 10  # the first keys are words on the game buttons: English in every language (user's rule)
_EN = "Attack Use Jump Menu Weapon Magic Journal Rest Sneak View "
WORLD_TX = {  # one text per key, in the order of WORLD_KEYS; _ stands for a space
    "en": _EN + "OK Reset Drag_the_buttons_where_you_want_them To_move_the_buttons,_hold_the_green_one_for_3_seconds_(Use,_A)",
    "fr": _EN + "OK Réinitialiser Glisse_les_boutons_où_tu_veux Pour_déplacer_les_boutons,_maintiens_le_bouton_vert_3_secondes_(Use,_A)",
    "es": _EN + "OK Restablecer Arrastra_los_botones_adonde_quieras Para_mover_los_botones,_mantén_el_botón_verde_3_segundos_(Use,_A)",
    "de": _EN + "OK Zurücksetzen Zieh_die_Tasten_an_die_gewünschte_Stelle Zum_Verschieben_der_Tasten_die_grüne_Taste_3_Sekunden_halten_(Use,_A)",
    "it": _EN + "OK Ripristina Trascina_i_pulsanti_dove_vuoi Per_spostare_i_pulsanti,_tieni_premuto_quello_verde_per_3_secondi_(Use,_A)",
    "pt": _EN + "OK Repor Arrasta_os_botões_para_onde_quiseres Para_mover_os_botões,_mantém_o_botão_verde_durante_3_segundos_(Use,_A)",
    "pl": _EN + "OK Resetuj Przeciągnij_przyciski_tam,_gdzie_chcesz Aby_przesunąć_przyciski,_przytrzymaj_zielony_przez_3_sekundy_(Use,_A)",
    "tr": _EN + "Tamam Sıfırla Düğmeleri_istediğin_yere_sürükle Düğmeleri_taşımak_için_yeşil_düğmeyi_3_saniye_basılı_tut_(Use,_A)",
}
if LAYOUT == "openworld":
    import json as _json
    def ctl(group, button, icon, word, size, colour, held, right=None, bottom=None):
        place = "" if right is None else ' style="right:calc(var(--rc)*%s);bottom:calc(var(--rc)*%s)"' % (right, bottom)
        return ('<div class="ctl race wb %s c-%s%s" data-btn="%d" data-key="%s:%s"%s>'
                '<svg viewBox="0 0 512 512" fill="currentColor">%s</svg>'
                '<small data-tx="w.%s"></small><b class="tag t-%s">%s</b></div>') % (size, colour, " held" if held else "", BIT[button], group, button, place,
                                                                             WORLD_ICON[icon], word, button, TAG[button])
    # Two layouts. The pad-shaped controls (A B X Y, shoulders, sticks, cross) stay for the menus; the in-game
    # set is added beside them and shown while the world is drawn (class in-world on #touch, from web_world_state: skinned models drawn, manhunt_d3d.cpp)
    swap('    <div class="stick" data-stick="r"><div class="knob" id="knob-r"></div></div>\n  </div>\n</div>\n',
         '    <div class="stick" data-stick="r"><div class="knob" id="knob-r"></div></div>\n'
         '    <div class="race-pad pad-foot">' + "".join(ctl("foot", *b) for b in WORLD_FOOT) + '</div>\n'
         '    <div class="race-pad pad-car">' + "".join(ctl("car", *b) for b in WORLD_CAR) + '</div>\n  </div>\n'
         '  <div class="world-util pad-foot">' + "".join(ctl("foot", *b) for b in WORLD_FOOT_UTIL) + '</div>\n'
         '  <div class="world-util pad-car">' + "".join(ctl("car", *b) for b in WORLD_CAR_UTIL) + '</div>\n'
         '  <div id="world-edit" hidden><span data-tx="w.move"></span><button type="button" id="world-reset" data-tx="w.reset"></button><button type="button" id="world-done" data-tx="w.done"></button></div>\n'
         '</div>\n')
    swap('<div id="touch" class="controls"', '<!-- Touch button icons: game-icons.net (Lorc, Delapouite), CC BY 3.0 -->\n<div id="touch" class="controls world"')
    words = {l: {"w." + k: w.replace("_", " ") for k, w in zip(WORLD_KEYS, v.split())} for l, v in WORLD_TX.items()}
    assert all(len(w) == len(WORLD_KEYS) for w in words.values())
    for l in words:  # user's rule: the words on the game buttons are always in English, like the game; only the move mode's texts follow the page
        for k in WORLD_KEYS[:WORLD_BUTTON_WORDS]: words[l]["w." + k] = words["en"]["w." + k]
    swap("let lang = pickLang(params.get('lang'));\n",
         "for (const [l, words] of Object.entries(" + _json.dumps(words, ensure_ascii=False) + ")) Object.assign(TX[l], words);  // what each touch button does in this game\n"
         "let lang = pickLang(params.get('lang'));\n")
    swap("  body.touch.hide-controls .controls { display: none; }\n",
         "  .world.in-world .cluster.right, .world .world-util { --rc: calc(var(--cell) * .8); } .world.in-world .cluster.right { justify-content: flex-end; }\n"
         "  .world:not(.in-world) .race-pad, .world:not(.in-world) .world-util { display: none !important; }\n"
         "  .world.in-world .cluster > .shoulders, .world.in-world .cluster.right > .face, .world.in-world .cluster.right > .stick { display: none; }\n"
         "  .world .wb .tag { position: absolute; top: 9%; left: 50%; transform: translateX(-50%); font: 700 calc(var(--rc) * .17)/1 system-ui, sans-serif;\n"
         "    padding: 1px 5px; border-radius: 6px; background: rgba(0, 0, 0, .6); color: #eef2f0; letter-spacing: .02em; }\n"
         "  .world .wb .t-A { background: #2f9e4f; } .world .wb .t-B { background: #c8352e; } .world .wb .t-X { background: #2b62c9; } .world .wb .t-Y { background: #c99a12; }\n"
         "  .world .wb svg { margin-top: 12%; }\n"
         "  @keyframes wbhint { 0%, 100% { box-shadow: 0 0 0 0 rgba(95, 224, 138, .9); transform: scale(1); } 50% { box-shadow: 0 0 0 12px rgba(95, 224, 138, 0); transform: scale(1.12); } }\n"
         "  .world .wb.hint { animation: wbhint 1s ease-in-out infinite; background: rgba(95, 224, 138, .35); }\n"
         "  #wb-tip { position: fixed; z-index: 6; max-width: min(320px, 70vw); padding: 10px 14px; border-radius: 12px; background: rgba(12, 18, 16, .95);\n"
         "    border: 2px solid #5fe08a; color: #eef2f0; font: 600 14px/1.35 system-ui, sans-serif; pointer-events: none; box-shadow: 0 6px 24px rgba(0, 0, 0, .5); }\n"
         "  #wb-tip::after { content: ''; position: absolute; top: 100%; left: var(--arrow, 50%); transform: translateX(-50%); border: 9px solid transparent; border-top-color: #5fe08a; }\n"
         "  .world .race-pad { position: relative; width: calc(var(--rc) * 6); height: calc(var(--rc) * 5.4); }\n"
         "  .world .world-util { position: absolute; top: 8px; left: calc(50% + 62px); display: flex; gap: 6px; pointer-events: auto; opacity: .75; }\n"
         "  .world .world-util .wb { position: relative; }\n"
         "  .world .pad-car, .world.driving .pad-foot { display: none; } .world.driving .race-pad.pad-car { display: block; } .world.driving .world-util.pad-car { display: flex; }\n"
         "  .world .wb { position: absolute; flex-direction: column; gap: 0; border-radius: 50%; border-width: 2px; overflow: hidden; touch-action: none; }\n"
         "  .world .wb.big { width: calc(var(--rc) * 1.9); height: calc(var(--rc) * 1.9); } .world .wb.med { width: calc(var(--rc) * 1.55); height: calc(var(--rc) * 1.55); }\n"
         "  .world .wb.sml { width: calc(var(--rc) * 1.2); height: calc(var(--rc) * 1.2); }\n"
         "  .world .wb svg { width: 50%; height: 50%; flex: none; } .world .wb.sml svg { width: 46%; height: 46%; }\n"
         "  .world .wb small { font-size: calc(var(--rc) * .2); font-weight: 600; line-height: 1.1; white-space: nowrap; color: #eef2f0; }\n"
         "  .world .wb.sml small { font-size: calc(var(--rc) * .175); }\n"
         "  .world .c-green { color: #5fe08a; border-color: #5fe08a; } .world .c-red { color: #ff7b7b; border-color: #ff7b7b; }\n"
         "  .world .c-yellow { color: #ffd966; border-color: #ffd966; } .world .c-blue { color: #8fb4ff; border-color: #8fb4ff; }\n"
         "  .world .c-white { color: #f2f5f4; border-color: rgba(255, 255, 255, .55); }\n"
         "  .world .wb { background: rgba(10, 14, 12, .55); }  /* readable over a light scene */\n"
         "  .world.editing .wb { border-style: dashed; background: rgba(var(--acc-rgb), .28); } .world.editing .wb.moving { background: rgba(var(--acc-rgb), .6); }\n"
         "  #world-edit { position: fixed; z-index: 5; top: 62px; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 10px; padding: 8px 12px;\n"
         "    border-radius: 14px; background: rgba(12, 18, 16, .92); border: 1px solid rgba(255, 255, 255, .2); color: #eef2f0; font-size: 13px; pointer-events: auto; white-space: nowrap; }\n"
         "  #world-edit[hidden] { display: none; }\n"
         "  #world-edit button { font: inherit; font-weight: 650; padding: 6px 14px; border-radius: 10px; border: 1px solid rgba(255, 255, 255, .3); background: transparent; color: inherit; }\n"
         "  #world-edit #world-done { background: var(--accent); color: #06130c; border-color: transparent; }\n"
         "  body.touch .world.in-world .cluster.right > .stick { display: none; }  /* the left stick stays drawn (user: the cross alone is not enough) */\n"
         "  body.touch .world.in-world .dpad { transform: scale(.78); transform-origin: left center; }\n"
         "  body.touch.hide-controls .controls { display: none; }\n")
    swap("    body.touch .cluster.mid { top: auto; left: 50%; transform: translateX(-50%); }\n",
         "    body.touch .cluster.mid { top: auto; left: 50%; transform: translateX(-50%); }\n"
         "    body.touch .world .cluster.right, body.touch .world .world-util { --rc: calc(var(--cell) * 1.05); } body.touch .world .cluster.right { align-items: flex-end; }\n")
    # the shell's drawn right stick is cut with the right cluster: its knob is missing (every touch threw before)
    swap("  if (!rstick) knobR.style.transform = '';\n", "  if (!rstick && knobR) knobR.style.transform = '';\n")
    swap("      if (button && touchRoot.contains(button)) buttons |= Number(button.dataset.btn);\n",
         "      if (button && touchRoot.contains(button)) buttons |= Number(button.dataset.btn);\n"
         "      for (const el of raceButtons) {  // a thumb on the border of two buttons presses both\n"
         "        const r = el.getBoundingClientRect();\n"
         "        if (r.width && Math.hypot(Math.max(r.left - t.clientX, 0, t.clientX - r.right), Math.max(r.top - t.clientY, 0, t.clientY - r.bottom)) <= RACE_REACH) buttons |= Number(el.dataset.btn);\n"
         "      }\n")
    swap("  setTimeout(() => note(t('menuHint')), 1500);\n",
         "  setTimeout(() => note(t('menuHint')), 1500);\n"
         "  // how to move the touch buttons: shown at each start when the in-game buttons first appear (see the layout poll)\n")
    swap("function onTouch(e) {\n",
         "const raceButtons = [...touchRoot.querySelectorAll('.race')], RACE_REACH = 8;\n"
         "function worldHint() {  // the green button pulses 8 s with the tip in a bubble above it\n"
         "  const el = [...touchRoot.querySelectorAll('.wb.c-green')].find((b) => b.getBoundingClientRect().width);\n"
         "  if (!el) return;\n"
         "  el.classList.add('hint');\n"
         "  const r = el.getBoundingClientRect(), tip = document.createElement('div');\n"
         "  tip.id = 'wb-tip'; tip.textContent = t('w.tip'); document.body.appendChild(tip);\n"
         "  const w = tip.offsetWidth, h = tip.offsetHeight, x = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2));\n"
         "  tip.style.left = x + 'px'; tip.style.top = Math.max(8, r.top - h - 14) + 'px';\n"
         "  tip.style.setProperty('--arrow', (r.left + r.width / 2 - x) + 'px');\n"
         "  setTimeout(() => { el.classList.remove('hint'); tip.remove(); }, 8000);\n"
         "}\n"
         "const worldForced = new URLSearchParams(location.search).get('world'); let worldLast = -1, worldSeen = 99, worldTipShown = false;\n"
         "setInterval(() => {  // on foot or in a vehicle: read in the game's memory (see make_page.py), the buttons follow\n"
         "  const driving = false;  // Morrowind: one set\n"
         "  let inWorld = worldForced === '1';\n"
         "  if (worldForced === null && Module.running && tesWin && tesWin.Module) inWorld = !!tesWin.Module.__omwWantsMouseLock;  // OpenMW: relative mouse = in play\n"
         "  if (!worldMove.on && touchRoot.classList.contains('in-world') !== inWorld) touchRoot.classList.toggle('in-world', inWorld);\n"
         "  if (inWorld && !worldTipShown && document.body.classList.contains('touch')) {  // once per start: the tip, and the green button pulses\n"
         "    worldTipShown = true;\n"
         "    setTimeout(() => worldHint(), 1500);\n"
         "  }\n"
         "  if (!worldMove.on) touchRoot.classList.toggle('driving', driving);\n"
         "}, 200);\n"
         "// Moving the round buttons: 3 s on a button that is tapped in play opens the move mode (see make_page.py).\n"
         "const worldMove = { on: false, hold: null, drag: null, at: {} };\n"
         "const worldStore = () => 'ps2web-world-at-' + (innerWidth >= innerHeight ? 'wide' : 'tall');\n"
         "function worldPlace() {\n"
         "  try { worldMove.at = JSON.parse(localStorage.getItem(worldStore()) || '{}') || {}; } catch (e) { worldMove.at = {}; }\n"
         "  for (const el of raceButtons) { const at = worldMove.at[el.dataset.key]; el.style.transform = at ? 'translate(' + at[0] * innerWidth + 'px,' + at[1] * innerHeight + 'px)' : ''; }\n"
         "}\n"
         "function worldMode(on) {\n"
         "  worldMove.on = on; worldMove.drag = null;\n"
         "  touchRoot.classList.toggle('editing', on);\n"
         "  document.getElementById('world-edit').hidden = !on;\n"
         "  for (const el of raceButtons) {  // in the move mode the game gets no button from them\n"
         "    if (on) { el.dataset.bit = el.dataset.btn; el.dataset.btn = '0'; } else if (el.dataset.bit) el.dataset.btn = el.dataset.bit;\n"
         "    el.classList.remove('moving', 'on');\n"
         "  }\n"
         "}\n"
         "function worldGrab(el, t) {\n"
         "  const at = worldMove.at[el.dataset.key] || [0, 0];\n"
         "  worldMove.drag = { el, id: t.identifier, x: t.clientX, y: t.clientY, ox: at[0] * innerWidth, oy: at[1] * innerHeight };\n"
         "  el.classList.add('moving');\n"
         "}\n"
         "touchRoot.addEventListener('touchstart', (e) => {\n"
         "  const el = e.target.closest && e.target.closest('.wb'), t = e.changedTouches[0];\n"
         "  if (!el) return;\n"
         "  if (worldMove.on) { if (!worldMove.drag) worldGrab(el, t); return; }\n"
         "  if (el.classList.contains('held')) return;\n"
         "  clearTimeout(worldMove.hold && worldMove.hold.timer);\n"
         "  worldMove.hold = { id: t.identifier, x: t.clientX, y: t.clientY, timer: setTimeout(() => {\n"
         "    worldMove.hold = null; worldMode(true); worldGrab(el, t);\n"
         "    if (navigator.vibrate) navigator.vibrate(40);\n"
         "  }, 3000) };\n"
         "}, { passive: true });\n"
         "touchRoot.addEventListener('touchmove', (e) => {\n"
         "  for (const t of e.changedTouches) {\n"
         "    const h = worldMove.hold, d = worldMove.drag;\n"
         "    if (h && t.identifier === h.id && Math.hypot(t.clientX - h.x, t.clientY - h.y) > 14) { clearTimeout(h.timer); worldMove.hold = null; }\n"
         "    if (d && t.identifier === d.id) {  // the button follows the finger and stays on the screen\n"
         "      d.el.style.transform = 'translate(' + d.ox + 'px,' + d.oy + 'px)';\n"
         "      const r = d.el.getBoundingClientRect();\n"
         "      const nx = Math.max(-r.left + d.ox, Math.min(innerWidth - r.right + d.ox, d.ox + t.clientX - d.x));\n"
         "      const ny = Math.max(-r.top + d.oy, Math.min(innerHeight - r.bottom + d.oy, d.oy + t.clientY - d.y));\n"
         "      d.el.style.transform = 'translate(' + nx + 'px,' + ny + 'px)';\n"
         "      worldMove.at[d.el.dataset.key] = [nx / innerWidth, ny / innerHeight];\n"
         "    }\n"
         "  }\n"
         "}, { passive: true });\n"
         "const worldLift = (e) => {\n"
         "  for (const t of e.changedTouches) {\n"
         "    if (worldMove.hold && t.identifier === worldMove.hold.id) { clearTimeout(worldMove.hold.timer); worldMove.hold = null; }\n"
         "    if (worldMove.drag && t.identifier === worldMove.drag.id) {\n"
         "      worldMove.drag.el.classList.remove('moving'); worldMove.drag = null;\n"
         "      try { localStorage.setItem(worldStore(), JSON.stringify(worldMove.at)); } catch (err) {}\n"
         "    }\n"
         "  }\n"
         "};\n"
         "touchRoot.addEventListener('touchend', worldLift, { passive: true });\n"
         "touchRoot.addEventListener('touchcancel', worldLift, { passive: true });\n"
         "document.getElementById('world-done').addEventListener('click', () => worldMode(false));\n"
         "document.getElementById('world-reset').addEventListener('click', () => { try { localStorage.removeItem(worldStore()); } catch (err) {} worldPlace(); });\n"
         "addEventListener('resize', worldPlace);\n"
         "worldPlace();\n"
         "function onTouch(e) {\n")

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "page_keeper.py"), encoding="utf-8").read())

# Automatic resolution drop, far less eager (user, 2026-11-17: "the automatic resolution change is TOO aggressive,
# the game must really stutter badly before it lowers one step"). The shared page took any second under 55 fps as
# "cannot keep up"; Fable (a 30 fps game, where this rule was made) runs at 30 by design, so every second counted and the page lowered the resolution 15 s
# into play, then again. The Xbox engine also reports no render thread idle time (always 0), so that guard never held.
# Now: a second counts only under 70% of the game's own rate (21 of 30) or with more than 10% of the sound missing,
# it takes 10 such seconds in a row, and nothing is lowered in the first 45 s (PC) / 20 s (phone) of play or of the
# last change.
swap("  phoneBad = (fps < 55 || gaps > 3) && renderIdle < 15 ? phoneBad + 1 : 0;\n",
     "  phoneBad = (fps < GAME_FPS * 0.7 || gaps > 10) ? phoneBad + 1 : 0;  // GAME_FPS: the game's own rate\n")
swap("  if (phoneBad < 3 || now - phoneSince < (TOUCH_SCREEN ? 6000 : 15000)) return;\n",
     "  if (phoneBad < 10 || now - phoneSince < (TOUCH_SCREEN ? 20000 : 45000)) return;\n")
swap("let phoneBad = 0, phoneSince = 0;\n", "let phoneBad = 0, phoneSince = 0;\nconst GAME_FPS = 60;  // OpenMW: the screen's rate, 60 on most\n")

open(WEB + "index.html", "w", encoding="utf-8").write(c)
print("page written, engine", stamp, len(c), "bytes")
