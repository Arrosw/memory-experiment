const CATEGORIES = ["bowl", "cup", "plate", "vase", "box", "pitcher"];
const MATERIALS  = ["wood", "plastic", "metal", "glass", "ceramic", "stone"];
const N = 6;

const phaseData    = document.getElementById("phase-data");
const PHASE        = phaseData.dataset.phase;
const X_ORDER      = JSON.parse(phaseData.dataset.xOrder);  // shuffled MATERIALS indices
const Y_ORDER      = JSON.parse(phaseData.dataset.yOrder);  // shuffled CATEGORIES indices

const canvasEl     = document.getElementById("grid-canvas");
const dotEl        = document.getElementById("grid-dot");
const previewImgEl = document.getElementById("preview-img");
const previewHint  = document.getElementById("preview-hint");
const confirmBtnEl = document.getElementById("confirm-btn");

let thumbMap = {};
let xIdx = -1;
let yIdx = -1;
const startMs = Date.now();

function getKey(xi, yi) {
  return `${CATEGORIES[Y_ORDER[yi]]}_${MATERIALS[X_ORDER[xi]]}`;
}

function placeDot(xi, yi) {
  const w = canvasEl.offsetWidth;
  const h = canvasEl.offsetHeight;
  dotEl.style.left = ((xi + 0.5) / N * w) + "px";
  dotEl.style.top  = ((yi + 0.5) / N * h) + "px";
  dotEl.style.display = "block";
}

function selectPos(xi, yi) {
  xi = Math.max(0, Math.min(N - 1, xi));
  yi = Math.max(0, Math.min(N - 1, yi));
  xIdx = xi;
  yIdx = yi;
  placeDot(xi, yi);
  const key = getKey(xi, yi);
  if (thumbMap[key]) {
    previewImgEl.src = thumbMap[key];
    previewImgEl.style.display = "block";
    previewHint.style.display = "none";
  }
  confirmBtnEl.disabled = false;
}

function posFromEvent(e) {
  const rect = canvasEl.getBoundingClientRect();
  const src  = e.touches ? e.touches[0] : e;
  const xi   = Math.floor((src.clientX - rect.left)  / rect.width  * N);
  const yi   = Math.floor((src.clientY - rect.top)   / rect.height * N);
  return [xi, yi];
}

// Mouse interaction
let dragging = false;
canvasEl.addEventListener("mousedown", (e) => {
  dragging = true;
  selectPos(...posFromEvent(e));
});
document.addEventListener("mouseup", () => { dragging = false; });
document.addEventListener("mousemove", (e) => {
  if (!dragging) return;
  selectPos(...posFromEvent(e));
});

// Touch interaction
canvasEl.addEventListener("touchstart", (e) => {
  selectPos(...posFromEvent(e));
}, { passive: true });
canvasEl.addEventListener("touchmove", (e) => {
  e.preventDefault();
  selectPos(...posFromEvent(e));
}, { passive: false });

// Submit
confirmBtnEl.addEventListener("click", async () => {
  if (xIdx < 0 || yIdx < 0) return;
  confirmBtnEl.disabled = true;
  const resp = await fetch(`/api/recall/${PHASE}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ x: xIdx, y: yIdx, response_time_ms: Date.now() - startMs }),
  });
  const data = await resp.json();
  if (data.next_url) window.location.href = data.next_url;
});

async function loadThumbs() {
  const resp = await fetch("/api/thumbs");
  thumbMap = await resp.json();
}

loadThumbs().catch((err) => console.error("Failed to load thumbs", err));
