CATEGORIES = ['bowl', 'mug', 'pitcher', 'tray', 'vase']
MATERIALS = ['wood', 'stone', 'ceramic', 'metal', 'glass']
DOG_BREEDS = ['german shepherd', 'golden retriever', 'husky', 'labrador', 'shiba inu']
DOG_BACKGROUNDS = ['dry_grassy_ground', 'dusty_ground', 'fine_gravel_ground', 'sand_ground', 'slightly_damp_dirt']
ANIMALS = ['Tiger', 'Panda', 'Eagle', 'Whale', 'Fox', 'Bear', 'Wolf', 'Hawk', 'Deer', 'Lynx',
           'Crow', 'Dove', 'Swan', 'Seal', 'Orca', 'Moth', 'Frog', 'Newt', 'Crab', 'Wren']
TRIALS_PER_PARTICIPANT = 1
STUDY_DURATION_SECONDS = 3
DAY_WINDOW = (1, 2)
DAY3_WINDOW = (3, 5)
WEEK_WINDOW = (7, 9)
WEEK2_WINDOW = (14, 16)
WEEK3_WINDOW = (21, 23)
WEEK4_WINDOW = (28, 30)
DEBUG_SKIP_WINDOWS = False  # 设为 True 可跳过时间窗口，仅用于本地测试
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
        trial_type TEXT NOT NULL DEFAULT 'object',
        study_started_at TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trial_id INTEGER NOT NULL REFERENCES trials(id),
        phase TEXT NOT NULL CHECK(phase IN ('immediate','day','3day','week','2week','3week','4week')),
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
    try:
        db.execute("ALTER TABLE trials ADD COLUMN trial_type TEXT NOT NULL DEFAULT 'object'")
        db.commit()
    except Exception:
        pass  # column already exists
    schema_row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='responses'").fetchone()
    if schema_row and "'3day'" not in schema_row['sql']:
        try:
            db.execute("ALTER TABLE responses RENAME TO responses_old")
            db.execute("""CREATE TABLE responses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trial_id INTEGER NOT NULL REFERENCES trials(id),
              phase TEXT NOT NULL CHECK(phase IN ('immediate','day','3day','week','2week','3week','4week')),
              responded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              resp_category TEXT,
              resp_material TEXT,
              resp_col INTEGER,
              resp_row INTEGER,
              category_correct INTEGER CHECK(category_correct IN (0,1)),
              material_correct INTEGER CHECK(material_correct IN (0,1)),
              response_time_ms INTEGER
          )""")
            db.execute("INSERT INTO responses SELECT * FROM responses_old")
            db.execute("DROP TABLE responses_old")
            db.execute("CREATE INDEX IF NOT EXISTS idx_resp_trial ON responses(trial_id)")
            db.commit()
        except Exception:
            db.rollback()
