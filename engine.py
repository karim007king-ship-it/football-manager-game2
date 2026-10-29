"""engine.py — منطق اللعبة الكامل."""
import sqlite3, random, os
from datetime import datetime, timedelta
from db import (initialize, _schedule_league, _schedule_cup,
                _schedule_continental, FIRST, LAST)

def _parse(d): return datetime.strptime(d, "%Y-%m-%d")
def _fmt(d): return d.strftime("%Y-%m-%d")

TRAIN_COST_PER_PLAYER_WEEK = 800

ACHIEVEMENTS = {
    'first_goal': ('أول هدف', 'سجل فريقك أول هدف'),
    'first_win': ('أول فوز', 'فزت بأول مباراة'),
    'first_clean_sheet': ('شباك نظيفة', 'حافظت على نظافة شباكك'),
    'league_champion': ('بطل الدوري', 'فزت بلقب الدوري'),
    'cup_winner': ('بطل الكأس', 'فزت بكأس تونس'),
    'continental_winner': ('بطل القارة', 'فزت بالبطولة القارية'),
    'top_scorer_owned': ('هداف الموسم', 'لديك هداف الموسم'),
    'hat_trick': ('هاتريك', 'لاعب سجل 3 أهداف في مباراة'),
    'unbeaten_5': ('5 بلا خسارة', 'خمس مباريات متتالية بلا خسارة'),
    'rich': ('ثري', 'تجاوزت ميزانيتك 10 ملايين'),
    'youth_star': ('نجم المستقبل', 'شاب وصل إلى 80 تقييم'),
    'loyal_servant': ('الوفي', 'لاعب أمضى 5 مواسم في ناديك'),
}
ATTR_MAP = {'pace':'pace','shooting':'shooting','passing':'passing',
            'defending':'defending','physical':'physical'}


class GameEngine:
    def __init__(self, db_path="football_manager_1.db"):
        self.db_path = db_path
        self._conn = initialize(db_path)
        self.last_season_summary = None
        self._load_state()
        self._load_settings()

    def _load_state(self):
        row = self._conn.execute("""SELECT current_date,active_season_id,
            user_club_id,last_weekly_process FROM game_state WHERE id=1""").fetchone()
        self.current_date = _parse(row[0])
        self.active_season_id = row[1]
        self.user_club_id = row[2]
        self.last_weekly_process = _parse(row[3]) if row[3] else _parse(row[0])

    def _load_settings(self):
        self.settings = {k: v for k, v in
                         self._conn.execute("SELECT key,value FROM settings").fetchall()}

    def _save_state(self):
        self._conn.execute("""UPDATE game_state SET current_date=?,
            active_season_id=?, last_weekly_process=? WHERE id=1""",
            (_fmt(self.current_date), self.active_season_id,
             _fmt(self.last_weekly_process)))
        self._conn.commit()

    def save_setting(self, key, value):
        self._conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                          (key, str(value)))
        self._conn.commit()
        self.settings[key] = str(value)
        return True

    def get_dashboard(self):
        c = self._conn.cursor()
        c.execute("""SELECT name,budget,wage_budget,stadium_capacity,tactic
            FROM clubs WHERE club_id=?""", (self.user_club_id,))
        name, budget, wage_b, cap, tactic = c.fetchone()
        c.execute("SELECT confidence,objective FROM board_status WHERE club_id=?",
                  (self.user_club_id,))
        conf, obj = c.fetchone()
        c.execute("SELECT name FROM seasons WHERE season_id=?",
                  (self.active_season_id,))
        season = c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(wage),0)/52 FROM players WHERE club_id=?",
                  (self.user_club_id,))
        weekly_wages = c.fetchone()[0]
        c.execute("""SELECT match_date,home_club_id,away_club_id,competition,
            round_name FROM matches WHERE (home_club_id=? OR away_club_id=?)
            AND status='scheduled' AND season_id=? ORDER BY match_date LIMIT 1""",
            (self.user_club_id, self.user_club_id, self.active_season_id))
        nxt = c.fetchone()
        next_match = None
        if nxt:
            hn = c.execute("SELECT name FROM clubs WHERE club_id=?",
                          (nxt[1],)).fetchone()[0]
            an = c.execute("SELECT name FROM clubs WHERE club_id=?",
                          (nxt[2],)).fetchone()[0]
            next_match = {"date": nxt[0], "home": hn, "away": an,
                          "comp": nxt[3], "round": nxt[4]}
        st = self.get_standings()
        pos = next((i for i, r in enumerate(st, 1)
                    if r["club_id"] == self.user_club_id), None)
        c.execute("SELECT COUNT(*) FROM players WHERE club_id=? AND is_injured=1",
                  (self.user_club_id,))
        injured = c.fetchone()[0]
        c.execute("""SELECT COUNT(*) FROM players WHERE club_id=?
            AND contract_years<=1 AND contract_years>0""", (self.user_club_id,))
        expiring = c.fetchone()[0]
        return {"club": name, "budget": budget, "wage_budget": wage_b,
                "weekly_wages": weekly_wages, "confidence": conf,
                "objective": obj, "season": season,
                "date": _fmt(self.current_date), "next_match": next_match,
                "position": pos, "stadium": cap, "tactic": tactic,
                "injured": injured, "expiring": expiring}

    def get_squad(self):
        c = self._conn.cursor()
        c.execute("""SELECT p.player_id, p.first_name||' '||p.last_name,
            p.position, p.age, p.overall_rating, p.potential_rating,
            p.is_starter, p.is_injured, p.injury_until, p.contract_years,
            p.wage, p.market_value, p.morale, p.is_youth, p.training_focus,
            p.seasons_at_club, s.appearances, s.goals, s.assists, s.motm
            FROM players p LEFT JOIN player_stats s ON s.player_id=p.player_id
            WHERE p.club_id=?
            ORDER BY p.is_starter DESC, p.overall_rating DESC""",
            (self.user_club_id,))
        return [dict(zip(["id","name","pos","age","ovr","pot","starter","injured",
            "injury_until","contract","wage","value","morale","youth",
            "training_focus","seasons_at_club","apps","goals","assists","motm"], r))
            for r in c.fetchall()]

    def get_squad_paged(self, page=0, page_size=15):
        squad = self.get_squad()
        start = page * page_size
        return squad[start:start + page_size], len(squad)

    def get_expiring_contracts(self):
        c = self._conn.cursor()
        c.execute("""SELECT player_id, first_name||' '||last_name, position,
            age, overall_rating, wage, contract_years, market_value
            FROM players WHERE club_id=? AND contract_years<=1
            ORDER BY contract_years, overall_rating DESC""", (self.user_club_id,))
        return [{"id": r[0], "name": r[1], "pos": r[2], "age": r[3], "ovr": r[4],
                 "wage": r[5], "contract": r[6], "value": r[7]}
                for r in c.fetchall()]

    def get_player_details(self, pid):
        c = self._conn.cursor()
        c.execute("""SELECT p.*, s.appearances, s.goals, s.assists, s.minutes,
            s.motm, s.clean_sheets, s.yellow_cards, s.red_cards, cl.name AS club_name
            FROM players p LEFT JOIN player_stats s ON s.player_id=p.player_id
            LEFT JOIN clubs cl ON cl.club_id=p.club_id WHERE p.player_id=?""", (pid,))
        row = c.fetchone()
        if not row: return None
        return dict(zip([d[0] for d in c.description], row))

    def get_standings(self):
        c = self._conn.cursor()
        c.execute("SELECT club_id,name FROM clubs")
        st = {cid: {"club_id": cid, "name": n, "p": 0, "w": 0, "d": 0, "l": 0,
                    "gf": 0, "ga": 0, "pts": 0} for cid, n in c.fetchall()}
        c.execute("""SELECT home_club_id,away_club_id,home_goals,away_goals
            FROM matches WHERE status='played' AND season_id=?
            AND competition='league'""", (self.active_season_id,))
        for h, a, hg, ag in c.fetchall():
            for t, gf, ga in [(h, hg, ag), (a, ag, hg)]:
                st[t]["p"] += 1; st[t]["gf"] += gf; st[t]["ga"] += ga
                if gf > ga: st[t]["w"] += 1; st[t]["pts"] += 3
                elif gf == ga: st[t]["d"] += 1; st[t]["pts"] += 1
                else: st[t]["l"] += 1
        for v in st.values(): v["gd"] = v["gf"] - v["ga"]
        return sorted(st.values(), key=lambda x: (x["pts"], x["gd"], x["gf"]),
                      reverse=True)

    def get_cup(self): return self._get_comp('cup')
    def get_continental(self): return self._get_comp('continental')

    def _get_comp(self, comp):
        c = self._conn.cursor()
        c.execute("""SELECT m.round_name,m.match_date,m.status,
            h.name,a.name,m.home_goals,m.away_goals FROM matches m
            JOIN clubs h ON h.club_id=m.home_club_id
            JOIN clubs a ON a.club_id=m.away_club_id
            WHERE m.season_id=? AND m.competition=?
            ORDER BY m.match_date, m.match_id""",
            (self.active_season_id, comp))
        return [{"round": r[0], "date": r[1], "status": r[2], "home": r[3],
                 "away": r[4], "hg": r[5], "ag": r[6]} for r in c.fetchall()]

    def get_fixtures(self, comp=None):
        c = self._conn.cursor()
        q = """SELECT m.match_date,m.competition,m.round_name,
            h.name,a.name,m.home_goals,m.away_goals,m.status,m.match_id
            FROM matches m JOIN clubs h ON h.club_id=m.home_club_id
            JOIN clubs a ON a.club_id=m.away_club_id
            WHERE m.season_id=? AND (m.home_club_id=? OR m.away_club_id=?)"""
        args = [self.active_season_id, self.user_club_id, self.user_club_id]
        if comp: q += " AND m.competition=?"; args.append(comp)
        q += " ORDER BY m.match_date"
        c.execute(q, args)
        return [{"date": r[0], "comp": r[1], "round": r[2], "home": r[3],
                 "away": r[4], "hg": r[5], "ag": r[6], "status": r[7],
                 "match_id": r[8]} for r in c.fetchall()]

    def get_match_events(self, match_id):
        c = self._conn.cursor()
        c.execute("""SELECT minute,event_type,detail FROM match_events
            WHERE match_id=? ORDER BY minute""", (match_id,))
        return [{"minute": r[0], "type": r[1], "detail": r[2]}
                for r in c.fetchall()]

    def get_transfer_market(self, limit=15):
        c = self._conn.cursor()
        c.execute("""SELECT p.player_id, p.first_name||' '||p.last_name,
            p.position, p.age, p.overall_rating, p.market_value, c.name
            FROM players p JOIN clubs c ON c.club_id=p.club_id
            WHERE p.club_id != ? AND p.overall_rating >= 55
            ORDER BY RANDOM() LIMIT ?""", (self.user_club_id, limit))
        return [{"id": r[0], "name": r[1], "pos": r[2], "age": r[3],
                 "ovr": r[4], "value": r[5], "club": r[6]} for r in c.fetchall()]

    def get_transfer_history(self, limit=50):
        c = self._conn.cursor()
        c.execute("""SELECT date,player_name,from_club,to_club,fee,move_type
            FROM transfer_history ORDER BY id DESC LIMIT ?""", (limit,))
        return [{"date": r[0], "player": r[1], "from": r[2], "to": r[3],
                 "fee": r[4], "type": r[5]} for r in c.fetchall()]

    def get_top_scorers(self, limit=10):
        c = self._conn.cursor()
        c.execute("""SELECT p.player_id, p.first_name||' '||p.last_name,
            c.name, s.goals, s.assists, s.appearances FROM player_stats s
            JOIN players p ON p.player_id=s.player_id
            JOIN clubs c ON c.club_id=p.club_id
            WHERE s.goals>0 ORDER BY s.goals DESC LIMIT ?""", (limit,))
        return [{"id": r[0], "name": r[1], "club": r[2], "goals": r[3],
                 "assists": r[4], "apps": r[5]} for r in c.fetchall()]

    def get_finances_log(self, limit=30):
        c = self._conn.cursor()
        c.execute("""SELECT date,amount,description,balance_after
            FROM finances_log WHERE club_id=? ORDER BY id DESC LIMIT ?""",
            (self.user_club_id, limit))
        return [{"date": r[0], "amount": r[1], "desc": r[2], "balance": r[3]}
                for r in c.fetchall()]

    def get_season_history(self):
        c = self._conn.cursor()
        c.execute("""SELECT season_name,league_champion,cup_winner,
            continental_winner,top_scorer,user_position
            FROM season_history ORDER BY id DESC""")
        return [{"season": r[0], "league": r[1], "cup": r[2], "cont": r[3],
                 "top": r[4], "pos": r[5]} for r in c.fetchall()]

    def get_achievements(self):
        c = self._conn.cursor()
        c.execute("""SELECT achievement_key,name,description,unlocked_date
            FROM achievements WHERE club_id=?""", (self.user_club_id,))
        unlocked = {r[0]: {"name": r[1], "desc": r[2], "date": r[3]}
                    for r in c.fetchall()}
        result = []
        for key, (name, desc) in ACHIEVEMENTS.items():
            if key in unlocked:
                result.append({"key": key, "name": name, "desc": desc,
                               "unlocked": True, "date": unlocked[key]["date"]})
            else:
                result.append({"key": key, "name": name, "desc": desc,
                               "unlocked": False, "date": None})
        return result

    def set_lineup(self, player_ids):
        if len(player_ids) != 11:
            return False, "يجب اختيار 11 لاعباً"
        c = self._conn.cursor()
        ph = ','.join('?' * len(player_ids))
        c.execute(f"""SELECT player_id FROM players WHERE player_id IN ({ph})
            AND club_id=? AND is_injured=0""", (*player_ids, self.user_club_id))
        valid = {r[0] for r in c.fetchall()}
        invalid = set(player_ids) - valid
        if invalid:
            return False, f"{len(invalid)} لاعب غير صالح"
        c.execute("UPDATE players SET is_starter=0 WHERE club_id=?",
                  (self.user_club_id,))
        for pid in player_ids:
            c.execute("UPDATE players SET is_starter=1 WHERE player_id=?", (pid,))
        self._conn.commit()
        return True, "تم حفظ التشكيلة"

    def set_tactic(self, tactic):
        if tactic not in ('attacking', 'balanced', 'defensive'):
            return False, "تكتيك غير صالح"
        self._conn.execute("UPDATE clubs SET tactic=? WHERE club_id=?",
                           (tactic, self.user_club_id))
        self._conn.commit()
        return True, "تم تحديث التكتيك"

    def buy_player(self, pid):
        c = self._conn.cursor()
        c.execute("""SELECT p.market_value, p.club_id,
            p.first_name||' '||p.last_name FROM players p WHERE p.player_id=?""", (pid,))
        row = c.fetchone()
        if not row: return False, "لاعب غير موجود"
        value, seller, pname = row
        c.execute("SELECT budget FROM clubs WHERE club_id=?", (self.user_club_id,))
        budget = c.fetchone()[0]
        if budget < value * 1.2:
            return False, f"ميزانية غير كافية (تحتاج {value*1.2:,.0f})"
        c.execute("SELECT name FROM clubs WHERE club_id=?", (self.user_club_id,))
        buyer_name = c.fetchone()[0]
        seller_row = c.execute("SELECT name FROM clubs WHERE club_id=?",
                              (seller,)).fetchone()
        seller_name = seller_row[0] if seller_row else "حر"
        c.execute("""UPDATE players SET club_id=?, is_starter=0,
            seasons_at_club=0 WHERE player_id=?""", (self.user_club_id, pid))
        c.execute("UPDATE clubs SET budget=budget-? WHERE club_id=?",
                  (value * 1.2, self.user_club_id))
        if seller:
            c.execute("UPDATE clubs SET budget=budget+? WHERE club_id=?",
                      (value, seller))
        self._log_finance(c, -value * 1.2, f"شراء {pname}")
        c.execute("""INSERT INTO transfer_history
            (date,player_name,from_club,to_club,fee,move_type)
            VALUES (?,?,?,?,?,?)""",
            (_fmt(self.current_date), pname, seller_name, buyer_name,
             value * 1.2, 'buy'))
        self._conn.commit()
        return True, f"تم شراء {pname}"

    def sell_player(self, pid):
        c = self._conn.cursor()
        c.execute("""SELECT market_value, first_name||' '||last_name
            FROM players WHERE player_id=? AND club_id=?""",
            (pid, self.user_club_id))
        row = c.fetchone()
        if not row: return False, "لاعب ليس في فريقك"
        value, pname = row
        club_name = c.execute("SELECT name FROM clubs WHERE club_id=?",
                             (self.user_club_id,)).fetchone()[0]
        c.execute("UPDATE players SET club_id=NULL,is_starter=0 WHERE player_id=?",
                  (pid,))
        c.execute("UPDATE clubs SET budget=budget+? WHERE club_id=?",
                  (value * 0.85, self.user_club_id))
        self._log_finance(c, value * 0.85, f"بيع {pname}")
        c.execute("""INSERT INTO transfer_history
            (date,player_name,from_club,to_club,fee,move_type)
            VALUES (?,?,?,?,?,?)""",
            (_fmt(self.current_date), pname, club_name, 'حر', value * 0.85, 'sell'))
        self._conn.commit()
        return True, f"تم بيع {pname} مقابل {value*0.85:,.0f}"

    def renew_contract(self, pid, years=2):
        if years not in (1, 2, 3, 4, 5): return False, "مدة غير صالحة"
        c = self._conn.cursor()
        c.execute("SELECT overall_rating, wage FROM players WHERE player_id=? AND club_id=?",
                  (pid, self.user_club_id))
        row = c.fetchone()
        if not row: return False, "لاعب ليس في فريقك"
        ovr, wage = row
        new_wage = int(wage * (1 + (ovr - 60) / 200)) if ovr > 60 else wage
        c.execute("UPDATE players SET contract_years=?, wage=?, contract_warned=0 "
                  "WHERE player_id=?", (years, new_wage, pid))
        self._conn.commit()
        return True, f"تم التجديد {years} سنوات براتب {new_wage:,.0f}"

    def release_player(self, pid):
        c = self._conn.cursor()
        c.execute("""SELECT market_value, wage, contract_years,
            first_name||' '||last_name FROM players
            WHERE player_id=? AND club_id=?""", (pid, self.user_club_id))
        row = c.fetchone()
        if not row: return False, "لاعب ليس في فريقك"
        value, wage, years, pname = row
        compensation = wage * max(1, years) * 0.5
        c.execute("UPDATE players SET club_id=NULL,is_starter=0 WHERE player_id=?",
                  (pid,))
        c.execute("UPDATE clubs SET budget=budget-? WHERE club_id=?",
                  (compensation, self.user_club_id))
        self._log_finance(c, -compensation, f"إنهاء عقد {pname}")
        self._conn.commit()
        return True, f"تم تحرير {pname} بتعويض {compensation:,.0f}"

    def set_training_focus(self, pid, attribute):
        if attribute not in ATTR_MAP: return False, "سمة غير صالحة"
        c = self._conn.cursor()
        c.execute("""SELECT overall_rating, potential_rating, training_focus
            FROM players WHERE player_id=? AND club_id=?""",
            (pid, self.user_club_id))
        row = c.fetchone()
        if not row: return False, "لاعب ليس في فريقك"
        ovr, pot, current = row
        if current == attribute:
            c.execute("UPDATE players SET training_focus=NULL WHERE player_id=?", (pid,))
            msg = "تم إيقاف التركيز"
        else:
            if ovr >= pot: return False, "اللاعب وصل سقفه"
            c.execute("UPDATE players SET training_focus=? WHERE player_id=?",
                      (attribute, pid))
            msg = f"تم التركيز على {attribute}"
        self._conn.commit()
        return True, msg

    def group_train(self, player_ids, attribute):
        if attribute not in ATTR_MAP: return False, "سمة غير صالحة"
        if not player_ids: return False, "لم تختر أي لاعب"
        c = self._conn.cursor()
        ph = ','.join('?' * len(player_ids))
        c.execute(f"""UPDATE players SET training_focus=?
            WHERE player_id IN ({ph}) AND club_id=?
            AND is_injured=0 AND overall_rating < potential_rating""",
            (attribute, *player_ids, self.user_club_id))
        count = c.rowcount
        self._conn.commit()
        return True, f"تم تدريب {count} لاعب على {attribute}"

    def advance_days(self, days=7):
        self.last_season_summary = None
        log = []
        c = self._conn.cursor()
        for _ in range(days):
            today = _fmt(self.current_date)
            log.append({"type": "date", "text": today})
            played = False
            c.execute("""SELECT match_id,home_club_id,away_club_id,
                competition,round_name FROM matches WHERE match_date=?
                AND status='scheduled' AND season_id=?""",
                (today, self.active_season_id))
            for mid, h, a, comp, rnd in c.fetchall():
                result = self._simulate_match(mid, h, a, comp)
                log.append({"type": "match", "comp": comp, "round": rnd,
                            "text": result, "match_id": mid})
                played = True
            if not played:
                log.append({"type": "rest", "text": "يوم راحة"})
            self.current_date += timedelta(days=1)

        self._process_injuries()
        self._process_wages(c, days)
        self._process_training(c, days)
        self._process_monthly_development()
        self._process_board()
        self._process_contract_warnings()
        self._check_achievements()
        self._check_cup_progression('cup')
        self._check_cup_progression('continental')
        self._check_season_end(log)

        self._conn.commit()
        self._save_state()
        return log

    def _process_wages(self, c, days):
        c.execute("SELECT COALESCE(SUM(wage),0)/52 FROM players WHERE club_id=?",
                  (self.user_club_id,))
        weekly = c.fetchone()[0] or 0
        amount = (weekly / 7.0) * days
        if amount > 0:
            c.execute("UPDATE clubs SET budget=budget-? WHERE club_id=?",
                      (amount, self.user_club_id))
            self._log_finance(c, -amount, f"رواتب {days} يوم")

    def _process_training(self, c, days):
        c.execute("""SELECT player_id, training_focus, overall_rating,
            potential_rating FROM players WHERE club_id=?
            AND training_focus IS NOT NULL AND is_injured=0""",
            (self.user_club_id,))
        players = c.fetchall()
        if not players: return
        amount = (TRAIN_COST_PER_PLAYER_WEEK / 7.0) * days * len(players)
        c.execute("UPDATE clubs SET budget=budget-? WHERE club_id=?",
                  (amount, self.user_club_id))
        self._log_finance(c, -amount, f"تدريب {len(players)} لاعب ({days}ي)")
        if days < 7: return
        for pid, focus, ovr, pot in players:
            if ovr >= pot: continue
            gap = pot - ovr
            prob = 0.15 if gap >= 10 else 0.10 if gap >= 5 else 0.06 if gap >= 2 else 0.03
            if random.random() < prob:
                col = ATTR_MAP[focus]
                c.execute(f"UPDATE players SET overall_rating=?, "
                          f"{col}=MIN(99,{col}+2) WHERE player_id=?",
                          (min(pot, ovr + 1), pid))

    def _simulate_match(self, mid, hid, aid, comp):
        c = self._conn.cursor()
        self._auto_lineup(hid, c)
        self._auto_lineup(aid, c)

        def strength(cid, tactic):
            c.execute("""SELECT position, AVG(overall_rating) FROM players
                WHERE club_id=? AND is_starter=1 AND is_injured=0
                GROUP BY position""", (cid,))
            d = dict(c.fetchall())
            atk = (d.get("FWD", 60) + d.get("MID", 60)) / 2
            dfn = (d.get("DEF", 60) + d.get("GK", 60)) / 2
            if tactic == 'attacking': atk += 3; dfn -= 2
            elif tactic == 'defensive': atk -= 2; dfn += 3
            return atk, dfn

        ht = c.execute("SELECT tactic FROM clubs WHERE club_id=?",
                      (hid,)).fetchone()[0]
        at = c.execute("SELECT tactic FROM clubs WHERE club_id=?",
                      (aid,)).fetchone()[0]
        hA, hD = strength(hid, ht)
        aA, aD = strength(aid, at)
        hg = self._poisson(1.35 + (hA - aD) / 20 + 0.3)
        ag = self._poisson(1.15 + (aA - hD) / 20)
        if comp in ('cup', 'continental') and hg == ag:
            if random.random() < 0.5: hg += 1
            else: ag += 1

        self._record_goals(mid, hid, hg, c)
        self._record_goals(mid, aid, ag, c)
        self._record_cards(mid, hid, c)
        self._record_cards(mid, aid, c)
        self._check_injuries_during_match(mid, hid, c)
        self._check_injuries_during_match(mid, aid, c)
        self._update_appearances(hid, c)
        self._update_appearances(aid, c)
        self._check_hat_trick(mid, c)

        winner = hid if hg > ag else (aid if ag > hg else None)
        if winner:
            motm = self._pick_motm(winner, c)
            if motm:
                c.execute("UPDATE player_stats SET motm=motm+1 WHERE player_id=?",
                          (motm,))

        attendance = random.randint(3000, 35000)
        c.execute("""UPDATE matches SET home_goals=?,away_goals=?,
            status='played', attendance=? WHERE match_id=?""",
            (hg, ag, attendance, mid))
        price = c.execute("SELECT ticket_price FROM clubs WHERE club_id=?",
                         (hid,)).fetchone()[0]
        revenue = price * attendance * 0.4
        c.execute("UPDATE clubs SET budget=budget+? WHERE club_id=?",
                  (revenue, hid))
        if hid == self.user_club_id:
            self._log_finance(c, revenue, "دخل التذاكر")

        hn = c.execute("SELECT name FROM clubs WHERE club_id=?",
                      (hid,)).fetchone()[0]
        an = c.execute("SELECT name FROM clubs WHERE club_id=?",
                      (aid,)).fetchone()[0]
        return f"{hn} {hg} - {ag} {an}"

    def _poisson(self, mean):
        L = 2.718281828 ** (-max(0, mean))
        k, p = 0, 1.0
        while True:
            k += 1; p *= random.random()
            if p <= L: return k - 1

    def _record_goals(self, mid, club_id, count, c):
        if count == 0: return
        c.execute("""SELECT player_id, position FROM players
            WHERE club_id=? AND is_starter=1 AND is_injured=0""", (club_id,))
        squad = c.fetchall()
        if not squad: return
        w = {"FWD": 5, "MID": 3, "DEF": 1, "GK": 0}
        pool = []
        for pid, pos in squad: pool += [pid] * w.get(pos, 1)
        if not pool: return
        for _ in range(count):
            scorer = random.choice(pool)
            c.execute("""INSERT INTO match_events (match_id,minute,event_type,
                player_id,club_id,detail) VALUES (?,?,?,?,?,?)""",
                (mid, random.randint(1, 90), 'goal', scorer, club_id, 'هدف'))
            c.execute("UPDATE player_stats SET goals=goals+1 WHERE player_id=?",
                      (scorer,))
            if random.random() < 0.6:
                creator = random.choice(pool)
                if creator != scorer:
                    c.execute("UPDATE player_stats SET assists=assists+1 "
                              "WHERE player_id=?", (creator,))

    def _record_cards(self, mid, club_id, c):
        c.execute("SELECT player_id FROM players WHERE club_id=? AND is_starter=1",
                  (club_id,))
        for (pid,) in c.fetchall():
            if random.random() < 0.08:
                c.execute("""INSERT INTO match_events (match_id,minute,event_type,
                    player_id,club_id,detail) VALUES (?,?,?,?,?,?)""",
                    (mid, random.randint(10, 90), 'yellow', pid, club_id, 'بطاقة'))
                c.execute("UPDATE player_stats SET yellow_cards=yellow_cards+1 "
                          "WHERE player_id=?", (pid,))

    def _check_injuries_during_match(self, mid, club_id, c):
        c.execute("""SELECT player_id FROM players
            WHERE club_id=? AND is_starter=1 AND is_injured=0""", (club_id,))
        for (pid,) in c.fetchall():
            if random.random() < 0.05:
                days = random.randint(7, 42)
                until = _fmt(self.current_date + timedelta(days=days))
                c.execute("UPDATE players SET is_injured=1, injury_until=? "
                          "WHERE player_id=?", (until, pid))
                c.execute("""INSERT INTO match_events (match_id,minute,event_type,
                    player_id,club_id,detail) VALUES (?,?,?,?,?,?)""",
                    (mid, random.randint(10, 90), 'injury', pid, club_id,
                     f'إصابة {days}ي'))

    def _update_appearances(self, club_id, c):
        c.execute("""UPDATE player_stats SET appearances=appearances+1
            WHERE player_id IN (SELECT player_id FROM players
            WHERE club_id=? AND is_starter=1 AND is_injured=0)""", (club_id,))

    def _check_hat_trick(self, mid, c):
        row = c.execute("""SELECT player_id FROM match_events WHERE match_id=?
            AND event_type='goal' GROUP BY player_id HAVING COUNT(*)>=3 LIMIT 1""",
            (mid,)).fetchone()
        if row:
            pc = c.execute("SELECT club_id FROM players WHERE player_id=?",
                          (row[0],)).fetchone()
            if pc and pc[0] == self.user_club_id:
                self._unlock(c, 'hat_trick')

    def _pick_motm(self, club_id, c):
        c.execute("""SELECT player_id FROM players WHERE club_id=?
            AND is_starter=1 AND is_injured=0
            ORDER BY overall_rating DESC LIMIT 3""", (club_id,))
        rows = c.fetchall()
        return random.choice(rows)[0] if rows else None

    def _auto_lineup(self, club_id, c):
        c.execute("UPDATE players SET is_starter=0 WHERE club_id=?", (club_id,))
        c.execute("""SELECT player_id FROM players WHERE club_id=? AND is_injured=0
            ORDER BY overall_rating DESC LIMIT 11""", (club_id,))
        for (pid,) in c.fetchall():
            c.execute("UPDATE players SET is_starter=1 WHERE player_id=?", (pid,))

    def _process_injuries(self):
        today = _fmt(self.current_date)
        self._conn.execute("""UPDATE players SET is_injured=0, injury_until=NULL
            WHERE is_injured=1 AND injury_until<=?""", (today,))
        self._conn.commit()

    def _process_monthly_development(self):
        if self.current_date.day != 1: return
        c = self._conn.cursor()
        for pid, age, ovr, pot in c.execute("""SELECT player_id,age,
            overall_rating,potential_rating FROM players""").fetchall():
            if age >= 30:
                change = random.choice([-2, -1, 0, 0, 0])
                if change != 0:
                    c.execute("UPDATE players SET overall_rating=? WHERE player_id=?",
                              (max(40, ovr + change), pid))
                continue
            if ovr >= pot: continue
            gap = pot - ovr
            if age <= 19: cap, prob = 3, 0.70
            elif age <= 22: cap, prob = 2, 0.60
            elif age <= 26: cap, prob = 1, 0.50
            else: cap, prob = 1, 0.30
            if gap >= 10: prob *= 0.5
            elif gap >= 5: prob *= 0.8
            if random.random() < prob:
                c.execute("UPDATE players SET overall_rating=? WHERE player_id=?",
                          (min(pot, ovr + random.randint(1, cap)), pid))
        self._conn.commit()

    def _log_finance(self, c, amount, desc):
        balance = c.execute("SELECT budget FROM clubs WHERE club_id=?",
                          (self.user_club_id,)).fetchone()[0]
        c.execute("""INSERT INTO finances_log
            (club_id,date,amount,description,balance_after)
            VALUES (?,?,?,?,?)""",
            (self.user_club_id, _fmt(self.current_date), amount, desc, balance))

    def _process_board(self):
        c = self._conn.cursor()
        rows = c.execute("""SELECT home_club_id,away_club_id,home_goals,away_goals
            FROM matches WHERE status='played'
            AND (home_club_id=? OR away_club_id=?) AND season_id=?
            ORDER BY match_date DESC LIMIT 5""",
            (self.user_club_id, self.user_club_id, self.active_season_id)).fetchall()
        if not rows: return
        delta = 0
        for h, a, hg, ag in rows:
            our = hg if h == self.user_club_id else ag
            opp = ag if h == self.user_club_id else hg
            if our > opp: delta += 2
            elif our < opp: delta -= 3
        cur_conf = c.execute("SELECT confidence FROM board_status WHERE club_id=?",
                            (self.user_club_id,)).fetchone()[0]
        new_conf = max(0, min(100, cur_conf + delta))
        c.execute("""UPDATE board_status SET confidence=?, last_evaluated=?
            WHERE club_id=?""",
            (new_conf, _fmt(self.current_date), self.user_club_id))
        self._conn.commit()

    def _process_contract_warnings(self):
        self._conn.execute("""UPDATE players SET contract_warned=1
            WHERE club_id=? AND contract_years<=1 AND contract_warned=0
            AND contract_years>0""", (self.user_club_id,))
        self._conn.commit()

    def _check_achievements(self):
        c = self._conn.cursor()
        uci = self.user_club_id
        if c.execute("""SELECT COUNT(*) FROM player_stats s
            JOIN players p ON p.player_id=s.player_id
            WHERE p.club_id=? AND s.goals>0""", (uci,)).fetchone()[0] > 0:
            self._unlock(c, 'first_goal')
        if c.execute("""SELECT COUNT(*) FROM matches WHERE status='played'
            AND season_id=? AND ((home_club_id=? AND home_goals>away_goals)
            OR (away_club_id=? AND away_goals>home_goals))""",
            (self.active_season_id, uci, uci)).fetchone()[0] > 0:
            self._unlock(c, 'first_win')
        if c.execute("""SELECT COUNT(*) FROM matches WHERE status='played'
            AND season_id=? AND ((home_club_id=? AND away_goals=0)
            OR (away_club_id=? AND home_goals=0))""",
            (self.active_season_id, uci, uci)).fetchone()[0] > 0:
            self._unlock(c, 'first_clean_sheet')
        if c.execute("SELECT budget FROM clubs WHERE club_id=?",
                    (uci,)).fetchone()[0] >= 10_000_000:
            self._unlock(c, 'rich')
        if c.execute("""SELECT COUNT(*) FROM players WHERE club_id=?
            AND age<=22 AND overall_rating>=80""", (uci,)).fetchone()[0] > 0:
            self._unlock(c, 'youth_star')
        if c.execute("""SELECT COUNT(*) FROM players WHERE club_id=?
            AND seasons_at_club>=5""", (uci,)).fetchone()[0] > 0:
            self._unlock(c, 'loyal_servant')
        rows = c.execute("""SELECT home_club_id,away_club_id,home_goals,away_goals
            FROM matches WHERE status='played'
            AND (home_club_id=? OR away_club_id=?) AND season_id=?
            ORDER BY match_date DESC LIMIT 5""",
            (uci, uci, self.active_season_id)).fetchall()
        if len(rows) == 5:
            unbeaten = all(
                (hg if h == uci else ag) >= (ag if h == uci else hg)
                for h, a, hg, ag in rows)
            if unbeaten: self._unlock(c, 'unbeaten_5')

    def _unlock(self, c, key):
        if key not in ACHIEVEMENTS: return
        name, desc = ACHIEVEMENTS[key]
        try:
            c.execute("""INSERT INTO achievements
                (club_id,achievement_key,name,description,unlocked_date,season_id)
                VALUES (?,?,?,?,?,?)""",
                (self.user_club_id, key, name, desc,
                 _fmt(self.current_date), self.active_season_id))
        except sqlite3.IntegrityError:
            pass

    def _check_cup_progression(self, comp):
        rounds = {'cup': ['ربع النهائي', 'نصف النهائي', 'النهائي'],
                  'continental': ['نصف النهائي', 'النهائي']}[comp]
        c = self._conn.cursor()
        for i, cur_r in enumerate(rounds):
            if c.execute("""SELECT COUNT(*) FROM matches WHERE round_name=?
                AND competition=? AND season_id=? AND status='scheduled'""",
                (cur_r, comp, self.active_season_id)).fetchone()[0] > 0:
                return
            if c.execute("""SELECT COUNT(*) FROM matches WHERE round_name=?
                AND competition=? AND season_id=? AND status='played'""",
                (cur_r, comp, self.active_season_id)).fetchone()[0] == 0:
                return
            matches = c.execute("""SELECT home_club_id,away_club_id,
                home_goals,away_goals FROM matches WHERE round_name=?
                AND competition=? AND season_id=? AND status='played'""",
                (cur_r, comp, self.active_season_id)).fetchall()
            winners = [self._winner(m) for m in matches]
            if cur_r == 'النهائي':
                col = 'cup_winner_id' if comp == 'cup' else 'continental_winner_id'
                if winners:
                    c.execute(f"UPDATE seasons SET {col}=? WHERE season_id=?",
                              (winners[0], self.active_season_id))
                    if winners[0] == self.user_club_id:
                        self._unlock(c, 'cup_winner' if comp == 'cup'
                                     else 'continental_winner')
                return
            nxt = rounds[i + 1]
            if c.execute("""SELECT COUNT(*) FROM matches WHERE round_name=?
                AND competition=? AND season_id=?""",
                (nxt, comp, self.active_season_id)).fetchone()[0] > 0:
                continue
            nd = _fmt(self.current_date + timedelta(days=14))
            for j in range(0, len(winners), 2):
                if j + 1 < len(winners):
                    c.execute("""INSERT INTO matches (season_id,competition,
                        round_name,match_date,home_club_id,away_club_id)
                        VALUES (?,?,?,?,?,?)""",
                        (self.active_season_id, comp, nxt, nd,
                         winners[j], winners[j+1]))

    def _winner(self, m):
        h, a, hg, ag = m
        if hg > ag: return h
        if ag > hg: return a
        return random.choice([h, a])

    def _check_season_end(self, log):
        c = self._conn.cursor()
        if c.execute("SELECT COUNT(*) FROM matches WHERE season_id=? AND status='scheduled'",
                    (self.active_season_id,)).fetchone()[0] > 0:
            return
        summary = self._capture_season_summary(c)
        self._write_season_history(c, summary)
        self._apply_season_rewards(c, summary)
        self._process_contracts_season_end(c)
        c.execute("UPDATE seasons SET is_active=0 WHERE season_id=?",
                  (self.active_season_id,))
        new_name = f"موسم {self.current_date.year + 1}/{self.current_date.year + 2}"
        c.execute("INSERT INTO seasons (name,is_active) VALUES (?,1)", (new_name,))
        self.active_season_id = c.lastrowid
        c.execute("""UPDATE players SET age=age+1, seasons_at_club=seasons_at_club+1
            WHERE club_id IS NOT NULL""")
        self._conn.commit()
        ids = [r[0] for r in c.execute("SELECT club_id FROM clubs").fetchall()]
        random.shuffle(ids)
        start = _fmt(self.current_date + timedelta(days=30))
        _schedule_league(c, self.active_season_id, ids, start)
        _schedule_cup(c, self.active_season_id, ids, start)
        _schedule_continental(c, self.active_season_id, ids, start)
        self._conn.commit()
        self._generate_youth(c)
        self._conn.commit()
        self.last_season_summary = summary
        log.append({"type": "season_end", "text": f"🏆 موسم جديد: {new_name}",
                    "summary": summary})

    def _capture_season_summary(self, c):
        st = self.get_standings()
        league = st[0] if st else None
        def final_winner(comp):
            row = c.execute("""SELECT home_club_id,away_club_id,
                home_goals,away_goals FROM matches WHERE competition=?
                AND season_id=? AND round_name='النهائي' AND status='played'""",
                (comp, self.active_season_id)).fetchone()
            if not row: return None
            h, a, hg, ag = row
            w = h if hg > ag else (a if ag > hg else None)
            if w:
                return c.execute("SELECT name FROM clubs WHERE club_id=?",
                                (w,)).fetchone()[0]
            return None
        top = self.get_top_scorers(1)
        user_pos = next((i for i, r in enumerate(st, 1)
                         if r["club_id"] == self.user_club_id), None)
        season_name = c.execute("SELECT name FROM seasons WHERE season_id=?",
                               (self.active_season_id,)).fetchone()[0]
        user_club = c.execute("SELECT name FROM clubs WHERE club_id=?",
                             (self.user_club_id,)).fetchone()[0]
        return {"season_name": season_name,
                "league_champion": league["name"] if league else None,
                "cup_winner": final_winner('cup'),
                "continental_winner": final_winner('continental'),
                "top_scorer": top[0] if top else None,
                "user_position": user_pos, "user_club": user_club}

    def _write_season_history(self, c, s):
        c.execute("""INSERT INTO season_history
            (season_id,season_name,league_champion,cup_winner,
            continental_winner,top_scorer,user_position,user_club)
            VALUES (?,?,?,?,?,?,?,?)""",
            (self.active_season_id, s["season_name"], s["league_champion"],
             s["cup_winner"], s["continental_winner"],
             s["top_scorer"]["name"] if s["top_scorer"] else None,
             s["user_position"], s["user_club"]))

    def _apply_season_rewards(self, c, s):
        user_rewards = 0
        if s["league_champion"] == s["user_club"]: user_rewards += 2_000_000
        if s["cup_winner"] == s["user_club"]: user_rewards += 1_000_000
        if s["continental_winner"] == s["user_club"]: user_rewards += 3_000_000
        if user_rewards > 0:
            c.execute("UPDATE clubs SET budget=budget+? WHERE club_id=?",
                      (user_rewards, self.user_club_id))
            self._log_finance(c, user_rewards, "جوائز نهاية الموسم")
        for cid, rep in c.execute("""SELECT club_id,reputation FROM clubs
            WHERE club_id!=?""", (self.user_club_id,)).fetchall():
            c.execute("UPDATE clubs SET budget=budget+? WHERE club_id=?",
                      (int(rep * 10000), cid))

    def _process_contracts_season_end(self, c):
        c.execute("UPDATE players SET contract_years=contract_years-1 "
                  "WHERE club_id IS NOT NULL")
        for pid, pname in c.execute("""SELECT player_id,
            first_name||' '||last_name FROM players
            WHERE club_id=? AND contract_years<=0""",
            (self.user_club_id,)).fetchall():
            c.execute("UPDATE players SET club_id=NULL,is_starter=0 "
                      "WHERE player_id=?", (pid,))
            self._log_finance(c, 0, f"انتهاء عقد {pname}")
        c.execute("""UPDATE players SET contract_years=3
            WHERE club_id IS NOT NULL AND club_id!=? AND contract_years<=0""",
            (self.user_club_id,))

    def _generate_youth(self, c):
        for _ in range(random.randint(2, 4)):
            fn, ln = random.choice(FIRST), random.choice(LAST)
            pos = random.choice(['DEF', 'MID', 'FWD'])
            age = random.randint(15, 17)
            ovr = random.randint(42, 58)
            pot = random.randint(72, 95)
            wage = max(1000, int(ovr * 80))
            val = max(5000, ovr * ovr * 150)
            c.execute("""INSERT INTO players (first_name,last_name,position,age,
                overall_rating,potential_rating,club_id,is_starter,wage,
                market_value,is_youth) VALUES (?,?,?,?,?,?,?,0,?,?,1)""",
                (fn, ln, pos, age, ovr, pot, self.user_club_id, wage, val))
            c.execute("INSERT INTO player_stats (player_id) VALUES (?)",
                      (c.lastrowid,))

    def reset(self):
        self._conn.close()
        if os.path.exists(self.db_path): os.remove(self.db_path)
        self.__init__(self.db_path)