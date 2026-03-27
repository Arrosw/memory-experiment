# Memory Experiment — 测试计划（手动）

> 小规模调查，手动走查即可。重点确保核心流程跑通、数据正确入库。

## 1. 已知问题

| # | 问题 | 位置 | 影响 |
|---|------|------|------|
| 1 | `register()` 缺少 `db.commit()` | app.py L164 | 极端情况下注册丢失 |
| 2 | `grid.js` fetch 无 catch，网络失败时按钮卡死 | grid.js L92-101 | 用户无法重试 |
| 3 | `generate_images.py` 的 CATEGORIES/MATERIALS 与 `config.py` 不一致 | generate_images.py L8-9 | Phase 2 图片缺失 |

## 2. 测试项

### 2.1 完整流程走查（P0）

设 `DEBUG_SKIP_WINDOWS = True` 跳过时间窗口。

```
1. 访问 / → 输入昵称 → 开始实验
2. /study 显示图片 + 倒计时 → 自动跳转 /recall/immediate
3. 拖动坐标选择 → 确认 → /done，显示参与码
4. 复制参与码，关闭页面
5. 重新打开，输入参与码 → /recall/week → 确认 → /done
6. 再次输入参与码 → /recall/month → 确认 → /done，三个蓝点
7. 再次输入参与码 → /done（无更多阶段）
```

检查：
- 每步跳转正确
- DB responses 表有 3 条记录（immediate/week/month）
- category_correct / material_correct 计算正确

### 2.2 参与码返回（P0）

- 有效码：跳转到正确阶段
- 无效码：回首页

### 2.3 中断恢复（P1）

- study 中途关闭 → 用码返回 → 应进入 recall（非重新 study）
- recall 中途关闭 → 用码返回 → 应能重新 recall

### 2.4 数据验证（P1）

实验跑完后执行：

```sql
-- 每个 (trial_id, phase) 应唯一
SELECT trial_id, phase, COUNT(*) c FROM responses GROUP BY trial_id, phase HAVING c > 1;

-- category_correct 计算正确
SELECT r.id FROM responses r JOIN trials t ON r.trial_id = t.id
WHERE r.category_correct != (r.resp_category = t.category);

-- material_correct 计算正确
SELECT r.id FROM responses r JOIN trials t ON r.trial_id = t.id
WHERE r.material_correct != (r.resp_material = t.material);
```

三条查询均应返回空结果。

## 3. 建议修复

1. **`register()` 加 `db.commit()`** — 一行修复
2. **`grid.js` fetch 加 catch** — 网络失败时恢复按钮，提示重试
3. **同步 `generate_images.py` 的 CATEGORIES/MATERIALS** — Phase 2 前必须修
