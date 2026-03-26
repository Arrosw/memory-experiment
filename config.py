CATEGORIES = ['bowl', 'cup', 'plate', 'vase', 'box', 'pitcher']
MATERIALS = ['wood', 'plastic', 'metal', 'glass', 'ceramic', 'stone']
ANIMALS = ['Tiger', 'Panda', 'Eagle', 'Whale', 'Fox', 'Bear', 'Wolf', 'Hawk', 'Deer', 'Lynx',
           'Crow', 'Dove', 'Swan', 'Seal', 'Orca', 'Moth', 'Frog', 'Newt', 'Crab', 'Wren']
TRIALS_PER_PARTICIPANT = 1
STUDY_DURATION_SECONDS = 5
WEEK_WINDOW = (5, 9)
MONTH_WINDOW = (25, 40)
DEBUG_SKIP_WINDOWS = False   # 设为 True 可跳过时间窗口，仅用于本地测试
ADMIN_USER = 'admin'
ADMIN_PASS = 'memory2026'
DB_PATH = 'data/experiment.db'


def init_db(db):
    db.executescript("""
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        nickname TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS trials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id INTEGER NOT NULL REFERENCES participants(id),
        category TEXT NOT NULL,
        material TEXT NOT NULL,
        trial_order INTEGER NOT NULL,
        study_started_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trial_id INTEGER NOT NULL REFERENCES trials(id),
        phase TEXT NOT NULL CHECK(phase IN ('immediate','week','month')),
        responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resp_category TEXT,
        resp_material TEXT,
        resp_col INTEGER,
        resp_row INTEGER,
        category_correct INTEGER CHECK(category_correct IN (0,1)),
        material_correct INTEGER CHECK(material_correct IN (0,1)),
        response_time_ms INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_part_code ON participants(code);
    CREATE INDEX IF NOT EXISTS idx_trials_part ON trials(participant_id);
    CREATE INDEX IF NOT EXISTS idx_resp_trial ON responses(trial_id);
    """)
    db.commit()
