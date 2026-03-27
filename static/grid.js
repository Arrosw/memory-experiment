const phaseData = document.getElementById("phase-data");
const PHASE     = phaseData.dataset.phase;
const X_ORDER   = JSON.parse(phaseData.dataset.xOrder);
const Y_ORDER   = JSON.parse(phaseData.dataset.yOrder);
const AVAIL_MATS = JSON.parse(phaseData.dataset.availMats);
const AVAIL_CATS = JSON.parse(phaseData.dataset.availCats);
const NX = X_ORDER.length;
const NY = Y_ORDER.length;

const yRailEl   = document.getElementById("y-rail");
const xRailEl   = document.getElementById("x-rail");
const yDotEl    = document.getElementById("y-dot");
const xDotEl    = document.getElementById("x-dot");
const previewEl = document.getElementById("preview-img");
const confirmEl = document.getElementById("confirm-btn");

let thumbMap = {};
let xIdx = 0;
let yIdx = 0;
const startMs = Date.now();

function getKey(xi, yi) {
  return AVAIL_CATS[Y_ORDER[yi]] + '_' + AVAIL_MATS[X_ORDER[xi]];
}

// Place X dot as % of x-rail width; transform: translateX(-50%) handles centering
function placeXDot(xi) {
  xDotEl.style.left = ((xi + 0.5) / NX * 100) + "%";
}

// Place Y dot as % of y-rail height; yi=0 → bottom, yi=N-1 → top
function placeYDot(yi) {
  yDotEl.style.top = ((NY - 1 - yi + 0.5) / NY * 100) + "%";
}

function updateImage() {
  const key = getKey(xIdx, yIdx);
  if (thumbMap[key]) {
    previewEl.src = thumbMap[key];
    previewEl.style.display = "block";
  }
  confirmEl.disabled = false;
}

function setX(xi) {
  xIdx = Math.max(0, Math.min(NX - 1, xi));
  placeXDot(xIdx);
  updateImage();
}

function setY(yi) {
  yIdx = Math.max(0, Math.min(NY - 1, yi));
  placeYDot(yIdx);
  updateImage();
}

function xIdxFrom(e) {
  const rect = xRailEl.getBoundingClientRect();
  const src  = e.touches ? e.touches[0] : e;
  return Math.max(0, Math.min(NX - 1, Math.floor((src.clientX - rect.left) / rect.width * NX)));
}

function yIdxFrom(e) {
  const rect = yRailEl.getBoundingClientRect();
  const src  = e.touches ? e.touches[0] : e;
  // frac=0 → top (yi=N-1), frac=1 → bottom (yi=0)
  return Math.max(0, Math.min(NY - 1, NY - 1 - Math.floor((src.clientY - rect.top) / rect.height * NY)));
}

// ── X axis interactions ──────────────────────────────────────────────────────
let dX = false;
xRailEl.addEventListener("mousedown",  (e) => { dX = true; setX(xIdxFrom(e)); });
xRailEl.addEventListener("touchstart", (e) => setX(xIdxFrom(e)), { passive: true });
xRailEl.addEventListener("touchmove",  (e) => { e.preventDefault(); setX(xIdxFrom(e)); }, { passive: false });
xDotEl .addEventListener("touchmove",  (e) => { e.preventDefault(); setX(xIdxFrom(e)); }, { passive: false });

// ── Y axis interactions ──────────────────────────────────────────────────────
let dY = false;
yRailEl.addEventListener("mousedown",  (e) => { dY = true; setY(yIdxFrom(e)); });
yRailEl.addEventListener("touchstart", (e) => setY(yIdxFrom(e)), { passive: true });
yRailEl.addEventListener("touchmove",  (e) => { e.preventDefault(); setY(yIdxFrom(e)); }, { passive: false });
yDotEl .addEventListener("touchmove",  (e) => { e.preventDefault(); setY(yIdxFrom(e)); }, { passive: false });

// ── Global mouse drag ────────────────────────────────────────────────────────
document.addEventListener("mousemove", (e) => {
  if (dX) setX(xIdxFrom(e));
  if (dY) setY(yIdxFrom(e));
});
document.addEventListener("mouseup", () => { dX = false; dY = false; });

// ── Submit ───────────────────────────────────────────────────────────────────
confirmEl.addEventListener("click", async () => {
  confirmEl.disabled = true;
  try {
    const resp = await fetch(`/api/recall/${PHASE}`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ x: xIdx, y: yIdx, response_time_ms: Date.now() - startMs }),
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
  placeXDot(xIdx);
  placeYDot(yIdx);
  updateImage();
}

init().catch(console.error);
