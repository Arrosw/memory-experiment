# Memory Experiment — Implementation Plan
> v2 | 2026-03-26 | Demo-first, Apple aesthetic, remote GPU

## 0. Core Hypothesis

> People actively forget surface material textures but retain core category semantics.

Validate by comparing **category accuracy** vs **material accuracy** across time delays (immediate / ~1 week / ~1 month).

---

## 1. Architecture Overview

```
memory-experiment/
├── CLAUDE.md                  # 开发规范
├── app.py                     # Flask 主应用（单文件，<400行）
├── config.py                  # 配置常量
├── generate_images.py         # 远程 GPU 图像生成脚本
├── templates/
│   ├── base.html              # 基础模板（Apple 样式 + 共用 CSS）
│   ├── index.html             # 注册/返回页
│   ├── study.html             # 学习阶段（展示图像）
│   ├── recall.html            # 回忆阶段（2D 网格）
│   ├── done.html              # 阶段完成提示
│   └── admin.html             # 管理员统计
├── static/
│   ├── style.css              # Apple 风格样式表
│   ├── grid.js                # 2D 网格交互
│   └── images/                # 图像库（后续填充）
│       └── {category}/{material}/
│           ├── study.png      # 学习用（1024×1024）
│           ├── recall.png     # 回忆展示用
│           └── thumb.jpg      # 缩略图（256×256）
├── data/
│   └── experiment.db          # SQLite
└── requirements.txt
```

**极简原则**：单文件 Flask app，无 ORM，原生 SQL，Jinja2 模板，vanilla JS/CSS。

---

## 2. Demo-First Strategy

### Phase 1: 基础框架 Demo（无真实图像）
- 使用 **占位图** 替代真实图像（纯色块 + 文字标签，如 "wood bowl"）
- 占位图通过 Flask 路由动态生成（Pillow 绘制），无需预存
- 完整实现所有流程：注册 → 学习 → 即时回忆 → 延迟回忆 → 统计
- 目标：可运行的端到端 demo，验证交互逻辑

```python
# 占位图生成（Phase 1 临时方案）
@app.route('/placeholder/<category>/<material>')
def placeholder(category, material):
    """生成带文字标签的纯色占位图"""
    from PIL import Image, ImageDraw, ImageFont
    import io
    # 每种材质一个固定色（视觉区分）
    MATERIAL_COLORS = {
        'wood': '#D2A679', 'plastic': '#4FC3F7', 'metal': '#B0BEC5',
        'glass': '#E0F7FA', 'ceramic': '#FFCCBC', 'stone': '#9E9E9E',
    }
    img = Image.new('RGB', (512, 512), MATERIAL_COLORS.get(material, '#EEE'))
    draw = ImageDraw.Draw(img)
    text = f"{material}\n{category}"
    draw.text((256, 256), text, fill='#333', anchor='mm',
              font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 48))
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')
```

### Phase 2: 接入远程 GPU 生成真实图像
### Phase 3: 人工筛选 → 替换占位图 → 正式实验

---

## 3. Image Generation (Remote 3090)

### 3.1 Model Choice: FLUX.1-dev

| 模型 | VRAM | 材质还原 | 决策 |
|------|------|----------|------|
| SDXL + RealVisXL | 10-12GB | 好 | fallback |
| FLUX.1-dev | 20-22GB | 最好 | **主选** |

RTX 3090 24GB → FP16 可运行 FLUX.1-dev。

### 3.2 Remote Execution Strategy

**方案：SSH + 脚本执行**（最简单，无需搭 API 服务）

```bash
# 本地触发远程生成
ssh gpu-server "cd ~/memory-experiment && python generate_images.py"
# 生成完毕后拉回本地
rsync -avz gpu-server:~/memory-experiment/output/ ./static/images/
```

`generate_images.py` 在 GPU 服务器上独立运行，不依赖 Flask。

### 3.3 Image Matrix

| 维度 | 选项 (6) |
|------|----------|
| **Category** | bowl, cup, plate, vase, box, pitcher |
| **Material** | wood, plastic, metal, glass, ceramic, stone |

- 组合数：6 × 6 = 36
- 每组生成 5 张（seed: 42, 137, 256, 512, 999），人工筛选保留 2 张（study + recall）
- 总生成：36 × 5 = 180 张

### 3.4 Prompt Template

```python
PROMPT_TEMPLATE = (
    "a single {material} {category}, studio product photography, "
    "white background, soft diffuse lighting, sharp focus, "
    "visible {material} texture, high detail, 8k, "
    "photorealistic, centered, isolated object"
)
# FLUX.1-dev 不支持 negative_prompt（flow-matching 架构）
```

### 3.5 Generation Parameters

```python
from diffusers import FluxPipeline
import torch

pipe = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-dev",
    torch_dtype=torch.float16,
)
pipe.enable_model_cpu_offload()

# 核心参数
PARAMS = {
    'width': 1024, 'height': 1024,
    'num_inference_steps': 28,    # FLUX.1-dev 官方默认
    'guidance_scale': 3.5,        # FLUX 推荐值
    'num_images_per_prompt': 1,   # 循环 5 次（显存稳定）
}
```

### 3.6 generate_images.py 架构

```python
CATEGORIES = ['bowl', 'cup', 'plate', 'vase', 'box', 'pitcher']
MATERIALS  = ['wood', 'plastic', 'metal', 'glass', 'ceramic', 'stone']
SEEDS = [42, 137, 256, 512, 999]

def main():
    pipe = load_model()
    for cat in CATEGORIES:
        for mat in MATERIALS:
            out_dir = Path(f"output/{cat}/{mat}")
            out_dir.mkdir(parents=True, exist_ok=True)
            if len(list(out_dir.glob("*.png"))) >= 5:
                continue  # 断点续传
            for i, seed in enumerate(SEEDS):
                img = pipe(
                    prompt=PROMPT_TEMPLATE.format(material=mat, category=cat),
                    generator=torch.Generator().manual_seed(seed),
                    **PARAMS
                ).images[0]
                img.save(out_dir / f"gen_{i+1}.png")
    print("Done. Run manual review, then rename best 2 to study.png / recall.png")

# CLI
# python generate_images.py
# python generate_images.py --categories bowl,cup --materials wood,metal
# python generate_images.py --dry-run  # 只打印 prompt
```

### 3.7 Post-generation Pipeline

```bash
# 1. 远程生成
ssh gpu "cd ~/memory && python generate_images.py"

# 2. 拉回本地审查
rsync -avz gpu:~/memory/output/ ./review/

# 3. 人工筛选（简单图片浏览器看5张选2张）
# 重命名为 study.png, recall.png

# 4. 生成缩略图
python -c "
from PIL import Image; from pathlib import Path
for p in Path('static/images').rglob('study.png'):
    Image.open(p).resize((256,256), Image.LANCZOS).save(
        p.parent / 'thumb.jpg', 'JPEG', quality=90)
for p in Path('static/images').rglob('recall.png'):
    Image.open(p).resize((256,256), Image.LANCZOS).save(
        p.parent / 'recall_thumb.jpg', 'JPEG', quality=90)
"

# 5. 部署
cp -r ./review/ ./static/images/
```

---

## 4. Database Schema (SQLite)

```sql
CREATE TABLE participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,       -- "Tiger_42" 格式
    nickname TEXT,                   -- 用户输入的昵称
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id INTEGER NOT NULL REFERENCES participants(id),
    category TEXT NOT NULL,          -- 正确类别
    material TEXT NOT NULL,          -- 正确材质
    trial_order INTEGER NOT NULL,    -- 1
    study_started_at TIMESTAMP
);

CREATE TABLE responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id INTEGER NOT NULL REFERENCES trials(id),
    phase TEXT NOT NULL CHECK(phase IN ('immediate','week','month')),
    responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resp_category TEXT,              -- 选择的类别
    resp_material TEXT,              -- 选择的材质
    resp_col INTEGER,                -- 原始列索引 0-5
    resp_row INTEGER,                -- 原始行索引 0-5
    category_correct INTEGER CHECK(category_correct IN (0,1)),
    material_correct INTEGER CHECK(material_correct IN (0,1)),
    response_time_ms INTEGER         -- 从页面加载到确认
);

CREATE INDEX idx_part_code ON participants(code);
CREATE INDEX idx_trials_part ON trials(participant_id);
CREATE INDEX idx_resp_trial ON responses(trial_id);
```

**简化决策**：去掉独立的 images 表。category + material 直接存在 trials 中，图像路径通过约定推导（`static/images/{cat}/{mat}/study.png`）。减少一层 JOIN。

---

## 5. Flask Routes

```python
# --- 受试者流程 ---
GET  /                        # 欢迎页：输入 code 返回 or 创建新用户
POST /register                # 创建 participant + 分配 1 个 trial → 跳转 /study
GET  /study                   # 学习阶段：展示当前 trial 图像，5s 倒计时
POST /api/study-start         # JS 调用：图像加载完成时记录 study_started_at
POST /api/study-done          # JS 调用：5s 结束，返回 next_url
GET  /recall/<phase>          # 回忆界面：2D 网格
POST /api/recall/<phase>      # JS 提交选择，返回 next_url
GET  /done                    # 阶段完成提示（不剧透答案）
GET  /return/<code>           # 凭 code 返回，自动判断应进入哪个 phase

# --- 管理员 ---
GET  /admin                   # 统计面板（HTTP Basic Auth）
GET  /admin/export.csv        # 导出原始数据

# --- API ---
GET  /api/thumbs              # 返回 36 个格子的缩略图 URL 映射 (JSON)
GET  /placeholder/<cat>/<mat> # Phase 1: 动态生成占位图
```

### Route Logic Highlights

```python
# Trial 分配：覆盖平衡策略
def assign_trials(participant_id, n=1):
    """优先选被分配最少的组合"""
    counts = db.execute(
        "SELECT category, material, COUNT(*) c FROM trials GROUP BY category, material"
    ).fetchall()
    count_map = {(r[0], r[1]): r[2] for r in counts}
    all_combos = [(c, m) for c in CATEGORIES for m in MATERIALS]
    all_combos.sort(key=lambda x: count_map.get(x, 0))
    selected = all_combos[:n]
    random.shuffle(selected)  # 消除顺序效应
    for order, (cat, mat) in enumerate(selected, 1):
        db.execute(
            "INSERT INTO trials (participant_id, category, material, trial_order) VALUES (?,?,?,?)",
            (participant_id, cat, mat, order)
        )
    db.commit()

# Phase 判断
def get_current_phase(participant_id):
    """返回 (trial_id, phase) 或 None"""
    trials = db.execute(
        "SELECT * FROM trials WHERE participant_id=? ORDER BY trial_order", (participant_id,)
    ).fetchall()
    for trial in trials:
        done_phases = {r['phase'] for r in db.execute(
            "SELECT phase FROM responses WHERE trial_id=?", (trial['id'],)
        )}
        days = (datetime.utcnow() - trial['study_started_at']).days if trial['study_started_at'] else 0
        if 'immediate' not in done_phases:
            return trial['id'], 'immediate'
        if 5 <= days <= 9 and 'week' not in done_phases:
            return trial['id'], 'week'
        if 25 <= days <= 40 and 'month' not in done_phases:
            return trial['id'], 'month'
    return None, None
```

### Session Management

```python
# Flask client-side session 足够（仅存 participant_id, current_trial_index, phase）
# 无敏感信息泄露风险：study_image 路径可从 trial 推导，无需隐藏
app.secret_key = os.urandom(24).hex()
```

**简化决策**：不用 Flask-Session filesystem backend。client-side cookie session 足够，因为 session 只存 participant_id 和进度索引，不含敏感信息。路径从 trial 的 category/material 推导，无需隐藏。

---

## 6. UI Design — Apple Aesthetic

### 6.1 Design Principles

- **极简**：每个页面只做一件事
- **大量留白**：内容区最大宽度 480px 居中
- **无边框**：用微阴影区分层级，不用 border
- **圆角**：卡片 12px，按钮 pill 形（9999px）
- **动效克制**：仅 hover/active 有 150ms 过渡

### 6.2 CSS Variables (base.html `<style>`)

```css
:root {
    /* Colors */
    --blue: #007AFF;
    --blue-hover: #0071E3;
    --bg: #F2F2F7;
    --card: #FFFFFF;
    --text-primary: #000000;
    --text-secondary: rgba(60, 60, 67, 0.6);
    --text-tertiary: rgba(60, 60, 67, 0.3);
    --separator: rgba(60, 60, 67, 0.12);
    --gray-5: #E5E5EA;
    --green: #34C759;
    --red: #FF3B30;

    /* Typography */
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Display",
            "Helvetica Neue", Arial, sans-serif;

    /* Spacing (4pt grid) */
    --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px;
    --s5: 20px; --s6: 24px; --s8: 32px; --s10: 40px;

    /* Radii */
    --r-sm: 8px; --r-md: 12px; --r-lg: 16px; --r-pill: 9999px;

    /* Shadows */
    --shadow-sm: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
    --shadow-md: 0 4px 14px rgba(0,0,0,0.08), 0 2px 6px rgba(0,0,0,0.04);

    /* Motion */
    --ease: cubic-bezier(0.25, 0.1, 0.25, 1.0);
    --dur-fast: 150ms;
    --dur-normal: 250ms;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: var(--font);
    background: var(--bg);
    color: var(--text-primary);
    -webkit-font-smoothing: antialiased;
    min-height: 100vh;
    display: flex; justify-content: center; align-items: flex-start;
    padding: var(--s8) var(--s4);
}
.container { max-width: 480px; width: 100%; }
.card {
    background: var(--card);
    border-radius: var(--r-md);
    padding: var(--s6);
    box-shadow: var(--shadow-sm);
    margin-bottom: var(--s4);
}
h1 { font-size: 28px; font-weight: 700; letter-spacing: 0.36px; margin-bottom: var(--s4); }
h2 { font-size: 22px; font-weight: 700; letter-spacing: 0.35px; margin-bottom: var(--s3); }
p { font-size: 17px; line-height: 1.5; color: var(--text-secondary); margin-bottom: var(--s4); }
.btn {
    display: inline-block; padding: 12px 32px;
    background: var(--blue); color: #fff; border: none;
    border-radius: var(--r-pill); font-size: 17px; font-weight: 400;
    cursor: pointer; text-decoration: none; text-align: center;
    transition: background var(--dur-fast) var(--ease),
                transform var(--dur-fast) var(--ease);
}
.btn:hover { background: var(--blue-hover); }
.btn:active { transform: scale(0.97); }
.btn:disabled { background: var(--gray-5); color: var(--text-tertiary); cursor: not-allowed; }
.input {
    width: 100%; padding: 12px 14px; font-size: 17px;
    border: 1px solid var(--gray-5); border-radius: var(--r-sm);
    outline: none; transition: border-color var(--dur-fast) var(--ease);
}
.input:focus { border-color: var(--blue); box-shadow: 0 0 0 3px rgba(0,122,255,0.15); }
.text-center { text-align: center; }
.text-secondary { color: var(--text-secondary); }
.mt-4 { margin-top: var(--s4); }
.mt-6 { margin-top: var(--s6); }
```

### 6.3 Page Designs

#### Welcome Page (index.html)
```
┌─────────────────────────────────┐
│                                 │
│        Memory Research          │
│                                 │
│   欢迎参与记忆研究实验             │
│   你将看到一些物品图像，            │
│   之后凭记忆找到它们。              │
│                                 │
│   ┌─────────────────────────┐   │
│   │ 输入昵称（可选）         │   │
│   └─────────────────────────┘   │
│                                 │
│        [ 开始实验 ]              │
│                                 │
│   ─── 或 ───                    │
│                                 │
│   已有参与码？                   │
│   ┌─────────────────────────┐   │
│   │ 输入你的参与码            │   │
│   └─────────────────────────┘   │
│        [ 继续实验 ]              │
│                                 │
└─────────────────────────────────┘
```

#### Study Page (study.html)
```
┌─────────────────────────────────┐
│                                 │
│   请记住这个物品                  │
│                                 │
│   ┌─────────────────────────┐   │
│   │                         │   │
│   │      [物品图像]          │   │
│   │      512×512 显示        │   │
│   │                         │   │
│   └─────────────────────────┘   │
│                                 │
│            ◉ 4               │   │  ← 倒计时圆环动画
│                                 │
└─────────────────────────────────┘
```

倒计时用 SVG 圆环动画（Apple Watch 风格）：
```html
<svg width="64" height="64" viewBox="0 0 64 64">
  <circle cx="32" cy="32" r="28" fill="none" stroke="var(--gray-5)" stroke-width="4"/>
  <circle cx="32" cy="32" r="28" fill="none" stroke="var(--blue)" stroke-width="4"
          stroke-dasharray="176" stroke-dashoffset="0"
          style="transition: stroke-dashoffset 1s linear; transform: rotate(-90deg); transform-origin: center;">
  </circle>
  <text x="32" y="32" text-anchor="middle" dominant-baseline="central"
        font-size="24" font-weight="600" fill="var(--text-primary)">5</text>
</svg>
```

#### Recall Page (recall.html) — 核心交互
```
┌─────────────────────────────────┐
│                                 │
│   找到你记忆中的图像              │
│                                 │
│   ┌─────────────────────────┐   │
│   │ ┌──┬──┬──┬──┬──┬──┐    │   │
│   │ │  │  │  │  │  │  │    │   │
│   │ ├──┼──┼──┼──┼──┼──┤    │   │
│   │ │  │  │  │  │  │  │    │   │
│   │ ├──┼──┼──┼──┼──┼──┤    │   │
│   │ │  │  │ ●│  │  │  │    │   │  ← 高亮当前格
│   │ ├──┼──┼──┼──┼──┼──┤    │   │
│   │ │  │  │  │  │  │  │    │   │
│   │ ├──┼──┼──┼──┼──┼──┤    │   │
│   │ │  │  │  │  │  │  │    │   │
│   │ ├──┼──┼──┼──┼──┼──┤    │   │
│   │ │  │  │  │  │  │  │    │   │
│   │ └──┴──┴──┴──┴──┴──┘    │   │
│   └─────────────────────────┘   │
│                                 │
│   ┌─────────────────────────┐   │
│   │      [大图预览]          │   │  ← 跟随鼠标/触摸实时更新
│   │      256×256             │   │
│   └─────────────────────────┘   │
│                                 │
│       [ 确认选择 ]              │   │  ← 初始 disabled
│                                 │
└─────────────────────────────────┘
```

**关键 UI 决策**：
- 网格不显示任何文字标签（避免语言策略污染视觉记忆）
- 网格格子内嵌入小缩略图（48×48），而非纯空格——让用户靠视觉而非猜测
- 高亮格用 2px `var(--blue)` 描边 + 微放大 `scale(1.05)`
- 大图预览区用 `var(--shadow-md)` 浮起
- 确认按钮在用户首次交互前保持 disabled

#### Done Page (done.html)
```
┌─────────────────────────────────┐
│                                 │
│          ✓                     │
│                                 │
│   本阶段已完成                   │
│                                 │
│   你的参与码：Tiger_42           │
│   请保存此码，1周后凭码返回        │
│                                 │
│   下次回忆时间：约 3月31日        │
│                                 │
│       [ 复制参与码 ]             │
│                                 │
└─────────────────────────────────┘
```

### 6.4 Grid Interaction (grid.js)

```javascript
// 核心逻辑（recall.html 内联或独立文件）
const CATEGORIES = ['bowl','cup','plate','vase','box','pitcher'];
const MATERIALS  = ['wood','plastic','metal','glass','ceramic','stone'];
const COLS = 6, ROWS = 6;

let thumbMap = {};    // { "bowl_wood": "/path/thumb.jpg", ... }
let currentCol = -1, currentRow = -1;
let hasInteracted = false;
const startMs = Date.now();

// 1. 预加载缩略图映射
fetch('/api/thumbs').then(r => r.json()).then(data => {
    thumbMap = data;
    // 预加载所有 Image 对象
    Object.values(data).forEach(url => { new Image().src = url; });
    renderGrid();
});

// 2. 渲染网格（CSS Grid，非 Canvas——更易适配移动端）
function renderGrid() {
    const grid = document.getElementById('grid');
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = `repeat(${COLS}, 1fr)`;
    grid.style.gap = '2px';
    for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
            const cell = document.createElement('div');
            const key = `${CATEGORIES[r]}_${MATERIALS[c]}`;
            cell.className = 'grid-cell';
            cell.style.backgroundImage = `url(${thumbMap[key]})`;
            cell.style.backgroundSize = 'cover';
            cell.dataset.col = c;
            cell.dataset.row = r;
            cell.addEventListener('mouseenter', onCellHover);
            cell.addEventListener('touchstart', onCellTouch, {passive: true});
            cell.addEventListener('click', onCellClick);
            grid.appendChild(cell);
        }
    }
}

// 3. Hover → 更新预览
function onCellHover(e) {
    const col = +e.target.dataset.col;
    const row = +e.target.dataset.row;
    selectCell(col, row);
}

function onCellTouch(e) {
    const col = +e.target.dataset.col;
    const row = +e.target.dataset.row;
    selectCell(col, row);
}

function selectCell(col, row) {
    currentCol = col; currentRow = row;
    hasInteracted = true;
    document.getElementById('confirm-btn').disabled = false;
    // 高亮
    document.querySelectorAll('.grid-cell').forEach(c => c.classList.remove('active'));
    const idx = row * COLS + col;
    document.getElementById('grid').children[idx].classList.add('active');
    // 大图预览
    const key = `${CATEGORIES[row]}_${MATERIALS[col]}`;
    document.getElementById('preview-img').src = thumbMap[key] || '';
}

function onCellClick(e) {
    const col = +e.target.dataset.col;
    const row = +e.target.dataset.row;
    selectCell(col, row);
}

// 4. 提交
document.getElementById('confirm-btn').addEventListener('click', () => {
    if (!hasInteracted) return;
    const elapsed = Date.now() - startMs;
    fetch(`/api/recall/${PHASE}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            col: currentCol, row: currentRow,
            response_time_ms: elapsed
        })
    }).then(r => r.json()).then(d => { window.location = d.next_url; });
});
```

**CSS Grid vs Canvas 决策**：
- Canvas 需要手动处理 DPI 缩放、触摸坐标转换、重绘
- CSS Grid 原生响应式，触摸事件直接绑定到 DOM 元素
- 缩略图用 `background-image` 直接嵌入格子
- 性能：36 个 48×48 缩略图 ≈ 100KB，秒级加载

### 6.5 Grid Cell CSS

```css
.grid-cell {
    aspect-ratio: 1;
    border-radius: var(--r-sm);
    background-color: var(--gray-5);
    background-size: cover;
    background-position: center;
    cursor: pointer;
    transition: transform var(--dur-fast) var(--ease),
                box-shadow var(--dur-fast) var(--ease);
}
.grid-cell:hover {
    transform: scale(1.03);
    box-shadow: var(--shadow-sm);
}
.grid-cell.active {
    transform: scale(1.06);
    box-shadow: 0 0 0 2px var(--blue), var(--shadow-md);
}
```

---

## 7. Experiment Flow

### 7.1 Timeline

```
注册 → 学习 (5s) → 即时回忆 (~30s) → [等待]
                                        ↓
5-9天后 → 延迟回忆1 (~30s) → [等待]
                               ↓
25-40天后 → 延迟回忆2 (~30s) → 完成
```

### 7.2 Per-participant

- 分配 **1 个 trial**（从 36 种组合中选 1 个，覆盖平衡）
- 学习阶段看 `study.png`；回忆阶段网格展示 `recall.png`（不同图像，测类别/材质概念而非图像识别）
- 回忆阶段不显示文字标签，不反馈正确答案

### 7.3 Participant Code

格式：`{Animal}_{2位数字}`，如 `Tiger_42`、`Panda_07`

```python
ANIMALS = ['Tiger','Panda','Eagle','Whale','Fox','Bear','Wolf','Hawk','Deer','Lynx',
           'Crow','Dove','Swan','Seal','Orca','Moth','Frog','Newt','Crab','Wren']

def generate_code():
    while True:
        code = f"{random.choice(ANIMALS)}_{random.randint(10,99)}"
        if not db.execute("SELECT 1 FROM participants WHERE code=?", (code,)).fetchone():
            return code
```

---

## 8. Statistics & Analysis

### 8.1 Core Analysis

```python
def analyze():
    """验证核心假设：材质遗忘速率 > 类别遗忘速率"""
    for phase in ['immediate', 'week', 'month']:
        rows = db.execute(
            "SELECT category_correct, material_correct FROM responses WHERE phase=?",
            (phase,)
        ).fetchall()
        n = len(rows)
        if n == 0: continue
        cat_acc = sum(r[0] for r in rows) / n
        mat_acc = sum(r[1] for r in rows) / n

        # McNemar 检验
        b = sum(1 for r in rows if r[0]==1 and r[1]==0)  # 类别对，材质错
        c = sum(1 for r in rows if r[0]==0 and r[1]==1)  # 类别错，材质对
        chi2_stat = (abs(b-c)-1)**2 / (b+c) if b+c > 0 else 0
        p = 1 - scipy.stats.chi2.cdf(chi2_stat, df=1) if b+c > 0 else 1.0

        print(f"{phase}: cat={cat_acc:.1%}, mat={mat_acc:.1%}, diff={cat_acc-mat_acc:+.1%}, p={p:.4f}")
```

### 8.2 Admin Dashboard Stats

```python
@app.route('/admin')
@require_admin
def admin():
    stats = {
        'total_participants': db.execute("SELECT COUNT(*) FROM participants").fetchone()[0],
        'phase_counts': db.execute(
            "SELECT phase, COUNT(*) FROM responses GROUP BY phase"
        ).fetchall(),
        'accuracy': db.execute("""
            SELECT phase,
                   AVG(category_correct) as cat_acc,
                   AVG(material_correct) as mat_acc
            FROM responses GROUP BY phase
        """).fetchall(),
    }
    return render_template('admin.html', stats=stats)
```

### 8.3 Sample Size

- 配对设计，Cohen's d=0.5，α=0.05，power=0.80 → **34 人**
- 目标：**40-50 人**（考虑 20% 延迟流失）
- 每人 1 trial → 即时 40-50 条 / 延迟1 约 32-40 条 / 延迟2 约 24-30 条

---

## 9. Deployment

### 9.1 Development (Phase 1 Demo)

```bash
pip install flask pillow
python app.py  # localhost:5000, 占位图模式
```

### 9.2 Production

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
# 或 ngrok http 5000（零服务器快速分享）
```

SQLite 并发：启动时 `PRAGMA journal_mode=WAL`，50 并发以内安全。

---

## 10. Development Sequence

| Step | Task | 依赖 |
|------|------|------|
| **1** | `config.py` + DB 初始化 | - |
| **2** | `app.py` 基础路由 + 占位图 | Step 1 |
| **3** | `base.html` + `style.css` (Apple 样式) | - |
| **4** | `index.html` 注册/返回页 | Step 2,3 |
| **5** | `study.html` 学习阶段 + 倒计时 | Step 2,3 |
| **6** | `recall.html` + `grid.js` 2D 网格 | Step 2,3 |
| **7** | `done.html` + phase 路由逻辑 | Step 2 |
| **8** | `admin.html` 统计面板 | Step 2 |
| **9** | 端到端测试（占位图模式） | Step 1-8 |
| **10** | `generate_images.py`（远程 GPU） | 独立 |
| **11** | 替换占位图 → 正式实验 | Step 9,10 |

---

## 11. Key Design Decisions Summary

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 图像生成模型 | FLUX.1-dev | 材质还原最优，24GB 可跑 |
| 远程生成方式 | SSH + rsync | 最简单，无需搭 API |
| Web 框架 | Flask（单文件） | 极简，无学习成本 |
| 数据库 | SQLite | 零配置，50 并发足够 |
| Session | Client-side cookie | 无敏感信息，无需 server-side |
| ORM | 无（原生 SQL） | 减少依赖，schema 简单 |
| 网格实现 | CSS Grid + DOM | 比 Canvas 更易适配移动端 |
| 缩略图加载 | 预加载全部 36 张 | ~100KB，秒级完成 |
| 回忆阶段标签 | 不显示文字 | 避免语言策略污染视觉记忆 |
| 回忆阶段图像 | 与学习不同 (recall.png) | 测概念记忆而非图像识别 |
| 占位图 | Pillow 动态生成 | Demo 阶段无需真实图像 |
| images 表 | 去掉 | 路径从 category+material 推导 |
| 负向提示词 | 仅 SDXL 使用 | FLUX.1-dev 不支持 negative_prompt |
| UI 风格 | Apple HIG | 轻量、扁平、大留白、pill 按钮 |
| 最大内容宽度 | 480px | 移动端友好，桌面端居中 |

---

## 12. Requirements

```
# Web (Phase 1 Demo)
flask>=3.0
pillow>=10.0

# GPU Server (Phase 2)
torch>=2.0
diffusers>=0.28
transformers>=4.40
accelerate>=0.30
sentencepiece>=0.2

# Analysis (Phase 3)
scipy>=1.12
numpy>=1.26
```

---

## 13. Risks & Mitigations

| 风险 | 缓解 |
|------|------|
| 受试者忘记 code | 完成页提示截图保存 + 复制按钮 |
| 材质生成不可辨 | 5 张选 2 张 + prompt 强化材质描述 |
| 延迟回忆流失率高 | done 页显示下次回忆日期 |
| 移动端触摸精度 | CSS Grid 原生触摸事件，格子够大（>48px） |
| 默认提交（未移动） | 确认按钮初始 disabled |
| SQLite 并发 | WAL 模式，>100 并发迁移 PostgreSQL |
| FLUX negative_prompt | 正向 prompt 强化，SDXL fallback |
