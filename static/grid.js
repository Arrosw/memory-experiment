const phaseData = document.getElementById("phase-data");
const PHASE     = phaseData.dataset.phase;
const X_ORDER   = JSON.parse(phaseData.dataset.xOrder);
const Y_ORDER   = JSON.parse(phaseData.dataset.yOrder);
const AVAIL_MATS = JSON.parse(phaseData.dataset.availMats);
const AVAIL_CATS = JSON.parse(phaseData.dataset.availCats);
const NX = X_ORDER.length;
const NY = Y_ORDER.length;

const yRailEl    = document.getElementById("y-rail");
const xRailEl    = document.getElementById("x-rail");
const yDotEl     = document.getElementById("y-dot");
const xDotEl     = document.getElementById("x-dot");
const imgLowerEl = document.getElementById("preview-img-lower");
const imgUpperEl = document.getElementById("preview-img-upper");
const confirmEl  = document.getElementById("confirm-btn");

let thumbMap = {};
let xPos = 0.0;  // float in [0, NX-1]; integer = snapped position
let yIdx = 0;
const startMs = Date.now();

function getKey(xi, yi) {
  return AVAIL_CATS[Y_ORDER[yi]] + '_' + AVAIL_MATS[X_ORDER[xi]];
}

// Place X dot as % of x-rail width; transform: translateX(-50%) handles centering
function placeXDot(xp) {
  xDotEl.style.left = (xp / (NX - 1) * 100) + "%";
}

// Place Y dot as % of y-rail height; yi=0 → bottom, yi=N-1 → top
function placeYDot(yi) {
  yDotEl.style.top = ((NY - 1 - yi + 0.5) / NY * 100) + "%";
}

function updateImage(xp) {
  const lo = Math.floor(xp);
  const hi = Math.min(lo + 1, NX - 1);
  const alpha = xp - lo;
  const loKey = getKey(lo, yIdx);
  const hiKey = getKey(hi, yIdx);
  if (thumbMap[loKey]) {
    imgLowerEl.src = thumbMap[loKey];
    imgLowerEl.style.display = "block";
  }
  imgUpperEl.src = thumbMap[hiKey] || "";
  imgUpperEl.style.opacity = alpha;
  confirmEl.disabled = false;
}

function setX(xp) {
  xPos = Math.max(0, Math.min(NX - 1, xp));
  placeXDot(xPos);
  updateImage(xPos);
}

function snapX() {
  xPos = Math.round(xPos);
  placeXDot(xPos);
  updateImage(xPos);
}

function setY(yi) {
  yIdx = Math.max(0, Math.min(NY - 1, yi));
  placeYDot(yIdx);
  updateImage(xPos);
}

function xPosFrom(e) {
  const rect = xRailEl.getBoundingClientRect();
  const src  = e.touches ? e.touches[0] : e;
  return Math.max(0, Math.min(NX - 1, (src.clientX - rect.left) / rect.width * (NX - 1)));
}

function yIdxFrom(e) {
  const rect = yRailEl.getBoundingClientRect();
  const src  = e.touches ? e.touches[0] : e;
  // frac=0 → top (yi=N-1), frac=1 → bottom (yi=0)
  return Math.max(0, Math.min(NY - 1, NY - 1 - Math.floor((src.clientY - rect.top) / rect.height * NY)));
}

// ── X axis interactions ──────────────────────────────────────────────────────
let dX = false;
xRailEl.addEventListener("mousedown",  (e) => { e.preventDefault(); dX = true; setX(xPosFrom(e)); });
xRailEl.addEventListener("touchstart", (e) => setX(xPosFrom(e)), { passive: true });
xRailEl.addEventListener("touchmove",  (e) => { e.preventDefault(); setX(xPosFrom(e)); }, { passive: false });
xDotEl .addEventListener("touchmove",  (e) => { e.preventDefault(); setX(xPosFrom(e)); }, { passive: false });
xRailEl.addEventListener("touchend",   () => snapX(), { passive: true });
xDotEl .addEventListener("touchend",   () => snapX(), { passive: true });

// ── Y axis interactions ──────────────────────────────────────────────────────
let dY = false;
yRailEl.addEventListener("mousedown",  (e) => { e.preventDefault(); dY = true; setY(yIdxFrom(e)); });
yRailEl.addEventListener("touchstart", (e) => setY(yIdxFrom(e)), { passive: true });
yRailEl.addEventListener("touchmove",  (e) => { e.preventDefault(); setY(yIdxFrom(e)); }, { passive: false });
yDotEl .addEventListener("touchmove",  (e) => { e.preventDefault(); setY(yIdxFrom(e)); }, { passive: false });

// ── Global mouse drag ────────────────────────────────────────────────────────
document.addEventListener("mousemove", (e) => {
  if (dX) setX(xPosFrom(e));
  if (dY) setY(yIdxFrom(e));
});
document.addEventListener("mouseup", () => {
  if (dX) snapX();
  dX = false; dY = false;
});

// ── Submit ───────────────────────────────────────────────────────────────────
confirmEl.addEventListener("click", async () => {
  confirmEl.disabled = true;
  try {
    const resp = await fetch(`/api/recall/${PHASE}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ x: Math.round(xPos), y: yIdx, response_time_ms: Date.now() - startMs }),
    });
    const data = await resp.json();
    if (data.next_url) window.location.href = data.next_url;
  } catch (_) {
    confirmEl.disabled = false;
    alert("网络异常，请重试");
  }
});

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  const resp = await fetch("/api/thumbs");
  thumbMap = await resp.json();
  // Preload all thumbnails so crossfade is instant
  Object.values(thumbMap).forEach(src => { const img = new Image(); img.src = src; });
  placeXDot(xPos);
  placeYDot(yIdx);
  updateImage(xPos);
}

init().catch(console.error);
