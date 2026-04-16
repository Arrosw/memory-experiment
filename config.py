CATEGORIES = ['bowl', 'mug', 'pitcher', 'tray', 'vase']
MATERIALS = ['wood', 'stone', 'ceramic', 'metal', 'glass']
DOG_BREEDS = ['german shepherd', 'golden retriever', 'husky', 'labrador', 'shiba inu']
DOG_BACKGROUNDS = ['dry_grassy_ground', 'dusty_ground', 'fine_gravel_ground', 'sand_ground', 'slightly_damp_dirt']
GENDERS = ['男', '女']
AGE_GROUPS = ['20岁及以下', '40岁及以下', '40岁以上']
EDUCATIONS = ['初中及以下', '高中/中专', '本科及以上']
ANIMALS = ['Tiger', 'Panda', 'Eagle', 'Whale', 'Fox', 'Bear', 'Wolf', 'Hawk', 'Deer', 'Lynx',
           'Crow', 'Dove', 'Swan', 'Seal', 'Orca', 'Moth', 'Frog', 'Newt', 'Crab', 'Wren']
TRIALS_PER_PARTICIPANT = 1
STUDY_DURATION_SECONDS = 3
DAY_WINDOW = (1, 2)
WEEK_WINDOW = (7, 9)
WEEK2_WINDOW = (14, 16)
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
        gender TEXT CHECK(gender IN ('男','女')),
        age TEXT CHECK(age IN ('20岁及以下','40岁及以下','40岁以上')),
        education TEXT CHECK(education IN ('初中及以下','高中/中专','本科及以上')),
        created_at TIMESTAMP
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
        phase TEXT NOT NULL CHECK(phase IN ('immediate','day','week','2week')),
        responded_at TIMESTAMP,
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
    for sql in (
        "ALTER TABLE participants ADD COLUMN gender TEXT CHECK(gender IN ('男','女'))",
        "ALTER TABLE participants ADD COLUMN age TEXT CHECK(age IN ('20岁及以下','40岁及以下','40岁以上'))",
        "ALTER TABLE participants ADD COLUMN education TEXT CHECK(education IN ('初中及以下','高中/中专','本科及以上'))",
    ):
        try:
            db.execute(sql)
            db.commit()
        except Exception:
            pass  # column already exists
    try:
        db.execute("""
            UPDATE participants
            SET age = CASE
                WHEN CAST(age AS INTEGER) <= 20 THEN '20岁及以下'
                WHEN CAST(age AS INTEGER) <= 40 THEN '40岁及以下'
                ELSE '40岁以上'
            END
            WHERE age IS NOT NULL
              AND age NOT IN ('20岁及以下','40岁及以下','40岁以上')
              AND CAST(age AS TEXT) != ''
              AND CAST(age AS TEXT) NOT GLOB '*[^0-9]*'
        """)
        db.commit()
    except Exception:
        db.rollback()
    schema_row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='responses'").fetchone()
    if schema_row and ",'3day'," in schema_row['sql']:
        try:
            db.execute("ALTER TABLE responses RENAME TO responses_old")
            db.execute("""CREATE TABLE responses (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              trial_id INTEGER NOT NULL REFERENCES trials(id),
              phase TEXT NOT NULL CHECK(phase IN ('immediate','day','week','2week')),
              responded_at TIMESTAMP,
              resp_category TEXT,
              resp_material TEXT,
              resp_col INTEGER,
              resp_row INTEGER,
              category_correct INTEGER CHECK(category_correct IN (0,1)),
              material_correct INTEGER CHECK(material_correct IN (0,1)),
              response_time_ms INTEGER
          )""")
            db.execute("INSERT INTO responses SELECT * FROM responses_old WHERE phase IN ('immediate','day','week','2week')")
            db.execute("DROP TABLE responses_old")
            db.execute("CREATE INDEX IF NOT EXISTS idx_resp_trial ON responses(trial_id)")
            db.commit()
        except Exception:
            db.rollback()
