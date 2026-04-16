import base64
import csv
import math
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path

from flask import Flask, Response, g, jsonify, redirect, render_template, request, send_file, session, url_for
from PIL import Image, ImageDraw, ImageFont

from config import ADMIN_PASS, ADMIN_USER, AGE_GROUPS, ANIMALS, CATEGORIES, DAY_WINDOW, DB_PATH, DEBUG_SKIP_WINDOWS, DOG_BACKGROUNDS, DOG_BREEDS, EDUCATIONS, GENDERS, MATERIALS, STUDY_DURATION_SECONDS, TRIALS_PER_PARTICIPANT, WEEK_WINDOW, WEEK2_WINDOW, init_db

MATERIAL_COLORS = {
    'wood': '#D2A679', 'plastic': '#4FC3F7', 'metal': '#B0BEC5',
    'glass': '#E0F7FA', 'ceramic': '#FFCCBC', 'stone': '#9E9E9E',
}
DIFFUSION_CATEGORIES = ('vase', 'bowl', 'mug', 'pitcher', 'tray')
DOG_DIFFUSION_BREEDS = ('german shepherd', 'husky', 'shiba inu', 'labrador', 'golden retriever')
DOG_DIFFUSION_BACKGROUNDS = ('sand_ground', 'dusty_ground', 'dry_grassy_ground', 'slightly_damp_dirt', 'fine_gravel_ground')
PHASE_ORDER = ('immediate', 'day', 'week', '2week')
PHASE_LABELS = {'immediate': '即时', 'day': '1天', 'week': '1周', '2week': '2周'}
PHASES = set(PHASE_ORDER)
BEIJING_TZ = timezone(timedelta(hours=8))
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-only-fallback-key')


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def beijing_timestamp() -> str:
    return beijing_now().strftime('%Y-%m-%d %H:%M:%S')


def scan_available():
    """Return (avail_cats, avail_mats) — sorted lists with ≥1 image. Falls back to full lists."""
    images_dir = Path(app.static_folder or 'static') / 'images'
    combos = set()
    if images_dir.exists():
        for cat_dir in images_dir.iterdir():
            if cat_dir.is_dir() and cat_dir.name in CATEGORIES:
                for mat_dir in cat_dir.iterdir():
                    if mat_dir.is_dir() and mat_dir.name in MATERIALS:
                        imgs = [f for f in mat_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
                        if imgs:
                            combos.add((cat_dir.name, mat_dir.name))
    if not combos:
        return list(CATEGORIES), list(MATERIALS)
    cats = sorted({c for c, m in combos}, key=lambda x: CATEGORIES.index(x))
    mats = sorted({m for c, m in combos}, key=lambda x: MATERIALS.index(x))
    return cats, mats


def scan_available_dog():
    images_dir = Path(app.static_folder or 'static') / 'images_dog'
    combos = set()
    if images_dir.exists():
        for breed_dir in images_dir.iterdir():
            if breed_dir.is_dir() and breed_dir.name in DOG_BREEDS:
                for bg_dir in breed_dir.iterdir():
                    if bg_dir.is_dir() and bg_dir.name in DOG_BACKGROUNDS:
                        imgs = [f for f in bg_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
                        if imgs:
                            combos.add((breed_dir.name, bg_dir.name))
    if not combos:
        return list(DOG_BREEDS), list(DOG_BACKGROUNDS)
    breeds = sorted({b for b, bg in combos}, key=lambda x: DOG_BREEDS.index(x))
    bgs = sorted({bg for b, bg in combos}, key=lambda x: DOG_BACKGROUNDS.index(x))
    return breeds, bgs


def get_random_image(category: str, material: str) -> str:
    img_dir = Path(app.static_folder or 'static') / 'images' / category / material
    if img_dir.exists():
        imgs = [f for f in img_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
        if imgs:
            return url_for('study_img', relpath=f"images/{category}/{material}/{random.choice(imgs).name}")
    return url_for('placeholder', cat=category, mat=material)


def get_random_image_dog(breed: str, background: str) -> str:
    img_dir = Path(app.static_folder or 'static') / 'images_dog' / breed / background
    if img_dir.exists():
        imgs = [f for f in img_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')]
        if imgs:
            return url_for('study_img', relpath=f"images_dog/{breed}/{background}/{random.choice(imgs).name}")
    return url_for('placeholder', cat=breed, mat=background)


def ensure_db() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    init_db(db)
    db.close()


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop('db', None)
    if db:
        db.close()


def generate_code(db) -> str:
    while True:
        code = f"{random.choice(ANIMALS)}_{random.randint(10,99)}"
        if not db.execute("SELECT 1 FROM participants WHERE code=?", (code,)).fetchone():
            return code


def assign_trials(db, participant_id: int) -> None:
    counts = db.execute("SELECT category, material, COUNT(*) c FROM trials WHERE trial_type='object' GROUP BY category, material").fetchall()
    count_map = {(r['category'], r['material']): r['c'] for r in counts}
    avail_cats, avail_mats = scan_available()
    all_combos = [(c, m) for c in avail_cats for m in avail_mats]
    random.shuffle(all_combos)
    all_combos.sort(key=lambda x: count_map.get(x, 0))
    cat, mat = all_combos[0]
    db.execute("INSERT INTO trials (participant_id, category, material, trial_order, trial_type) VALUES (?,?,?,?,?)",
               (participant_id, cat, mat, 1, 'object'))

    dog_counts = db.execute("SELECT category, material, COUNT(*) c FROM trials WHERE trial_type='dog' GROUP BY category, material").fetchall()
    dog_count_map = {(r['category'], r['material']): r['c'] for r in dog_counts}
    avail_breeds, avail_bgs = scan_available_dog()
    dog_combos = [(b, bg) for b in avail_breeds for bg in avail_bgs]
    random.shuffle(dog_combos)
    dog_combos.sort(key=lambda x: dog_count_map.get(x, 0))
    breed, bg = dog_combos[0]
    db.execute("INSERT INTO trials (participant_id, category, material, trial_order, trial_type) VALUES (?,?,?,?,?)",
               (participant_id, breed, bg, 2, 'dog'))
    db.commit()


def parse_ts(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').replace(tzinfo=BEIJING_TZ)


def get_phase_row(db, participant_id: int):
    trials = db.execute("SELECT * FROM trials WHERE participant_id=? ORDER BY trial_order, id", (participant_id,)).fetchall()
    now = beijing_now()
    for trial in trials:
        done = {r['phase'] for r in db.execute("SELECT phase FROM responses WHERE trial_id=?", (trial['id'],)).fetchall()}
        if not trial['study_started_at']:
            return trial, 'study'
        if 'immediate' not in done:
            return trial, 'immediate'
        study_date = parse_ts(trial['study_started_at']).date()
        days = (now.date() - study_date).days
        if 'day' not in done and (DEBUG_SKIP_WINDOWS or DAY_WINDOW[0] <= days <= DAY_WINDOW[1]):
            return trial, 'day'
        if 'week' not in done and (DEBUG_SKIP_WINDOWS or WEEK_WINDOW[0] <= days <= WEEK_WINDOW[1]):
            return trial, 'week'
        if '2week' not in done and (DEBUG_SKIP_WINDOWS or days >= WEEK2_WINDOW[0]):
            return trial, '2week'
    return None, None


def get_current_phase(db, participant_id: int):
    trial, phase = get_phase_row(db, participant_id)
    return (trial['id'], phase) if trial else (None, None)


def participant_id():
    return session.get('participant_id')


def image_url(category: str, material: str, phase: str) -> str:
    if phase == 'immediate':
        return url_for('placeholder', cat=category, mat=material)
    path = Path(app.static_folder or 'static') / 'images' / category / material / 'study.png'
    return f"/static/images/{category}/{material}/study.png" if path.exists() else url_for('placeholder', cat=category, mat=material)


def admin_ok() -> bool:
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Basic '):
        return False
    try:
        decoded = base64.b64decode(auth.split(' ', 1)[1]).decode()
    except Exception:
        return False
    return decoded == f"{ADMIN_USER}:{ADMIN_PASS}"


def admin_fail():
    return Response('Unauthorized', 401, {'WWW-Authenticate': 'Basic realm="Admin"'})


def current_trial_for_study(db, participant_id: int):
    trial, phase = get_phase_row(db, participant_id)
    return trial if phase == 'study' else None


@app.get('/')
def index():
    return render_template('index.html', genders=GENDERS, age_groups=AGE_GROUPS, educations=EDUCATIONS)


@app.post('/register')
def register():
    db = get_db()
    code = generate_code(db)
    nickname = request.form.get('nickname', '').strip()
    gender = request.form.get('gender', '').strip()
    age = request.form.get('age', '').strip()
    education = request.form.get('education', '').strip()
    error = None
    if not nickname:
        error = '请填写姓名'
    elif gender not in GENDERS:
        error = '请选择性别'
    elif age not in AGE_GROUPS:
        error = '请选择年龄段'
    elif education not in EDUCATIONS:
        error = '请选择学历'
    if error:
        return render_template(
            'index.html',
            error=error,
            form={'nickname': nickname, 'gender': gender, 'age': age, 'education': education},
            genders=GENDERS,
            age_groups=AGE_GROUPS,
            educations=EDUCATIONS,
        ), 400
    db.execute(
        "INSERT INTO participants (code, nickname, gender, age, education, created_at) VALUES (?,?,?,?,?,?)",
        (code, nickname, gender, age, education, beijing_timestamp()),
    )
    db.commit()
    participant_id = db.execute("SELECT id FROM participants WHERE code=?", (code,)).fetchone()['id']
    assign_trials(db, participant_id)
    session['participant_id'] = participant_id
    return redirect(url_for('study'))


@app.get('/study')
def study():
    pid = participant_id()
    if not pid:
        return redirect(url_for('index'))
    db = get_db()
    trial = current_trial_for_study(db, pid)
    if not trial:
        trial_id, phase = get_current_phase(db, pid)
        return redirect(url_for('recall', phase=phase) if trial_id and phase in PHASES else url_for('done'))
    code = db.execute("SELECT code FROM participants WHERE id=?", (pid,)).fetchone()['code']
    if trial['trial_type'] == 'dog':
        img_url = get_random_image_dog(trial['category'], trial['material'])
    else:
        img_url = get_random_image(trial['category'], trial['material'])
    return render_template('study.html', image_url=img_url, duration=STUDY_DURATION_SECONDS, code=code, trial_type=trial['trial_type'])


@app.post('/api/study-start')
def study_start():
    pid = participant_id()
    if not pid:
        return jsonify({'ok': False}), 401
    trial = current_trial_for_study(get_db(), pid)
    if trial:
        get_db().execute("UPDATE trials SET study_started_at=COALESCE(study_started_at, ?) WHERE id=?", (beijing_timestamp(), trial['id']))
        get_db().commit()
    return jsonify({'ok': True})


@app.post('/api/study-done')
def study_done():
    return jsonify({'next_url': url_for('recall', phase='immediate')})


@app.get('/recall/<phase>')
def recall(phase: str):
    pid = participant_id()
    if not pid:
        return redirect(url_for('index'))
    if phase not in PHASES:
        return redirect(url_for('done'))
    db = get_db()
    trial, current = get_phase_row(db, pid)
    if not trial or current != phase:
        return redirect(url_for('done'))
    if trial['trial_type'] == 'dog':
        avail_cats, avail_mats = scan_available_dog()
    else:
        avail_cats, avail_mats = scan_available()
    x_order = list(range(len(avail_mats)))
    y_order = list(range(len(avail_cats)))
    random.shuffle(y_order)
    session['recall_x_order'] = x_order
    session['recall_y_order'] = y_order
    session['recall_avail_cats'] = avail_cats
    session['recall_avail_mats'] = avail_mats
    session['recall_trial_type'] = trial['trial_type']
    return render_template('recall.html', phase=phase, x_order=x_order, y_order=y_order,
                           avail_cats=avail_cats, avail_mats=avail_mats, trial_type=trial['trial_type'])


@app.post('/api/recall/<phase>')
def save_recall(phase: str):
    pid = participant_id()
    if not pid or phase not in PHASES:
        return jsonify({'next_url': url_for('index')}), 400
    db = get_db()
    trial, current = get_phase_row(db, pid)
    if not trial or current != phase:
        return jsonify({'next_url': url_for('done')})
    data = request.get_json(silent=True) or {}
    xi, yi = data.get('x'), data.get('y')
    avail_cats = session.get('recall_avail_cats', list(CATEGORIES))
    avail_mats = session.get('recall_avail_mats', list(MATERIALS))
    x_order = session.get('recall_x_order', list(range(len(avail_mats))))
    y_order = session.get('recall_y_order', list(range(len(avail_cats))))
    if xi not in range(len(avail_mats)) or yi not in range(len(avail_cats)):
        return jsonify({'next_url': url_for('recall', phase=phase)}), 400
    resp_material = avail_mats[x_order[xi]]
    resp_category = avail_cats[y_order[yi]]
    db.execute(
        "INSERT INTO responses (trial_id, phase, responded_at, resp_category, resp_material, resp_col, resp_row, category_correct, material_correct, response_time_ms) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (trial['id'], phase, beijing_timestamp(), resp_category, resp_material, x_order[xi], y_order[yi], int(resp_category == trial['category']), int(resp_material == trial['material']), data.get('response_time_ms'))
    )
    db.commit()
    next_trial, next_phase = get_phase_row(db, pid)
    if next_trial is None:
        next_url = url_for('done', phase=phase)
    elif next_phase == 'study':
        next_url = url_for('study')
    else:
        next_url = url_for('recall', phase=next_phase)
    return jsonify({'next_url': next_url})


@app.get('/done')
def done():
    pid = participant_id()
    code = ''
    phase = request.args.get('phase', 'immediate')
    progress = [
        {'key': 'immediate', 'label': '即时', 'done': False, 'note': ''},
        {'key': 'day',       'label': '',      'done': False, 'note': ''},
        {'key': 'week',      'label': '',      'done': False, 'note': ''},
        {'key': '2week',     'label': '',      'done': False, 'note': ''},
    ]
    if pid:
        db = get_db()
        row = db.execute("SELECT code FROM participants WHERE id=?", (pid,)).fetchone()
        code = row['code'] if row else ''
        trials = db.execute("SELECT id, study_started_at FROM trials WHERE participant_id=? ORDER BY trial_order", (pid,)).fetchall()
        total_trials = len(trials)
        if trials:
            resp_phases = db.execute(
                "SELECT phase, COUNT(DISTINCT trial_id) c FROM responses "
                "WHERE trial_id IN (SELECT id FROM trials WHERE participant_id=?) GROUP BY phase",
                (pid,)
            ).fetchall()
            phases_done = {r['phase'] for r in resp_phases if r['c'] >= total_trials}
            for p in progress:
                p['done'] = p['key'] in phases_done
            first_trial = trials[0]
            if first_trial['study_started_at']:
                started = parse_ts(first_trial['study_started_at'])
                today = beijing_now().date()
                for key, offset in [('day', DAY_WINDOW[0]), ('week', WEEK_WINDOW[0]), ('2week', WEEK2_WINDOW[0])]:
                    entry = next(x for x in progress if x['key'] == key)
                    if not entry['done']:
                        target = (started + timedelta(days=offset)).date()
                        days_left = (target - today).days
                        if days_left > 0:
                            entry['note'] = f"{days_left}天后（{target.month}月{target.day}日）"
                        else:
                            entry['note'] = f"{target.month}月{target.day}日（可返回）"
    return render_template('done.html', code=code, phase=phase, progress=progress)


@app.get('/return/<code>')
def return_with_code(code: str):
    row = get_db().execute("SELECT id FROM participants WHERE code=?", (code,)).fetchone()
    if not row:
        return redirect(url_for('index'))
    session['participant_id'] = row['id']
    trial_id, phase = get_current_phase(get_db(), row['id'])
    if not trial_id:
        return redirect(url_for('done'))
    return redirect(url_for('study') if phase == 'study' else url_for('recall', phase=phase))


def _round_or_none(value):
    return round(value, 3) if value is not None else None


def _ellipse_params(points, mean_x, mean_y):
    n = len(points)
    if n < 2:
        return None
    var_x = sum((p['x'] - mean_x) ** 2 for p in points) / (n - 1)
    var_y = sum((p['y'] - mean_y) ** 2 for p in points) / (n - 1)
    cov = sum((p['x'] - mean_x) * (p['y'] - mean_y) for p in points) / (n - 1)
    disc = math.sqrt(max(0, (var_x - var_y) ** 2 + 4 * cov * cov))
    eig_1 = max(0, (var_x + var_y + disc) / 2)
    eig_2 = max(0, (var_x + var_y - disc) / 2)
    if eig_1 == 0 and eig_2 == 0:
        return None
    return {
        'rx': _round_or_none(2 * math.sqrt(eig_1)),
        'ry': _round_or_none(2 * math.sqrt(eig_2)),
        'angle': _round_or_none(0.5 * math.atan2(2 * cov, var_x - var_y)),
        'var_category': _round_or_none(var_x),
        'var_material': _round_or_none(var_y),
    }


def _diffusion_summary(points):
    n = len(points)
    if not points:
        metrics = {'abs_category': None, 'abs_material': None, 'distance': None, 'var_ratio': None}
        return {'n': 0, 'points': [], 'mean': None, 'ellipse': None, 'metrics': metrics}
    mean_x = sum(p['x'] for p in points) / n
    mean_y = sum(p['y'] for p in points) / n
    ellipse = _ellipse_params(points, mean_x, mean_y)
    var_x = ellipse['var_category'] if ellipse else None
    var_y = ellipse['var_material'] if ellipse else None
    ratio = var_y / var_x if var_x and var_y is not None else None
    metrics = {
        'abs_category': _round_or_none(sum(abs(p['x']) for p in points) / n),
        'abs_material': _round_or_none(sum(abs(p['y']) for p in points) / n),
        'distance': _round_or_none(sum(math.hypot(p['x'], p['y']) for p in points) / n),
        'var_ratio': _round_or_none(ratio),
    }
    return {'n': n, 'points': points, 'mean': {'x': _round_or_none(mean_x), 'y': _round_or_none(mean_y)}, 'ellipse': ellipse, 'metrics': metrics}


def _diffusion_point(row, x_order, y_order):
    if row['category'] not in x_order or row['resp_category'] not in x_order:
        return None
    if row['material'] not in y_order or row['resp_material'] not in y_order:
        return None
    return {
        'x': x_order.index(row['resp_category']) - x_order.index(row['category']),
        'y': y_order.index(row['resp_material']) - y_order.index(row['material']),
        'source': row['trial_type'],
    }


def _diffusion_chart(key, title, note, x_label, y_label, grouped):
    return {
        'key': key,
        'title': title,
        'note': note,
        'x_label': x_label,
        'y_label': y_label,
        'phases': [{'key': ph, 'label': PHASE_LABELS[ph], **_diffusion_summary(grouped[ph])} for ph in PHASE_ORDER],
    }


def build_diffusion_charts(db):
    rows = db.execute(
        "SELECT r.phase, t.trial_type, t.category, t.material, r.resp_category, r.resp_material "
        "FROM responses r JOIN trials t ON r.trial_id = t.id "
        "WHERE r.resp_category IS NOT NULL AND r.resp_material IS NOT NULL"
    ).fetchall()
    grouped = {
        'object': {phase: [] for phase in PHASE_ORDER},
        'dog': {phase: [] for phase in PHASE_ORDER},
        'combined': {phase: [] for phase in PHASE_ORDER},
    }
    orders = {
        'object': (DIFFUSION_CATEGORIES, tuple(MATERIALS)),
        'dog': (DOG_DIFFUSION_BREEDS, DOG_DIFFUSION_BACKGROUNDS),
    }
    for row in rows:
        if row['phase'] not in PHASE_ORDER or row['trial_type'] not in orders:
            continue
        point = _diffusion_point(row, *orders[row['trial_type']])
        if point is None:
            continue
        grouped[row['trial_type']][row['phase']].append(point)
        grouped['combined'][row['phase']].append(point)
    return [
        _diffusion_chart('object', '物体记忆弥散图', '横轴是物体类别偏差，纵轴是材质偏差。类别顺序：vase → bowl → mug → pitcher → tray。', '类别偏差', '材质偏差', grouped['object']),
        _diffusion_chart('dog', '狗记忆弥散图', '横轴是狗品种偏差，纵轴是背景偏差。品种顺序：german shepherd → husky → shiba inu → labrador → golden retriever。', '狗品种偏差', '背景偏差', grouped['dog']),
        _diffusion_chart('combined', '总体记忆弥散图', '合并物体和狗 trial：横轴统一为低频语义偏差，纵轴统一为高频表面偏差。', '低频偏差', '高频偏差', grouped['combined']),
    ]


@app.get('/admin')
def admin():
    if not admin_ok():
        return admin_fail()
    db = get_db()

    def elapsed_label(elapsed_seconds):
        if elapsed_seconds is None:
            return '—'
        if elapsed_seconds < 60:
            return '<1分钟'
        if elapsed_seconds < 86400:
            return '<1天'
        if elapsed_seconds < 7 * 86400:
            return '<1周'
        if elapsed_seconds < 14 * 86400:
            return '<2周'
        if elapsed_seconds < 30 * 86400:
            return '<1月'
        return '>1月'

    total = db.execute("SELECT COUNT(*) c FROM participants").fetchone()['c']
    phase_counts = db.execute("SELECT phase, COUNT(*) c FROM responses GROUP BY phase").fetchall()
    accuracy = db.execute("SELECT phase, AVG(category_correct) ac, AVG(material_correct) am FROM responses GROUP BY phase").fetchall()
    obj_phase_counts = db.execute(
        "SELECT r.phase, COUNT(*) c FROM responses r JOIN trials t ON r.trial_id = t.id WHERE t.trial_type = 'object' GROUP BY r.phase"
    ).fetchall()
    dog_phase_counts = db.execute(
        "SELECT r.phase, COUNT(*) c FROM responses r JOIN trials t ON r.trial_id = t.id WHERE t.trial_type = 'dog' GROUP BY r.phase"
    ).fetchall()
    obj_accuracy = db.execute(
        "SELECT r.phase, AVG(r.category_correct) ac, AVG(r.material_correct) am "
        "FROM responses r JOIN trials t ON r.trial_id = t.id WHERE t.trial_type = 'object' GROUP BY r.phase"
    ).fetchall()
    dog_accuracy = db.execute(
        "SELECT r.phase, AVG(r.category_correct) ac, AVG(r.material_correct) am "
        "FROM responses r JOIN trials t ON r.trial_id = t.id WHERE t.trial_type = 'dog' GROUP BY r.phase"
    ).fetchall()
    gender_rows = db.execute(
        "SELECT gender, COUNT(*) c FROM participants WHERE gender IS NOT NULL GROUP BY gender ORDER BY gender"
    ).fetchall()
    education_rows = db.execute(
        "SELECT education, COUNT(*) c FROM participants WHERE education IS NOT NULL GROUP BY education ORDER BY education"
    ).fetchall()
    age_rows = db.execute(
        "SELECT age, COUNT(*) c FROM participants WHERE age IN ('20岁及以下','40岁及以下','40岁以上') GROUP BY age ORDER BY age"
    ).fetchall()
    gender_map = {row['gender']: row['c'] for row in gender_rows}
    education_map = {row['education']: row['c'] for row in education_rows}
    age_map = {row['age']: row['c'] for row in age_rows}

    def format_pct(value):
        return f"{value * 100:.1f}%" if value is not None else '—'

    def build_demo_section(title, field, labels, count_map):
        if field not in {'gender', 'education', 'age'}:
            raise ValueError('invalid demographic field')
        phase_rows = db.execute(
            f"SELECT label, phase, COUNT(*) response_count, AVG(object_low) object_low, AVG(object_high) object_high, AVG(bio_low) bio_low, AVG(bio_high) bio_high "
            "FROM ("
            f"  SELECT p.{field} label, p.id participant_id, r.phase, "
            "  MAX(CASE WHEN t.trial_type = 'object' THEN r.category_correct END) object_low, "
            "  MAX(CASE WHEN t.trial_type = 'object' THEN r.material_correct END) object_high, "
            "  MAX(CASE WHEN t.trial_type = 'dog' THEN r.category_correct END) bio_low, "
            "  MAX(CASE WHEN t.trial_type = 'dog' THEN r.material_correct END) bio_high "
            "  FROM responses r JOIN trials t ON r.trial_id = t.id JOIN participants p ON t.participant_id = p.id "
            f"  WHERE p.{field} IS NOT NULL AND r.phase IN ('immediate','day','week','2week') GROUP BY p.{field}, p.id, r.phase"
            ") WHERE object_low IS NOT NULL AND object_high IS NOT NULL AND bio_low IS NOT NULL AND bio_high IS NOT NULL "
            "GROUP BY label, phase"
        ).fetchall()
        phase_map = {(row['label'], row['phase']): row for row in phase_rows}

        def cells(label, key, is_percent=False):
            values = []
            for phase in PHASE_ORDER:
                row = phase_map.get((label, phase))
                value = row[key] if row else None
                values.append(format_pct(value) if is_percent else (value or 0))
            return values

        groups = []
        metric_defs = [
            ('完整次数', 'response_count', False),
            ('物体低频', 'object_low', True),
            ('物体高频', 'object_high', True),
            ('生物低频', 'bio_low', True),
            ('生物高频', 'bio_high', True),
        ]
        for label in labels:
            groups.append({
                'label': label,
                'participant_count': count_map.get(label, 0),
                'metrics': [
                    {'label': metric_label, 'cells': cells(label, key, is_percent)}
                    for metric_label, key, is_percent in metric_defs
                ],
            })
        return {'title': title, 'groups': groups}

    demo_sections = [
        build_demo_section('性别', 'gender', GENDERS, gender_map),
        build_demo_section('年龄段', 'age', AGE_GROUPS, age_map),
        build_demo_section('学历', 'education', EDUCATIONS, education_map),
    ]
    obj_acc_map = {r['phase']: {'cat': r['ac'], 'mat': r['am']} for r in obj_accuracy}
    dog_acc_map = {r['phase']: {'cat': r['ac'], 'mat': r['am']} for r in dog_accuracy}

    def avg2(a, b):
        if a is None and b is None:
            return None
        a = a or 0
        b = b or 0
        return (a + b) / 2

    total_acc = {}
    for ph in PHASE_ORDER:
        o = obj_acc_map.get(ph, {})
        d = dog_acc_map.get(ph, {})
        total_acc[ph] = {
            'low': avg2(o.get('cat'), d.get('cat')),
            'high': avg2(o.get('mat'), d.get('mat')),
        }
    chart_data = {
        'cat': [
            round(total_acc['immediate']['low'] * 100, 1) if total_acc.get('immediate', {}).get('low') is not None else None,
            round(total_acc['day']['low'] * 100, 1) if total_acc.get('day', {}).get('low') is not None else None,
            round(total_acc['week']['low'] * 100, 1) if total_acc.get('week', {}).get('low') is not None else None,
            round(total_acc['2week']['low'] * 100, 1) if total_acc.get('2week', {}).get('low') is not None else None,
        ],
        'mat': [
            round(total_acc['immediate']['high'] * 100, 1) if total_acc.get('immediate', {}).get('high') is not None else None,
            round(total_acc['day']['high'] * 100, 1) if total_acc.get('day', {}).get('high') is not None else None,
            round(total_acc['week']['high'] * 100, 1) if total_acc.get('week', {}).get('high') is not None else None,
            round(total_acc['2week']['high'] * 100, 1) if total_acc.get('2week', {}).get('high') is not None else None,
        ],
    }
    recent = db.execute("SELECT code, nickname, gender, age, education, created_at FROM participants ORDER BY created_at DESC, id DESC LIMIT 10").fetchall()
    detail_rows = db.execute(
        "SELECT "
        "p.code, p.nickname, p.gender, p.age, p.education, t.id trial_id, t.trial_type, t.category, t.material, r.phase, "
        "CAST((julianday(r.responded_at) - julianday(t.study_started_at)) * 86400 AS INTEGER) AS elapsed_seconds, "
        "r.category_correct, r.material_correct, r.resp_category, r.resp_material "
        "FROM participants p "
        "JOIN trials t ON t.participant_id = p.id "
        "LEFT JOIN responses r ON r.trial_id = t.id "
        "ORDER BY p.created_at DESC, p.id DESC, t.trial_order ASC, t.id ASC, r.responded_at ASC, r.id ASC"
    ).fetchall()

    per_user = []
    row_map = {}

    def default_phase():
        return {'elapsed_label': '—', 'cat_ok': None, 'mat_ok': None, 'resp_cat': None, 'resp_mat': None}

    for row in detail_rows:
        code = row['code']
        if code not in row_map:
            row_map[code] = {
                'code': row['code'],
                'nickname': row['nickname'],
                'gender': row['gender'],
                'age': row['age'],
                'education': row['education'],
                'object': {**{'category': '', 'material': ''}, **{phase: default_phase() for phase in PHASE_ORDER}},
                'dog':    {**{'category': '', 'material': ''}, **{phase: default_phase() for phase in PHASE_ORDER}},
            }
            per_user.append(row_map[code])
        tt = row['trial_type']
        if tt in ('object', 'dog'):
            row_map[code][tt]['category'] = row['category']
            row_map[code][tt]['material'] = row['material']
            if row['phase'] in PHASES:
                row_map[code][tt][row['phase']] = {
                    'elapsed_label': elapsed_label(row['elapsed_seconds']),
                    'cat_ok': row['category_correct'],
                    'mat_ok': row['material_correct'],
                    'resp_cat': row['resp_category'],
                    'resp_mat': row['resp_material'],
                }

    stats = {
        'total_participants': total,
        'phase_counts': phase_counts,
        'accuracy': accuracy,
        'recent': recent,
        'demo_sections': demo_sections,
    }
    return render_template(
        'admin.html',
        stats=stats,
        obj_acc_map=obj_acc_map,
        dog_acc_map=dog_acc_map,
        total_acc=total_acc,
        per_user=per_user,
        obj_phase_counts={r['phase']: r['c'] for r in obj_phase_counts},
        dog_phase_counts={r['phase']: r['c'] for r in dog_phase_counts},
        chart_data=chart_data,
        diffusion_charts=build_diffusion_charts(db),
        debug_skip=DEBUG_SKIP_WINDOWS,
    )


@app.get('/admin/export.csv')
def export_csv():
    if not admin_ok():
        return admin_fail()
    rows = get_db().execute(
        "SELECT p.code participant_code, p.nickname, p.gender, p.age age_group, p.education, t.trial_type, t.category, t.material, r.phase, r.responded_at, r.resp_category, r.resp_material, r.resp_col, r.resp_row, r.category_correct, r.material_correct, r.response_time_ms "
        "FROM responses r JOIN trials t ON r.trial_id=t.id JOIN participants p ON t.participant_id=p.id ORDER BY r.id"
    ).fetchall()
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(['participant_code', 'nickname', 'gender', 'age_group', 'education', 'trial_type', 'category', 'material', 'phase', 'responded_at', 'resp_category', 'resp_material', 'resp_col', 'resp_row', 'category_correct', 'material_correct', 'response_time_ms'])
    for row in rows:
        writer.writerow([row[k] for k in row.keys()])
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=responses.csv'})


@app.get('/api/thumbs')
def thumbs():
    avail_cats, avail_mats = scan_available()
    data = {}
    for category in avail_cats:
        for material in avail_mats:
            image_dir = Path(app.static_folder or 'static') / 'images' / category / material
            files = [p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}] if image_dir.exists() else []
            if files:
                img = Image.open(random.choice(files)).convert('RGB')
            else:
                img = Image.new('RGB', (512, 512), MATERIAL_COLORS[material])
                draw, font = ImageDraw.Draw(img), load_font()
                text = f"{material}\n{category}"
                box = draw.multiline_textbbox((0, 0), text, font=font, align='center')
                pos = ((512 - (box[2] - box[0])) / 2, (512 - (box[3] - box[1])) / 2)
                draw.multiline_text(pos, text, fill='#1f2933', font=font, align='center', spacing=10)
            img = img.resize((300, 300), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format='JPEG', quality=40)
            data[f'{category}_{material}'] = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    resp = jsonify(data)
    resp.headers['Cache-Control'] = 'max-age=3600'
    return resp


@app.get('/api/thumbs-dog')
def thumbs_dog():
    avail_breeds, avail_bgs = scan_available_dog()
    data = {}
    for breed in avail_breeds:
        for bg in avail_bgs:
            image_dir = Path(app.static_folder or 'static') / 'images_dog' / breed / bg
            files = [p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}] if image_dir.exists() else []
            key = f'{breed}_{bg}'
            if files:
                img = Image.open(random.choice(files)).convert('RGB')
                img = img.resize((300, 300), Image.LANCZOS)
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=40)
                data[key] = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
    resp = jsonify(data)
    resp.headers['Cache-Control'] = 'max-age=3600'
    return resp


@app.get('/api/study-img/<path:relpath>')
def study_img(relpath: str):
    if not (relpath.startswith('images/') or relpath.startswith('images_dog/')):
        return Response('Not found', 404)
    full_path = Path(app.static_folder or 'static') / relpath
    if not full_path.exists() or not full_path.is_file():
        return Response('Not found', 404)
    img = Image.open(full_path).convert('RGB')
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=70)
    buf.seek(0)
    resp = send_file(buf, mimetype='image/jpeg')
    resp.headers['Cache-Control'] = 'max-age=3600'
    return resp


def load_font():
    for name in ['Arial.ttf', '/System/Library/Fonts/Supplemental/Arial.ttf', '/Library/Fonts/Arial.ttf']:
        try:
            return ImageFont.truetype(name, 42)
        except Exception:
            pass
    return ImageFont.load_default()


@app.get('/placeholder/<cat>/<mat>')
def placeholder(cat: str, mat: str):
    if cat not in CATEGORIES or mat not in MATERIALS:
        return Response('Not found', 404)
    img = Image.new('RGB', (512, 512), MATERIAL_COLORS[mat])
    draw, font = ImageDraw.Draw(img), load_font()
    text = f"{mat}\n{cat}"
    box = draw.multiline_textbbox((0, 0), text, font=font, align='center')
    pos = ((512 - (box[2] - box[0])) / 2, (512 - (box[3] - box[1])) / 2)
    draw.multiline_text(pos, text, fill='#1f2933', font=font, align='center', spacing=10)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


ensure_db()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
