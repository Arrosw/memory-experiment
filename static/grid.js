const CATEGORIES = ["bowl", "cup", "plate", "vase", "box", "pitcher"];
const MATERIALS = ["wood", "plastic", "metal", "glass", "ceramic", "stone"];
const COLS = 6;
const ROWS = 6;

const PHASE = document.getElementById("phase-data").dataset.phase;
const gridEl = document.getElementById("grid");
const previewImgEl = document.getElementById("preview-img");
const confirmBtnEl = document.getElementById("confirm-btn");

let thumbMap = {};
let currentCol = -1;
let currentRow = -1;
const startMs = Date.now();

function keyForCell(col, row) {
  return `${CATEGORIES[row]}_${MATERIALS[col]}`;
}

function preloadImages(urlMap) {
  return Promise.all(
    Object.values(urlMap).map(
      (url) =>
        new Promise((resolve) => {
          const img = new Image();
          img.onload = resolve;
          img.onerror = resolve;
          img.src = url;
        }),
    ),
  );
}

function selectCell(col, row) {
  currentCol = col;
  currentRow = row;

  document.querySelectorAll(".grid-cell").forEach((cell) => {
    cell.classList.remove("active");
  });

  const selectedIndex = row * COLS + col;
  const selectedCell = gridEl.children[selectedIndex];
  if (selectedCell) {
    selectedCell.classList.add("active");
  }

  previewImgEl.src = thumbMap[keyForCell(col, row)] || "";
  previewImgEl.style.display = "block";
  confirmBtnEl.disabled = false;
}

function renderGrid() {
  gridEl.replaceChildren();

  for (let row = 0; row < ROWS; row += 1) {
    for (let col = 0; col < COLS; col += 1) {
      const cell = document.createElement("div");
      cell.className = "grid-cell";
      cell.style.backgroundImage = `url("${thumbMap[keyForCell(col, row)] || ""}")`;
      cell.dataset.col = String(col);
      cell.dataset.row = String(row);

      const handleSelect = () => selectCell(col, row);
      cell.addEventListener("mouseenter", handleSelect);
      cell.addEventListener("touchstart", handleSelect, { passive: true });
      cell.addEventListener("click", handleSelect);

      gridEl.appendChild(cell);
    }
  }
}

async function loadGrid() {
  const response = await fetch("/api/thumbs");
  thumbMap = await response.json();
  await preloadImages(thumbMap);
  renderGrid();
}

confirmBtnEl.addEventListener("click", async () => {
  if (currentCol < 0 || currentRow < 0) {
    return;
  }

  const response = await fetch(`/api/recall/${PHASE}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      col: currentCol,
      row: currentRow,
      response_time_ms: Date.now() - startMs,
    }),
  });

  const data = await response.json();
  if (data.next_url) {
    window.location.href = data.next_url;
  }
});

loadGrid().catch((error) => {
  console.error("Failed to load recall grid", error);
});
