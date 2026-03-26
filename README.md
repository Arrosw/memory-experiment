# 记忆实验

研究人类记忆中，物体的**表面材质**（wood、metal、glass…）是否比**语义类别**（bowl、cup、vase…）遗忘得更快。

## 研究假设

> 人们会主动遗忘物体的表面材质纹理，但保留对物体类别的语义记忆。

通过对比三个时间节点（即时 / 约1周 / 约1个月）的类别准确率与材质准确率，验证上述假设。

## 实验流程

1. **学习阶段** — 参与者观看一张物体图片（如木质碗）5 秒
2. **即时回忆** — 在 6×6 网格（类别 × 材质）中选出刚才看到的物体
3. **一周回忆** — 约 5–9 天后返回，再次回忆同一物体
4. **一个月回忆** — 约 25–40 天后返回，完成最终回忆

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python app.py
```

浏览器访问 `http://localhost:5000`

### 3. 参与实验

1. 打开首页，输入昵称（可选）后点击「开始」
2. 专注观看图片 5 秒
3. 在 6×6 网格中点击你认为正确的格子（行 = 类别，列 = 材质）
4. 记下页面显示的**专属代码**（如 `Tiger_42`），用于后续返回
5. 在提示日期返回，访问 `http://localhost:5000/return/<你的代码>` 继续实验

### 4. 管理后台

访问 `/admin`，使用 HTTP Basic Auth 登录：

- 用户名：`admin`
- 密码：`memory2026`

后台提供：各阶段参与人数、类别/材质准确率统计、最近参与者列表。

导出原始数据：

```
GET /admin/export.csv
```

返回包含所有回答记录的 CSV 文件。

## 项目结构

```
memory/
├── app.py                  # Flask 主应用（路由、数据库、会话）
├── config.py               # 配置常量（类别、材质、时间窗口）
├── generate_images.py      # FLUX.1-dev 图像生成脚本（在 GPU 服务器运行）
├── templates/
│   ├── base.html           # 基础布局（含全部 CSS）
│   ├── index.html          # 注册 / 返回页
│   ├── study.html          # 学习阶段
│   ├── recall.html         # 回忆阶段（2D 网格）
│   ├── done.html           # 阶段完成提示
│   └── admin.html          # 管理员统计面板
├── static/
│   ├── grid.js             # 网格交互逻辑
│   └── images/             # 图像库：{类别}/{材质}/study.png（第二阶段填充）
├── data/experiment.db      # SQLite 数据库（已加入 .gitignore）
├── requirements.txt
└── plan.md                 # 完整设计方案与决策记录
```

## 开发阶段

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1 | 进行中 | 使用动态生成的占位图，完整流程可运行 |
| Phase 2 | 待完成 | 通过 `generate_images.py` 在远程 GPU 生成真实图像 |
| Phase 3 | 待完成 | 替换占位图，运行正式实验并分析数据 |

## 图像生成（远程 GPU）

需要在配备 RTX 3090 的服务器上运行 FLUX.1-dev：

```bash
# 在远程服务器生成图像
ssh gpu-server "cd ~/memory && python generate_images.py"

# 将生成结果同步到本地
rsync -avz gpu-server:~/memory/output/ ./static/images/
```

Phase 2 额外依赖：`torch`、`diffusers`、`transformers`、`accelerate`（见 `requirements.txt` 注释部分）。

## 类别与材质

| | wood | plastic | metal | glass | ceramic | stone |
|---|---|---|---|---|---|---|
| **bowl** | | | | | | |
| **cup** | | | | | | |
| **plate** | | | | | | |
| **vase** | | | | | | |
| **box** | | | | | | |
| **pitcher** | | | | | | |

回忆阶段的 6×6 网格即对应上表，参与者在其中选择目标物体。

## 数据库结构

- `participants` — 参与者信息（专属代码、昵称、注册时间）
- `trials` — 每次实验分配的物体（类别 + 材质）
- `responses` — 每个阶段的回答记录（准确率、响应时间）
