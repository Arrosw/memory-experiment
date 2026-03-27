# Memory Experiment — 修复方案

> 对应：test_result.md 中确认的 4 个问题

---

## Fix 1：`register()` 加 `db.commit()`（P2）

**文件**：`app.py` L164

**修改**：在 INSERT 之后、SELECT 之前加一行 commit。

```python
# 修改前
@app.post('/register')
def register():
    db = get_db()
    code = generate_code(db)
    db.execute("INSERT INTO participants (code, nickname) VALUES (?,?)", (code, request.form.get('nickname', '').strip() or None))
    participant_id = db.execute("SELECT id FROM participants WHERE code=?", (code,)).fetchone()['id']
    assign_trials(db, participant_id)
    session['participant_id'] = participant_id
    return redirect(url_for('study'))

# 修改后
@app.post('/register')
def register():
    db = get_db()
    code = generate_code(db)
    db.execute("INSERT INTO participants (code, nickname) VALUES (?,?)", (code, request.form.get('nickname', '').strip() or None))
    db.commit()
    participant_id = db.execute("SELECT id FROM participants WHERE code=?", (code,)).fetchone()['id']
    assign_trials(db, participant_id)
    session['participant_id'] = participant_id
    return redirect(url_for('study'))
```

**验证**：注册新用户 → DB 中立即可查到 participants 行，即使 assign_trials 尚未返回。

---

## Fix 2：`grid.js` submit handler 加 try/catch（P1）

**文件**：`static/grid.js` L92-101

**修改**：用 try/catch 包裹 fetch，失败时恢复按钮。

```js
// 修改前
confirmEl.addEventListener("click", async () => {
  confirmEl.disabled = true;
  const resp = await fetch(`/api/recall/${PHASE}`, {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify({ x: xIdx, y: yIdx, response_time_ms: Date.now() - startMs }),
  });
  const data = await resp.json();
  if (data.next_url) window.location.href = data.next_url;
});

// 修改后
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
```

**验证**：在 DevTools Network 面板中将网络设为 Offline → 点击确认 → 弹出提示且按钮恢复可点击。

---

## Fix 3：同步 `generate_images.py` 的 CATEGORIES/MATERIALS（P0）

**文件**：`generate_images.py` L8-9

**修改**：替换为与 `config.py` 一致的值。

```python
# 修改前
CATEGORIES = ["bowl", "cup", "plate", "vase", "box", "pitcher"]
MATERIALS = ["wood", "plastic", "metal", "glass", "ceramic", "stone"]

# 修改后
CATEGORIES = ["bowl", "mug", "pitcher", "tray", "vase"]
MATERIALS = ["wood", "metal", "glass", "ceramic", "stone"]
```

**验证**：`python generate_images.py --dry-run` 输出的 prompt 应只含 bowl/mug/pitcher/tray/vase × wood/metal/glass/ceramic/stone（25 组）。

---

## Fix 4：`secret_key` 固定化（P2）

**文件**：`app.py` L21

**修改**：从环境变量读取，缺省时才随机生成（仅本地开发）。

```python
# 修改前
app.secret_key = os.urandom(24).hex()

# 修改后
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-fallback-key')
```

**验证**：设 `SECRET_KEY=abc123` 启动 → 注册 → 重启 app（同一 SECRET_KEY）→ 用参与码返回 → session 仍有效。
