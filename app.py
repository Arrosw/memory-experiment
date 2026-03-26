import base64
import csv
import os
import random
import sqlite3
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path

from flask import Flask, Response, g, jsonify, redirect, render_template, request, send_file, session, url_for
from PIL import Image, ImageDraw, ImageFont

from config import ADMIN_PASS, ADMIN_USER, ANIMALS, CATEGORIES, DB_PATH, DEBUG_SKIP_WINDOWS, MATERIALS, MONTH_WINDOW, STUDY_DURATION_SECONDS, TRIALS_PER_PARTICIPANT, WEEK_WINDOW, init_db

MATERIAL_COLORS = {
    'wood': '#D2A679', 'plastic': '#4FC3F7', 'metal': '#B0BEC5',
    'glass': '#E0F7FA', 'ceramic': '#FFCCBC', 'stone': '#9E9E9E',
}
PHASES = {'immediate', 'week', 'month'}
app = Flask(__name__)
app.secret_key = os.urandom(24).hex()


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
    counts = db.execute("SELECT category, material, COUNT(*) c FROM trials GROUP BY category, material").fetchall()
    count_map = {(r['category'], r['material']): r['c'] for r in counts}
    all_combos = [(c, m) for c in CATEGORIES for m in MATERIALS]
    random.shuffle(all_combos)
    all_combos.sort(key=lambda x: count_map.get(x, 0))
    selected = all_combos[:TRIALS_PER_PARTICIPANT]
    for order, (cat, mat) in enumerate(selected, 1):
        db.execute("INSERT INTO trials (participant_id, category, material, trial_order) VALUES (?,?,?,?)", (participant_id, cat, mat, order))
    db.commit()


def parse_ts(value):
    if not value:
        return None
    return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)


def get_phase_row(db, participant_id: int):
    trials = db.execute("SELECT * FROM trials WHERE participant_id=? ORDER BY trial_order, id", (participant_id,)).fetchall()
    now = datetime.now(timezone.utc)
    for trial in trials:
        done = {r['phase'] for r in db.execute("SELECT phase FROM responses WHERE trial_id=?", (trial['id'],)).fetchall()}
        if not trial['study_started_at']:
            return trial, 'study'
        if 'immediate' not in done:
            return trial, 'immediate'
        days = (now - parse_ts(trial['study_started_at'])).days
        if 'week' not in done and (DEBUG_SKIP_WINDOWS or WEEK_WINDOW[0] <= days <= WEEK_WINDOW[1]):
            return trial, 'week'
        if 'month' not in done and (DEBUG_SKIP_WINDOWS or MONTH_WINDOW[0] <= days <= MONTH_WINDOW[1]):
            return trial, 'month'
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
    return render_template('index.html')


@app.post('/register')
def register():
    db = get_db()
    code = generate_code(db)
    db.execute("INSERT INTO participants (code, nickname) VALUES (?,?)", (code, request.form.get('nickname', '').strip() or None))
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
    img_url = image_url(trial['category'], trial['material'], 'immediate')
    return render_template('study.html', image_url=img_url, duration=STUDY_DURATION_SECONDS, code=code)


@app.post('/api/study-start')
def study_start():
    pid = participant_id()
    if not pid:
        return jsonify({'ok': False}), 401
    trial = current_trial_for_study(get_db(), pid)
    if trial:
        get_db().execute("UPDATE trials SET study_started_at=COALESCE(study_started_at, CURRENT_TIMESTAMP) WHERE id=?", (trial['id'],))
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
    x_order = list(range(len(MATERIALS)))
    y_order = list(range(len(CATEGORIES)))
    random.shuffle(x_order)
    random.shuffle(y_order)
    session['recall_x_order'] = x_order
    session['recall_y_order'] = y_order
    return render_template('recall.html', phase=phase, x_order=x_order, y_order=y_order)


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
    if xi not in range(6) or yi not in range(6):
        return jsonify({'next_url': url_for('recall', phase=phase)}), 400
    x_order = session.get('recall_x_order', list(range(6)))
    y_order = session.get('recall_y_order', list(range(6)))
    col = x_order[xi]   # actual MATERIALS index
    row = y_order[yi]   # actual CATEGORIES index
    resp_material = MATERIALS[col]
    resp_category = CATEGORIES[row]
    db.execute(
        "INSERT INTO responses (trial_id, phase, resp_category, resp_material, resp_col, resp_row, category_correct, material_correct, response_time_ms) VALUES (?,?,?,?,?,?,?,?,?)",
        (trial['id'], phase, resp_category, resp_material, col, row, int(resp_category == trial['category']), int(resp_material == trial['material']), data.get('response_time_ms'))
    )
    db.commit()
    return jsonify({'next_url': url_for('done', phase=phase)})


@app.get('/done')
def done():
    pid = participant_id()
    code = ''
    phase = request.args.get('phase', 'immediate')
    next_date = ''
    if pid:
        db = get_db()
        row = db.execute("SELECT code FROM participants WHERE id=?", (pid,)).fetchone()
        code = row['code'] if row else ''
        trial_row = db.execute(
            "SELECT study_started_at FROM trials WHERE participant_id=? ORDER BY id LIMIT 1", (pid,)
        ).fetchone()
        if trial_row and trial_row['study_started_at']:
            started = parse_ts(trial_row['study_started_at'])
            from datetime import timedelta
            if phase == 'immediate':
                target = started + timedelta(days=WEEK_WINDOW[0])
                next_date = f"约{target.month}月{target.day}日"
            elif phase == 'week':
                target = started + timedelta(days=MONTH_WINDOW[0])
                next_date = f"约{target.month}月{target.day}日"
    return render_template('done.html', code=code, next_date=next_date, phase=phase)


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
    acc_map = {r['phase']: {'cat': r['ac'], 'mat': r['am']} for r in accuracy}
    chart_data = {
        'cat': [
            round(acc_map['immediate']['cat'] * 100, 1) if acc_map.get('immediate', {}).get('cat') is not None else None,
            round(acc_map['week']['cat'] * 100, 1) if acc_map.get('week', {}).get('cat') is not None else None,
            round(acc_map['month']['cat'] * 100, 1) if acc_map.get('month', {}).get('cat') is not None else None,
        ],
        'mat': [
            round(acc_map['immediate']['mat'] * 100, 1) if acc_map.get('immediate', {}).get('mat') is not None else None,
            round(acc_map['week']['mat'] * 100, 1) if acc_map.get('week', {}).get('mat') is not None else None,
            round(acc_map['month']['mat'] * 100, 1) if acc_map.get('month', {}).get('mat') is not None else None,
        ],
    }
    recent = db.execute("SELECT code, nickname, created_at FROM participants ORDER BY created_at DESC, id DESC LIMIT 10").fetchall()
    detail_rows = db.execute(
        "SELECT "
        "p.code, p.nickname, t.id trial_id, t.category, t.material, r.phase, "
        "CAST((julianday(r.responded_at) - julianday(t.study_started_at)) * 86400 AS INTEGER) AS elapsed_seconds, "
        "r.category_correct, r.material_correct "
        "FROM participants p "
        "JOIN trials t ON t.participant_id = p.id "
        "LEFT JOIN responses r ON r.trial_id = t.id "
        "ORDER BY p.created_at DESC, p.id DESC, t.trial_order ASC, t.id ASC, r.responded_at ASC, r.id ASC"
    ).fetchall()

    per_user = []
    row_map = {}
    for row in detail_rows:
        key = (row['code'], row['trial_id'])
        if key not in row_map:
            row_map[key] = {
                'code': row['code'],
                'nickname': row['nickname'],
                'category': row['category'],
                'material': row['material'],
                'immediate': {'elapsed_label': '—', 'cat_ok': None, 'mat_ok': None},
                'week': {'elapsed_label': '—', 'cat_ok': None, 'mat_ok': None},
                'month': {'elapsed_label': '—', 'cat_ok': None, 'mat_ok': None},
            }
            per_user.append(row_map[key])
        if row['phase'] in PHASES:
            row_map[key][row['phase']] = {
                'elapsed_label': elapsed_label(row['elapsed_seconds']),
                'cat_ok': row['category_correct'],
                'mat_ok': row['material_correct'],
            }

    stats = {'total_participants': total, 'phase_counts': phase_counts, 'accuracy': accuracy, 'recent': recent}
    return render_template('admin.html', stats=stats, per_user=per_user, chart_data=chart_data, debug_skip=DEBUG_SKIP_WINDOWS)


@app.get('/admin/export.csv')
def export_csv():
    if not admin_ok():
        return admin_fail()
    rows = get_db().execute(
        "SELECT p.code participant_code, p.nickname, t.category, t.material, r.phase, r.responded_at, r.resp_category, r.resp_material, r.resp_col, r.resp_row, r.category_correct, r.material_correct, r.response_time_ms "
        "FROM responses r JOIN trials t ON r.trial_id=t.id JOIN participants p ON t.participant_id=p.id ORDER BY r.id"
    ).fetchall()
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(['participant_code', 'nickname', 'category', 'material', 'phase', 'responded_at', 'resp_category', 'resp_material', 'resp_col', 'resp_row', 'category_correct', 'material_correct', 'response_time_ms'])
    for row in rows:
        writer.writerow([row[k] for k in row.keys()])
    return Response(buf.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=responses.csv'})


@app.get('/api/thumbs')
def thumbs():
    data = {}
    for category in CATEGORIES:
        for material in MATERIALS:
            path = Path(app.static_folder or 'static') / 'images' / category / material / 'thumb.png'
            data[f'{category}_{material}'] = f"/static/images/{category}/{material}/thumb.png" if path.exists() else url_for('placeholder', cat=category, mat=material)
    return jsonify(data)


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
    app.run(debug=True, host='0.0.0.0')
