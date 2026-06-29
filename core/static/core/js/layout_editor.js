(function () {
  const panel = document.getElementById("tab-layout");
  if (!panel) return;

  const layoutUrl = panel.dataset.layoutUrl;
  const rowsInput = document.getElementById("le-rows");
  const colsInput = document.getElementById("le-cols");
  const gridEl = document.getElementById("le-grid");
  const summaryEl = document.getElementById("le-summary");
  const paletteEl = document.getElementById("le-palette");
  const saveBtn = document.getElementById("le-save");
  const applyBtn = document.getElementById("le-apply-grid");
  const clearBtn = document.getElementById("le-clear");
  const dirtyHint = document.getElementById("le-dirty-hint");
  const noCategoriesEl = document.getElementById("le-no-categories");

  if (!layoutUrl || !gridEl) return;

  const CAT_COLORS = {
    P: "var(--amber)",
    S: "var(--green)",
    L: "#7C3AED",
    C: "var(--rose)",
  };

  let categories = [];
  let activeCategoryId = null;
  let eraserActive = false;
  let grid = [];
  let dirty = false;

  function getCookie(name) {
    const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
    return match ? decodeURIComponent(match[2]) : "";
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Request failed.");
    }
    return data;
  }

  function setDirty(value) {
    dirty = value;
    if (dirtyHint) {
      dirtyHint.style.display = dirty ? "" : "none";
    }
  }

  function clampGridSize() {
    let rows = parseInt(rowsInput.value, 10) || 4;
    let cols = parseInt(colsInput.value, 10) || 10;
    rows = Math.max(1, Math.min(12, rows));
    cols = Math.max(1, Math.min(20, cols));
    rowsInput.value = String(rows);
    colsInput.value = String(cols);
    return { rows, cols };
  }

  function resizeGrid(rows, cols, oldGrid) {
    const next = [];
    for (let r = 0; r < rows; r += 1) {
      next[r] = [];
      for (let c = 0; c < cols; c += 1) {
        if (oldGrid[r] && oldGrid[r][c]) {
          next[r][c] = { ...oldGrid[r][c] };
        } else {
          next[r][c] = { categoryId: null, sunbedId: null, label: "" };
        }
      }
    }
    return next;
  }

  function categoryById(id) {
    return categories.find((cat) => cat.id === id);
  }

  function updateSummary() {
    if (!summaryEl) return;
    const counts = {};
    let totalCells = 0;
    let empty = 0;
    for (let r = 0; r < grid.length; r += 1) {
      for (let c = 0; c < grid[r].length; c += 1) {
        totalCells += 1;
        const cell = grid[r][c];
        if (!cell.categoryId) {
          empty += 1;
          continue;
        }
        const cat = categoryById(cell.categoryId);
        const key = cat ? cat.name : "?";
        counts[key] = (counts[key] || 0) + 1;
      }
    }
    let html = "";
    categories.forEach((cat) => {
      if (!counts[cat.name]) return;
      const color = CAT_COLORS[cat.prefix] || "var(--text-3)";
      html += `<div class="le-summary__item"><span class="le-summary__dot" style="background:${color}"></span>${cat.name}: ${counts[cat.name]}</div>`;
    });
    html += `<div class="le-summary__item le-summary__item--muted">Empty: ${empty} · Total cells: ${totalCells}</div>`;
    summaryEl.innerHTML = html;
  }

  function drawGrid() {
    let html = "";
    for (let r = 0; r < grid.length; r += 1) {
      html += '<div class="le-row">';
      for (let c = 0; c < grid[r].length; c += 1) {
        const cell = grid[r][c];
        const cat = cell.categoryId ? categoryById(cell.categoryId) : null;
        const prefix = cat ? cat.prefix : "";
        const cls = prefix ? `le-cell le-cell--${prefix}` : "le-cell";
        const label = cell.label || (prefix || "");
        html += `<button type="button" class="${cls}" data-row="${r}" data-col="${c}" aria-label="Cell ${r + 1}, ${c + 1}">${label}</button>`;
      }
      html += "</div>";
    }
    gridEl.innerHTML = html;
    updateSummary();
  }

  function selectBrush(categoryId, eraser) {
    eraserActive = eraser;
    activeCategoryId = eraser ? null : categoryId;
    paletteEl.querySelectorAll(".le-brush").forEach((btn) => {
      const isEraser = btn.dataset.eraser === "true";
      const isActive = eraser ? isEraser : Number(btn.dataset.categoryId) === categoryId;
      btn.classList.toggle("le-brush--active", isActive);
    });
  }

  function buildPalette() {
    if (!categories.length) {
      if (noCategoriesEl) noCategoriesEl.style.display = "";
      paletteEl.innerHTML = "";
      return;
    }
    if (noCategoriesEl) noCategoriesEl.style.display = "none";
    let html = "";
    categories.forEach((cat, index) => {
      const color = CAT_COLORS[cat.prefix] || "var(--text-3)";
      html += `<button type="button" class="le-brush${index === 0 ? " le-brush--active" : ""}" data-category-id="${cat.id}"><span class="le-brush__dot" style="background:${color}"></span>${cat.name}</button>`;
    });
    html += '<span class="le-palette__sep" aria-hidden="true"></span>';
    html += '<button type="button" class="le-brush" data-eraser="true"><span class="le-brush__dot le-brush__dot--eraser"></span>Eraser</button>';
    paletteEl.innerHTML = html;
    activeCategoryId = categories[0].id;
    eraserActive = false;
    paletteEl.querySelectorAll(".le-brush").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.dataset.eraser === "true") {
          selectBrush(null, true);
        } else {
          selectBrush(Number(btn.dataset.categoryId), false);
        }
      });
    });
  }

  function paintCell(row, col) {
    const cell = grid[row][col];
    if (eraserActive) {
      if (!cell.categoryId) return;
      cell.categoryId = null;
      cell.sunbedId = null;
      cell.label = "";
    } else if (activeCategoryId) {
      if (cell.categoryId === activeCategoryId) {
        cell.categoryId = null;
        cell.sunbedId = null;
        cell.label = "";
      } else {
        cell.categoryId = activeCategoryId;
        const cat = categoryById(activeCategoryId);
        cell.label = cat ? cat.prefix : "";
      }
    }
    setDirty(true);
    drawGrid();
  }

  function cellsFromGrid() {
    const cells = [];
    for (let r = 0; r < grid.length; r += 1) {
      for (let c = 0; c < grid[r].length; c += 1) {
        const cell = grid[r][c];
        if (!cell.categoryId) continue;
        const entry = {
          row: r,
          col: c,
          category_id: cell.categoryId,
        };
        if (cell.sunbedId) {
          entry.sunbed_id = cell.sunbedId;
        }
        cells.push(entry);
      }
    }
    return cells;
  }

  function loadFromPayload(data) {
    categories = data.categories || [];
    buildPalette();
    const { rows, cols } = { rows: data.rows, cols: data.cols };
    rowsInput.value = String(rows);
    colsInput.value = String(cols);
    grid = resizeGrid(rows, cols, []);
    (data.cells || []).forEach((row, r) => {
      row.forEach((cell, c) => {
        if (!cell) return;
        grid[r][c] = {
          categoryId: cell.category_id,
          sunbedId: cell.sunbed_id,
          label: cell.label || "",
        };
      });
    });
    setDirty(false);
    drawGrid();
  }

  async function loadLayout() {
    const data = await fetchJson(layoutUrl);
    loadFromPayload(data);
  }

  function applyGridSize() {
    const { rows, cols } = clampGridSize();
    grid = resizeGrid(rows, cols, grid);
    setDirty(true);
    drawGrid();
  }

  function clearGrid() {
    if (!window.confirm("Clear all cells on the canvas?")) return;
    for (let r = 0; r < grid.length; r += 1) {
      for (let c = 0; c < grid[r].length; c += 1) {
        grid[r][c] = { categoryId: null, sunbedId: null, label: "" };
      }
    }
    setDirty(true);
    drawGrid();
  }

  async function saveLayout() {
    const { rows, cols } = clampGridSize();
    saveBtn.disabled = true;
    try {
      const data = await fetchJson(layoutUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify({
          rows,
          cols,
          cells: cellsFromGrid(),
        }),
      });
      loadFromPayload(data.layout);
      alert("Layout saved.");
    } catch (error) {
      console.error(error);
      alert(error.message || "Could not save layout.");
    } finally {
      saveBtn.disabled = false;
    }
  }

  gridEl.addEventListener("click", (event) => {
    const cellBtn = event.target.closest(".le-cell");
    if (!cellBtn || !gridEl.contains(cellBtn)) return;
    paintCell(Number(cellBtn.dataset.row), Number(cellBtn.dataset.col));
  });

  if (applyBtn) applyBtn.addEventListener("click", applyGridSize);
  if (clearBtn) clearBtn.addEventListener("click", clearGrid);
  if (saveBtn) saveBtn.addEventListener("click", saveLayout);

  if (rowsInput) {
    rowsInput.addEventListener("change", applyGridSize);
  }
  if (colsInput) {
    colsInput.addEventListener("change", applyGridSize);
  }

  loadLayout().catch((error) => {
    console.error(error);
    alert(error.message || "Could not load layout.");
  });
})();
