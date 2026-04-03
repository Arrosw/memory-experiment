# Memory Experiment — Development Guide

## Project Overview
Human memory experiment: test whether people forget surface material textures faster than core category semantics. Flask web app + remote GPU image generation.

## Tech Stack
- **Backend**: Flask (single file `app.py`), SQLite, Python 3.10+
- **Frontend**: Vanilla HTML/CSS/JS, Jinja2 templates, no frameworks
- **Image Gen**: FLUX.1-dev via diffusers on remote 3090 GPU
- **Style**: Apple HIG aesthetic (see plan.md Section 6)

## Development Rules

### Architecture
- Single-file Flask app (`app.py`), keep concise (currently ~570 lines)
- No ORM — use raw SQL with `sqlite3`
- No frontend frameworks — vanilla JS only
- Minimize dependencies: flask, pillow for Phase 1

### Code Style
- Python: snake_case, type hints on public functions only
- SQL: UPPERCASE keywords, lowercase identifiers
- JS: camelCase, const by default, no var
- CSS: BEM-lite naming (`.grid-cell`, `.grid-cell.active`)
- Keep functions short (<30 lines)

### Database
- SQLite with WAL mode (`PRAGMA journal_mode=WAL` at startup)
- Use `db = sqlite3.connect('data/experiment.db')` with `row_factory = sqlite3.Row`
- Always parameterize queries (never f-string SQL)

### UI Design
- Apple aesthetic: see plan.md Section 6 for exact CSS variables
- Max content width: 480px, centered
- Font: `-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif`
- Buttons: pill shape (`border-radius: 9999px`), `#007AFF` blue
- Cards: white, `border-radius: 12px`, subtle shadow
- No borders on cards — use shadow only
- Transitions: 150ms for hover, 250ms for state changes
- Spacing: 4pt grid (4, 8, 12, 16, 20, 24, 32, 40px)

### Image Paths Convention
- Study image: `static/images/{category}/{material}/study.png`
- Recall image: `static/images/{category}/{material}/recall.png`
- Thumbnail: `static/images/{category}/{material}/thumb.jpg` (256x256)
- Phase 1 placeholder: served dynamically via `/placeholder/<cat>/<mat>`

### Template Structure
- `base.html`: all CSS inline in `<style>` (single-file simplicity), common layout
- Each page extends base, has single `.card` container
- No external CSS files needed for Phase 1 (embed in base.html)

### Key Constants (config.py — source of truth)
```python
CATEGORIES   = ['bowl', 'mug', 'pitcher', 'tray', 'vase']
MATERIALS    = ['wood', 'stone', 'ceramic', 'metal', 'glass']
DOG_BREEDS   = ['german shepherd', 'golden retriever', 'husky', 'labrador', 'shiba inu']
DOG_BACKGROUNDS = ['dry_grassy_ground', 'dusty_ground', 'fine_gravel_ground', 'sand_ground', 'slightly_damp_dirt']
TRIALS_PER_PARTICIPANT = 1        # object trials; always 1 dog trial added separately
STUDY_DURATION_SECONDS = 3
WEEK_WINDOW  = (5, 9)             # days after study
MONTH_WINDOW = (25, 40)           # days after study
DEBUG_SKIP_WINDOWS = False        # True → bypass time window checks
ADMIN_USER / ADMIN_PASS = 'admin' / 'memory2026'
DB_PATH = 'data/experiment.db'
```

### Database Schema
```sql
participants: id, code (unique), nickname, created_at
trials:       id, participant_id, category, material, trial_order, trial_type ('object'|'dog'), study_started_at
responses:    id, trial_id, phase ('immediate'|'week'|'month'), responded_at,
              resp_category, resp_material, resp_col, resp_row,
              category_correct (0|1), material_correct (0|1), response_time_ms
```
- `trials.trial_type='object'`: category=物体类别, material=材质
- `trials.trial_type='dog'`:    category=狗品种, material=背景

### Route Map (app.py)
```
GET  /                      → index.html (register form)
POST /register              → create participant + assign 2 trials → /study
GET  /study                 → show study image (object or dog), 3s timer
POST /api/study-start       → record study_started_at
POST /api/study-done        → JSON {next_url: /recall/immediate}
GET  /recall/<phase>        → recall grid UI (phase: immediate|week|month)
POST /api/recall/<phase>    → save response; smart-redirect to next trial or /done
GET  /done                  → progress page (phase done = ALL trials have that phase response)
GET  /return/<code>         → restore session by code → /study or /recall/<phase>
GET  /admin                 → admin dashboard (Basic auth)
GET  /admin/export.csv      → CSV export
GET  /api/thumbs            → base64 JPEG thumbnails for object recall grid
GET  /api/thumbs-dog        → base64 JPEG thumbnails for dog recall grid
GET  /placeholder/<cat>/<mat> → generated placeholder image
```

### Key Functions (app.py)
- `scan_available()` → (avail_cats, avail_mats) from static/images/
- `scan_available_dog()` → (avail_breeds, avail_bgs) from static/images_dog/
- `get_random_image(cat, mat)` → URL from static/images/
- `get_random_image_dog(breed, bg)` → URL from static/images_dog/
- `assign_trials(db, pid)` → inserts 1 object trial (order=1) + 1 dog trial (order=2), balanced by usage count
- `get_phase_row(db, pid)` → (trial, phase_str) — next incomplete step for participant; iterates all trials in order
- `get_current_phase(db, pid)` → (trial_id, phase_str)

### Session Variables (set in /recall/<phase>)
- `recall_avail_cats`, `recall_avail_mats` — ordered lists for current recall grid
- `recall_x_order`, `recall_y_order` — shuffled index arrays
- `recall_trial_type` — 'object' or 'dog'

### Participant Flow
1. Register → assign 2 trials
2. Study object image (3s) → /recall/immediate (object grid) → save_recall → /study (dog)
3. Study dog image (3s) → /recall/immediate (dog grid) → save_recall → /done
4. (Return week/month): /recall/week object → /recall/week dog → /done

### Image Paths
- Object study: `static/images/{category}/{material}/study.png`
- Object recall week/month: same study.png
- Dog study: `static/images_dog/{breed}/{background}/study.png`
- Phase 1 placeholder: `/placeholder/<cat>/<mat>` (generated dynamically)

### Admin Panel (3 accuracy tables)
1. **物体准确率** — filtered `WHERE trial_type='object'`; columns: phase / count / 类别acc / 材质acc
2. **狗的准确率** — filtered `WHERE trial_type='dog'`; columns: phase / count / 狗类别acc / 背景acc
3. **总体准确率** — low_freq = avg(object_cat, dog_cat); high_freq = avg(object_mat, dog_mat)
- Per-user detail: 2 rows per participant (object row + dog row)

### Development Phases
1. **Phase 1 (current)**: Demo with placeholder images — full flow works end-to-end
2. **Phase 2**: Generate real images on remote 3090 via `generate_images.py`
3. **Phase 3**: Replace placeholders, run actual experiment

### Testing
- Run: `python app.py` (debug=False; use `app.run(debug=True)` locally)
- Manual flow: register → study object → recall object → study dog → recall dog → /done
- Delayed recall: set `DEBUG_SKIP_WINDOWS = True` in config.py

### Remote GPU (Image Generation)
```bash
ssh gpu-server "cd ~/memory && python generate_images.py"
rsync -avz gpu-server:~/memory/output/ ./static/images/
```

### File Reference
- `plan.md` — full design plan with all decisions and rationale
- `app.py` — Flask app (~570 lines): routes, DB helpers, admin
- `config.py` — constants + init_db (schema + migration)
- `static/grid.js` — recall grid UI (drag axes, crossfade thumbs, submit)
- `generate_images.py` — FLUX.1-dev image gen (GPU server only)
- `templates/base.html` — all CSS inline here
- `templates/{index,study,recall,done,admin}.html` — page templates
- `CHANGELOG.md` — one entry per meaningful commit

### Git & GitHub Workflow
- **Commit often**: one logical change per commit, conventional commit messages
  - Format: `type(scope): short description` (e.g. `feat(app): add recall route`, `fix(db): parameterize participant query`)
  - Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- **Branch strategy**: `main` is always runnable; feature work on `feat/<name>` branches
- **Push on milestone**: push to GitHub after each Phase milestone or significant feature
- **CHANGELOG.md**: append an entry every time you commit a meaningful change
  - Format: `## [date] — short title\n- bullet points of what changed and why`
- **Never commit**: `data/experiment.db`, `static/images/` (real images), `.env`, `__pycache__`
- Add `.gitignore` covering the above before first commit

### Code Generation & Review Process
- **Codex GPT5.4** writes code (via MCP tool) — provide full context from CLAUDE.md + plan.md
- **Claude Code** reviews all generated code before committing:
  - Check security (SQL injection, XSS, session fixation)
  - Check adherence to architecture rules (file size, no ORM, vanilla JS)
  - Check correctness against experiment design in plan.md
- Do not commit code that has not been reviewed

### First Principles
Please think using first principles. You cannot always assume that I am fully aware of what I want and how to obtain it. Please be cautious and start from the original needs and problems. If the motives and goals are not clear, stop and discuss with me. 

### Scheme Specification
When you are required to provide a modification or reconfiguration plan, the following specifications must be followed:
- It is not allowed to provide compatibility or patch-based solutions.
- Excessive design is prohibited. The shortest path implementation must be maintained and the first requirement must not be violated.
- It is not permitted to propose solutions beyond the requirements provided by me, such as some fallback and downgrade plans, as this may cause issues with the business logic.
- The logic of the plan must be correct and must undergo full-chain logic verification.