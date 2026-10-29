"""db.py — قاعدة البيانات والبيانات الأولية."""
import sqlite3, os, random
from datetime import datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS clubs (
  club_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, short_name TEXT,
  reputation INTEGER DEFAULT 50, budget REAL DEFAULT 5000000,
  wage_budget REAL DEFAULT 200000, stadium_capacity INTEGER DEFAULT 20000,
  ticket_price REAL DEFAULT 15, is_user_club INTEGER DEFAULT 0,
  tactic TEXT DEFAULT 'balanced'
);
CREATE TABLE IF NOT EXISTS players (
  player_id INTEGER PRIMARY KEY AUTOINCREMENT,
  first_name TEXT NOT NULL, last_name TEXT NOT NULL,
  position TEXT NOT NULL, age INTEGER NOT NULL,
  overall_rating INTEGER NOT NULL, potential_rating INTEGER NOT NULL,
  pace INTEGER DEFAULT 60, shooting INTEGER DEFAULT 60,
  passing INTEGER DEFAULT 60, defending INTEGER DEFAULT 60,
  physical INTEGER DEFAULT 60, club_id INTEGER, is_starter INTEGER DEFAULT 0,
  is_injured INTEGER DEFAULT 0, injury_until TEXT,
  contract_years INTEGER DEFAULT 3, wage REAL DEFAULT 5000,
  market_value REAL DEFAULT 50000, morale INTEGER DEFAULT 70,
  is_youth INTEGER DEFAULT 0, training_focus TEXT DEFAULT NULL,
  training_progress INTEGER DEFAULT 0, seasons_at_club INTEGER DEFAULT 0,
  contract_warned INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS player_stats (
  player_id INTEGER PRIMARY KEY,
  appearances INTEGER DEFAULT 0, goals INTEGER DEFAULT 0,
  assists INTEGER DEFAULT 0, minutes INTEGER DEFAULT 0,
  motm INTEGER DEFAULT 0, clean_sheets INTEGER DEFAULT 0,
  yellow_cards INTEGER DEFAULT 0, red_cards INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS seasons (
  season_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, is_active INTEGER DEFAULT 1,
  champion_club_id INTEGER, cup_winner_id INTEGER,
  continental_winner_id INTEGER, top_scorer_id INTEGER
);
CREATE TABLE IF NOT EXISTS matches (
  match_id INTEGER PRIMARY KEY AUTOINCREMENT,
  season_id INTEGER, competition TEXT DEFAULT 'league',
  round_name TEXT, match_date TEXT NOT NULL,
  home_club_id INTEGER NOT NULL, away_club_id INTEGER NOT NULL,
  home_goals INTEGER DEFAULT 0, away_goals INTEGER DEFAULT 0,
  status TEXT DEFAULT 'scheduled', attendance INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS match_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_id INTEGER NOT NULL, minute INTEGER NOT NULL,
  event_type TEXT NOT NULL, player_id INTEGER,
  club_id INTEGER, detail TEXT
);
CREATE TABLE IF NOT EXISTS board_status (
  club_id INTEGER PRIMARY KEY,
  confidence INTEGER DEFAULT 80,
  objective TEXT DEFAULT 'المنافسة على صدارة الدوري',
  last_evaluated TEXT
);
CREATE TABLE IF NOT EXISTS finances_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  club_id INTEGER NOT NULL, date TEXT NOT NULL,
  amount REAL NOT NULL, description TEXT, balance_after REAL
);
CREATE TABLE IF NOT EXISTS season_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, season_id INTEGER, season_name TEXT,
  league_champion TEXT, cup_winner TEXT, continental_winner TEXT,
  top_scorer TEXT, user_position INTEGER, user_club TEXT
);
CREATE TABLE IF NOT EXISTS achievements (
  id INTEGER PRIMARY KEY AUTOINCREMENT, club_id INTEGER NOT NULL,
  achievement_key TEXT NOT NULL, name TEXT NOT NULL, description TEXT,
  unlocked_date TEXT NOT NULL, season_id INTEGER,
  UNIQUE(club_id, achievement_key)
);
CREATE TABLE IF NOT EXISTS transfer_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
  player_name TEXT, from_club TEXT, to_club TEXT,
  fee REAL, move_type TEXT
);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY, value TEXT
);
CREATE TABLE IF NOT EXISTS game_state (
  id INTEGER PRIMARY KEY CHECK (id=1),
  current_date TEXT NOT NULL, active_season_id INTEGER,
  user_club_id INTEGER DEFAULT 1, last_weekly_process TEXT
);
CREATE INDEX IF NOT EXISTS idx_match_date ON matches(match_date, status);
CREATE INDEX IF NOT EXISTS idx_player_club ON players(club_id, is_starter);
"""

CLUBS = [
    ("الترجي الرياضي التونسي", "الترجي", 80, 8000000, 300000, 60000, 20),
    ("النجم الرياضي الساحلي", "النجم", 75, 5500000, 220000, 25000, 15),
    ("النادي الإفريقي", "الإفريقي", 72, 4500000, 200000, 40000, 15),
    ("النادي الرياضي الصفاقسي", "الصفاقسي", 70, 4000000, 180000, 25000, 12),
    ("الاتحاد الرياضي المنستيري", "المنستيري", 65, 2500000, 120000, 15000, 10),
    ("النادي الرياضي البنزرتي", "البنزرتي", 62, 2000000, 100000, 18000, 10),
    ("الملعب التونسي", "الملعب", 60, 1800000, 90000, 12000, 8),
    ("مستقبل قابس", "قابس", 55, 1200000, 70000, 10000, 8),
]
FIRST = ["محمد","أمين","يوسف","حمزة","أنس","معز","سيف","خالد","إلياس",
         "مالك","زياد","رائد","كريم","نبيل","طه","صابر","وليد","بسام",
         "مراد","حاتم","عصام","شادي","رياض","فراس"]
LAST = ["بن رمضان","الجزيري","المساكني","العبيدي","الشعلالي","بالعيد",
        "الطبوبي","الخنيسي","البجاوي","العياري","بن سعيد","الطرابلسي",
        "الحمروني","العيوني","المبروك","الزيتوني","بن علي","الجبالي"]
POS_BASE = ["DEF","DEF","DEF","MID","MID","MID","FWD","FWD","DEF","MID"]
RATING_RANGES = [(72,85),(68,80),(65,78),(62,76),(58,72),(55,70),(52,68),(48,65)]


def _ensure_column(cur, table, col, definition):
    cur.execute(f"PRAGMA table_info({table})")
    if col not in [r[1] for r in cur.fetchall()]:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")


def _migrate(cur):
    for col, d in [
        ("training_focus", "TEXT DEFAULT NULL"),
        ("training_progress", "INTEGER DEFAULT 0"),
        ("seasons_at_club", "INTEGER DEFAULT 0"),
        ("contract_warned", "INTEGER DEFAULT 0"),
    ]:
        _ensure_column(cur, "players", col, d)
    _ensure_column(cur, "game_state", "last_weekly_process", "TEXT")


def _seed(cur):
    for i, (name, short, rep, bud, wage, cap, price) in enumerate(CLUBS):
        cur.execute("""INSERT INTO clubs (name,short_name,reputation,budget,
            wage_budget,stadium_capacity,ticket_price,is_user_club)
            VALUES (?,?,?,?,?,?,?,?);""",
            (name, short, rep, bud, wage, cap, price, 1 if i == 0 else 0))
    cur.execute("INSERT INTO seasons (name,is_active) VALUES ('موسم 2026/2027',1);")
    cur.execute("SELECT club_id FROM clubs ORDER BY club_id;")
    club_ids = [r[0] for r in cur.fetchall()]
    for ci, cid in enumerate(club_ids):
        lo, hi = RATING_RANGES[ci]
        for i in range(18):
            fn, ln = random.choice(FIRST), random.choice(LAST)
            pos = "GK" if i == 0 else POS_BASE[i % len(POS_BASE)]
            age = random.randint(18, 34)
            ovr = random.randint(lo, hi)
            if age >= 30: ovr = max(lo, ovr - 3)
            pot = min(94, ovr + random.randint(0, 10))
            val = max(20000, ovr * ovr * 180)
            wage = max(3000, int(ovr * 120))
            cur.execute("""INSERT INTO players (first_name,last_name,position,
                age,overall_rating,potential_rating,pace,shooting,passing,
                defending,physical,club_id,is_starter,wage,market_value)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);""",
                (fn, ln, pos, age, ovr, pot,
                 min(99, ovr + random.randint(-8, 8)),
                 min(99, ovr + random.randint(-8, 8) + (10 if pos=="FWD" else 0)),
                 min(99, ovr + random.randint(-8, 8) + (5 if pos=="MID" else 0)),
                 min(99, ovr + random.randint(-8, 8) + (12 if pos in("DEF","GK") else 0)),
                 min(99, ovr + random.randint(-10, 6)),
                 cid, 1 if i < 11 else 0, wage, val))
            cur.execute("INSERT INTO player_stats (player_id) VALUES (?)",
                        (cur.lastrowid,))
        cur.execute("""INSERT OR IGNORE INTO board_status (club_id,confidence,objective)
            VALUES (?,80,'المنافسة على صدارة الدوري');""", (cid,))
    today = datetime.now().strftime("%Y-%m-%d")
    cur.execute("""INSERT OR REPLACE INTO game_state
        (id,current_date,active_season_id,user_club_id,last_weekly_process)
        VALUES (1,?,1,1,?);""", (today, today))
    for k, v in [("font_scale","1.0"),("auto_save","1"),
                 ("confirm_delete","1"),("confirm_release","1"),
                 ("welcome_shown","0")]:
        cur.execute("INSERT OR IGNORE INTO settings (key,value) VALUES (?,?);",
                    (k, v))
    return club_ids


def _schedule_league(cur, season_id, club_ids, start_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    offset = 0
    n = len(club_ids)
    fixtures = []
    teams = list(club_ids)
    for rnd in range(n - 1):
        for j in range(n // 2):
            a, b = teams[j], teams[n - 1 - j]
            fixtures.append((a, b) if rnd % 2 == 0 else (b, a))
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    fixtures += [(b, a) for (a, b) in fixtures]
    for home, away in fixtures:
        d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        cur.execute("""INSERT INTO matches (season_id,competition,round_name,
            match_date,home_club_id,away_club_id) VALUES (?,?,?,?,?,?);""",
            (season_id, 'league', 'الدوري', d, home, away))
        offset += 3


def _schedule_cup(cur, season_id, club_ids, start_str):
    start = datetime.strptime(start_str, "%Y-%m-%d") + timedelta(days=45)
    sh = club_ids[:]
    random.shuffle(sh)
    d = start.strftime("%Y-%m-%d")
    for i in range(0, 8, 2):
        cur.execute("""INSERT INTO matches (season_id,competition,round_name,
            match_date,home_club_id,away_club_id) VALUES (?,?,?,?,?,?);""",
            (season_id, 'cup', 'ربع النهائي', d, sh[i], sh[i+1]))


def _schedule_continental(cur, season_id, club_ids, start_str):
    cur.execute("SELECT club_id FROM clubs ORDER BY reputation DESC LIMIT 4;")
    top4 = [r[0] for r in cur.fetchall()]
    if 1 not in top4: top4[-1] = 1
    random.shuffle(top4)
    start = datetime.strptime(start_str, "%Y-%m-%d") + timedelta(days=75)
    d = start.strftime("%Y-%m-%d")
    for i in (0, 2):
        cur.execute("""INSERT INTO matches (season_id,competition,round_name,
            match_date,home_club_id,away_club_id) VALUES (?,?,?,?,?,?);""",
            (season_id, 'continental', 'نصف النهائي', d, top4[i], top4[i+1]))


def initialize(db_path="football_manager.db"):
    fresh = not os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()
    cur.executescript(SCHEMA)
    _migrate(cur)
    if fresh:
        ids = _seed(cur)
        today = datetime.now().strftime("%Y-%m-%d")
        _schedule_league(cur, 1, ids, today)
        _schedule_cup(cur, 1, ids, today)
        _schedule_continental(cur, 1, ids, today)
        conn.commit()
    return conn


def get_save_metadata(path):
    if not os.path.exists(path): return None
    conn = None
    try:
        conn = sqlite3.connect(path)
        row = conn.execute("""SELECT gs.current_date, s.name, c.name
            FROM game_state gs JOIN seasons s ON s.season_id=gs.active_season_id
            JOIN clubs c ON c.club_id=gs.user_club_id WHERE gs.id=1""").fetchone()
        if row: return {"date": row[0], "season": row[1], "club": row[2]}
    except Exception:
        return None
    finally:
        if conn: conn.close()
    return None