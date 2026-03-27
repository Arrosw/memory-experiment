# Memory Experiment — 测试结果

> 测试日期：2026-03-27
> 测试方式：代码静态分析 + DB 验证（`data/experiment.db`，30名参与者，32条回应）

---

## 1. 已知问题核查

### Issue 1：`register()` 缺少 `db.commit()`
**状态：确认存在，实际低风险**

`register()` 本体无 `db.commit()`，但 `assign_trials()` 最后会调用 `db.commit()`，由于共用同一 db 连接，`INSERT INTO participants` 随之被提交。若 `assign_trials()` 在 commit 前抛异常，参与者行会丢失。当前代码路径正常时不会触发，但属于隐患。

**建议**：在 `db.execute("INSERT INTO participants ...")` 之后加一行 `db.commit()`。

---

### Issue 2：`grid.js` fetch 无 catch，网络失败时按钮卡死
**状态：确认存在**

```js
// static/grid.js L92-101
confirmEl.addEventListener("click", async () => {
  confirmEl.disabled = true;
  const resp = await fetch(`/api/recall/${PHASE}`, { ... });
  const data = await resp.json();
  if (data.next_url) window.location.href = data.next_url;
  // ← 无 try/catch，网络异常时 disabled=true 永不恢复
});
```

网络失败时 `await fetch(...)` 抛出，按钮保持 disabled，用户无法重试。
**建议**：外层包 `try/catch`，catch 中将 `confirmEl.disabled = false` 并提示用户重试。

---

### Issue 3：`generate_images.py` CATEGORIES/MATERIALS 与 `config.py` 不一致
**状态：确认存在，Phase 2 前必须修**

| 文件 | CATEGORIES | MATERIALS |
|------|-----------|-----------|
| `config.py` | bowl, mug, pitcher, tray, vase | wood, metal, glass, ceramic, stone |
| `generate_images.py` | bowl, **cup, plate**, vase, **box**, pitcher | wood, **plastic**, metal, glass, ceramic, stone |
| `static/images/` 实际目录 | bowl, mug, pitcher, tray, vase | wood, metal, glass, ceramic, stone |

`static/images/` 与 `config.py` 一致，但 `generate_images.py` 包含错误的类别（cup/plate/box）和多余材质（plastic），运行后会生成 app 无法使用的图片。
**建议**：将 `generate_images.py` L8-9 同步为 `config.py` 的值。

---

## 2. 测试项结果

### 2.1 完整流程走查（P0）— 代码走查

| 步骤 | 路由/操作 | 结果 |
|------|-----------|------|
| 访问 `/` | `render_template('index.html')` | ✅ 正常 |
| `POST /register` | 生成 code、assign trial、redirect `/study` | ✅ 正常（见 Issue 1） |
| `GET /study` | 取 trial，渲染图片+参与码+倒计时 | ✅ 正常 |
| `POST /api/study-start` | 写 `study_started_at`（COALESCE 防重写） | ✅ 正常 |
| `POST /api/study-done` | 返回 `{next_url: /recall/immediate}` | ✅ 正常 |
| `GET /recall/immediate` | 渲染 grid，写 session 随机顺序 | ✅ 正常 |
| `POST /api/recall/immediate` | 存 response，算 correct 标志，返回 done URL | ✅ 正常 |
| `GET /done` | 显示参与码 + 三阶段进度点 | ✅ 正常 |
| `/return/<code>` → week | 需要 `DEBUG_SKIP_WINDOWS=True` | ⚠️ 当前 False，线上无法测试 |
| `/return/<code>` → month | 同上 | ⚠️ 同上 |
| 所有阶段完成后返回 | `get_phase_row` 返回 `(None,None)` → redirect done | ✅ 逻辑正确 |

> **注意**：`DEBUG_SKIP_WINDOWS = False`，如需本地走查全三阶段，须先临时改为 `True`。

---

### 2.2 参与码返回（P0）— 代码 + DB 验证

| 场景 | 期望 | 实际 |
|------|------|------|
| 有效码（如 `Crab_20`） | 跳转到正确阶段 | ✅ DB 查询确认 code 存在，逻辑路径正确 |
| 无效码（`INVALID_CODE`） | 回首页 | ✅ `if not row: redirect(index)` 覆盖 |

---

### 2.3 中断恢复（P1）— 代码走查

| 场景 | `get_phase_row` 返回 | 恢复跳转 |
|------|---------------------|---------|
| study 未开始就关闭（`study_started_at` IS NULL） | `(trial, 'study')` | → `/study` ✅ |
| 倒计时开始后关闭（`study_started_at` 已写，immediate 未做） | `(trial, 'immediate')` | → `/recall/immediate` ✅ |
| recall 页面中途关闭（response 未写） | `(trial, 'immediate/week/month')` | → 对应 recall 页面 ✅ |

---

### 2.4 数据验证（P1）— SQL 查询实测

```sql
-- 以下三条均对当前 DB（30参与者，32回应）执行
```

| 查询 | 期望 | 实际 |
|------|------|------|
| `(trial_id, phase)` 唯一性 | 空结果 | ✅ 空 |
| `category_correct` 计算正确性 | 空结果 | ✅ 空 |
| `material_correct` 计算正确性 | 空结果 | ✅ 空 |

**当前 DB 状态**：

| 指标 | 值 |
|------|----|
| 参与者总数 | 30 |
| trials 总数 | 30 |
| responses 总数 | 32 |
| immediate 回应 | 23 |
| week 回应 | 5 |
| month 回应 | 4 |
| 完成全 3 阶段的参与者 | 3（Hawk_53、Whale_45、Swan_80） |
| `response_time_ms` 为 NULL | 0（全部有效） |

---

## 3. 额外发现

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 4 | `app.secret_key = os.urandom(24).hex()` 每次重启重新生成 | app.py L21 | 重启后已有 session 全部失效，用户需重新用参与码返回 |
| 5 | `month` 窗口只检查下界（`days >= 25`），无上界 | app.py L114 | month 阶段永久开放，应为有意设计，无需修改 |

---

## 4. 建议修复优先级

| 优先 | 问题 | 操作 |
|------|------|------|
| P0 — Phase 2 前必须 | Issue 3：generate_images.py 类别/材质不一致 | 同步为 config.py 的值 |
| P1 | Issue 2：grid.js 无 catch | 添加 try/catch，恢复按钮 |
| P2 | Issue 1：register() 无 db.commit() | 加一行 db.commit() |
| P2 | 额外发现 4：secret_key 随机 | 改为固定值或从环境变量读取 |
