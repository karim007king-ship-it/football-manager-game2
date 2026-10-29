"""main.py — النسخة النهائية المستقرة مع دعم الخط العربي والحماية من الانهيار."""
import os, shutil
import traceback

# --- 1. إعداد الخط العربي ---
from kivy.core.text import LabelBase
arabic_font = None
# نبحث عن خطوط الأندرويد المدمجة
font_paths = [
    "/system/fonts/DroidSansArabic.ttf",
    "/system/fonts/NotoNaskhArabic-Regular.ttf",
    "/system/fonts/NotoSansArabic-Regular.ttf",
    "/system/fonts/DroidNaskh-Regular.ttf"
]
for path in font_paths:
    if os.path.exists(path):
        LabelBase.register(name="ArabicFont", fn_regular=path)
        arabic_font = "ArabicFont"
        break

import arabic_reshaper
from bidi.algorithm import get_display
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.toolbar import MDTopAppBar
from engine import GameEngine
from db import get_save_metadata

CARD_BG = get_color_from_hex("#1E2A3A")
PRIMARY = get_color_from_hex("#4CAF50")
GOLD = get_color_from_hex("#FFC107")
GREY = get_color_from_hex("#9E9E9E")
DIM = get_color_from_hex("#B0BEC5")
RED = get_color_from_hex("#E53935")
BLUE = get_color_from_hex("#42A5F5")
PAGE_SIZE = 15

def ar(text):
    if not text: return ""
    try: return get_display(arabic_reshaper.reshape(str(text)))
    except Exception: return str(text)

def _fs():
    try:
        app = MDApp.get_running_app()
        if app and app.engine:
            return float(app.engine.settings.get("font_scale", "1.0"))
    except Exception: pass
    return 1.0

def _s(size_str):
    try: return f"{float(size_str.replace('sp', '')) * _fs():.1f}sp"
    except Exception: return size_str

def label(text, size="15sp", bold=False, color=(1, 1, 1, 1), halign="right"):
    # إضافة الخط العربي هنا
    lb = MDLabel(text=ar(text), halign=halign, font_size=_s(size), bold=bold,
                 theme_text_color="Custom", text_color=color,
                 font_name=arabic_font if arabic_font else None,
                 size_hint_y=None, height=dp(26) * _fs())
    lb.bind(width=lambda w, v: setattr(w, "text_size", (w.width - dp(8), None)))
    lb.bind(texture_size=lambda w, ts: setattr(w, "height", ts[1] + dp(4) * _fs()))
    return lb

def card(*children, bg=CARD_BG):
    box = MDBoxLayout(orientation="vertical", padding=dp(10), spacing=dp(4), adaptive_height=True)
    for ch in children: box.add_widget(ch)
    c = MDCard(orientation="vertical", padding=dp(6), size_hint_y=None,
               adaptive_height=True, radius=[14], md_bg_color=bg)
    c.add_widget(box)
    return c

def scroll(inner):
    s = MDScrollView(); s.add_widget(inner); return s

def button(text, cb, bg=None, size_hint_x=None):
    b = MDRaisedButton(text=ar(text), on_release=lambda *_: cb(), font_size=_s("13sp"), font_name=arabic_font if arabic_font else None)
    if bg: b.md_bg_color = bg
    if size_hint_x: b.size_hint_x = size_hint_x
    return b

def grid_buttons(items, cols=2):
    g = MDGridLayout(cols=cols, spacing=dp(4), size_hint_y=None, adaptive_height=True)
    for text, cb, bg in items:
        b = button(text, cb, bg=bg)
        b.size_hint_x = 1
        b.size_hint_y = None
        b.height = dp(42) * _fs()
        g.add_widget(b)
    return g

def paginator(page, total, page_size, on_prev, on_next):
    total_pages = max(1, (total + page_size - 1) // page_size)
    bar = MDBoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
    bar.add_widget(button("◀ السابق" if page > 0 else "◀", on_prev if page > 0 else lambda: None, size_hint_x=0.35))
    bar.add_widget(label(f"{page + 1} / {total_pages}", size="13sp", color=GOLD, halign="center"))
    bar.add_widget(button("التالي ▶" if page < total_pages - 1 else "▶", on_next if page < total_pages - 1 else lambda: None, size_hint_x=0.35))
    return bar

class WelcomeScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(16), padding=dp(20), adaptive_height=True)
        box.add_widget(label("⚽", size="64sp", halign="center"))
        box.add_widget(label("مدير كرة القدم", size="32sp", bold=True, color=GOLD, halign="center"))
        box.add_widget(label("النسخة النهائية 5.0", size="14sp", color=DIM, halign="center"))
        box.add_widget(label("", size="8sp"))
        box.add_widget(card(label("🎯 الهدف", size="16sp", bold=True, color=GOLD), label("قُد فريقك للفوز بالدوري والكأس والبطولة القارية.", size="13sp")))
        box.add_widget(card(label("🎮 كيف تلعب", size="16sp", bold=True, color=GOLD), label("1. اختر فتحة حفظ", size="13sp"), label("2. اضغط «تقديم أسبوع» لعبور المباريات", size="13sp"), label("3. راقب الميزانية والعقود والإصابات", size="13sp"), label("4. تنقّل عبر الأزرار السفلية", size="13sp")))
        box.add_widget(button("🚀 ابدأ اللعب", self._go, bg=PRIMARY))
        box.add_widget(button("📖 الدليل الكامل", lambda: setattr(self.app.sm, "current", "manual")))
        self.add_widget(scroll(box))
    def _go(self):
        if self.app.engine: self.app.engine.save_setting("welcome_shown", "1")
        self.app.sm.current = "saves"

class SaveSelectionScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12), adaptive_height=True)
        box.add_widget(label("💾 اختر فتحة حفظ", size="24sp", bold=True, color=GOLD))
        for i in (1, 2, 3):
            meta = get_save_metadata(f"football_manager_{i}.db")
            inner = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
            inner.add_widget(label(f"📁 الفتحة {i}", size="16sp", bold=True))
            if meta:
                inner.add_widget(label(f"🏟️ {meta['club']}", size="14sp"))
                inner.add_widget(label(f"📅 {meta['date']} | {meta['season']}", size="12sp", color=DIM))
                inner.add_widget(grid_buttons([("متابعة", lambda s=i: self._load(s), PRIMARY), ("حذف", lambda s=i: self._confirm_delete(s), RED)]))
            else:
                inner.add_widget(label("(فارغة)", size="12sp", color=GREY))
                inner.add_widget(button("إنشاء لعبة جديدة", lambda s=i: self._load(s), bg=GOLD))
            box.add_widget(card(inner))
        box.add_widget(grid_buttons([("⚙️ الإعدادات", lambda: setattr(self.app.sm, "current", "settings"), BLUE), ("📖 الدليل", lambda: setattr(self.app.sm, "current", "manual"), None)]))
        self.add_widget(scroll(box))
    def _load(self, slot):
        self.app.engine = GameEngine(f"football_manager_{slot}.db")
        self.app.advance_log = []
        self.app.sm.current = "dashboard"
    def _confirm_delete(self, slot):
        def do(*_):
            dlg.dismiss()
            path = f"football_manager_{slot}.db"
            if os.path.exists(path): os.remove(path)
            self.on_enter()
        dlg = MDDialog(title=ar("تأكيد الحذف"), text=ar(f"حذف الفتحة {slot} بالكامل؟"), buttons=[MDFlatButton(text=ar("حذف"), theme_text_color="Custom", text_color=RED, on_release=do), MDFlatButton(text=ar("إلغاء"), on_release=lambda *_: dlg.dismiss())])
        dlg.open()

class DashboardScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        d = self.app.engine.get_dashboard()
        box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8), adaptive_height=True)
        box.add_widget(card(label(d["club"], size="22sp", bold=True, color=GOLD), label(f"💰 {d['budget']:,.0f} د.ت"), label(f"💸 {d['weekly_wages']:,.0f} د.ت/أسبوع"), label(f"📅 {d['date']} | {d['season']}"), label(f"⚙️ {self._tac(d['tactic'])} | 🚑 {d['injured']}", size="13sp", color=BLUE)))
        if d.get("expiring", 0) > 0:
            box.add_widget(card(label(f"⚠️ {d['expiring']} عقد ينتهي قريبًا", size="14sp", bold=True, color=GOLD), button("مراجعة العقود", lambda: setattr(self.app.sm, "current", "contracts"), bg=GOLD), bg=get_color_from_hex("#3A2A15")))
        conf = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(4))
        conf.add_widget(label(f"🏛️ ثقة الإدارة: {d['confidence']}%"))
        conf.add_widget(MDProgressBar(value=d["confidence"], max=100, color=PRIMARY if d["confidence"] >= 50 else RED))
        conf.add_widget(label(f"🎯 {d['objective']}", size="13sp", color=DIM))
        box.add_widget(card(conf))
        if d["next_match"]:
            nm = d["next_match"]
            comp = {"league": "⚽", "cup": "🏆", "continental": "🌍"}[nm["comp"]]
            box.add_widget(card(label(f"{comp} [{nm['round']}]", size="14sp", bold=True, color=GOLD), label(f"{nm['home']} × {nm['away']}", size="16sp"), label(f"📅 {nm['date']}")))
        if d.get("position"): box.add_widget(card(label(f"📊 مركزك: #{d['position']}", size="15sp", bold=True)))
        box.add_widget(grid_buttons([("📅 أسبوع", lambda: self._advance(7), PRIMARY), ("📅 3 أيام", lambda: self._advance(3), None), ("📅 يوم", lambda: self._advance(1), None), ("📋 المباريات", lambda: setattr(self.app.sm, "current", "fixtures"), None), ("📜 التاريخ", lambda: setattr(self.app.sm, "current", "history"), None), ("🏅 الإنجازات", lambda: setattr(self.app.sm, "current", "achievements"), None), ("💾 الفتحات", lambda: setattr(self.app.sm, "current", "saves"), None), ("⚙️ الإعدادات", lambda: setattr(self.app.sm, "current", "settings"), None)]))
        self.add_widget(scroll(box))
    def _tac(self, t): return {"attacking": "هجومي", "balanced": "متوازن", "defensive": "دفاعي"}.get(t, t)
    def _advance(self, days):
        self.app.advance_log = self.app.engine.advance_days(days)
        s = self.app.engine.last_season_summary
        if s: self.app.last_summary = s; self.app.sm.current = "season_summary"
        else: self.app.sm.current = "advance"

class AdvanceScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(6), padding=dp(8))
        box.add_widget(label("📰 سجل التقدم", size="20sp", bold=True))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        for item in self.app.advance_log or []:
            t = item["type"]
            if t == "date": inner.add_widget(label(f"📅 {item['text']}", size="15sp", bold=True, color=GOLD))
            elif t == "match":
                icon = {"league": "⚽", "cup": "🏆", "continental": "🌍"}.get(item["comp"], "•")
                inner.add_widget(label(f"   {icon} {item['text']}", size="14sp"))
            elif t == "rest": inner.add_widget(label("   💤 يوم راحة", size="13sp", color=GREY))
        box.add_widget(scroll(inner))
        box.add_widget(grid_buttons([("متابعة", self._more, PRIMARY), ("رجوع", lambda: setattr(self.app.sm, "current", "dashboard"), None)]))
        self.add_widget(box)
    def _more(self):
        self.app.advance_log = self.app.engine.advance_days(7)
        s = self.app.engine.last_season_summary
        if s: self.app.last_summary = s; self.app.sm.current = "season_summary"
        else: self.on_enter()

class SquadScreen(MDScreen):
    def on_enter(self): self.page = 0; self._render()
    def _render(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label("👥 تشكيلة الفريق", size="20sp", bold=True))
        box.add_widget(grid_buttons([("⚙️ تشكيلة", lambda: setattr(self.app.sm, "current", "lineup"), None), ("🎯 تكتيك", lambda: setattr(self.app.sm, "current", "tactics"), None), ("📝 عقود", lambda: setattr(self.app.sm, "current", "contracts"), None), ("🏋️ تدريب", lambda: setattr(self.app.sm, "current", "training"), BLUE)]))
        players, total = self.app.engine.get_squad_paged(self.page, PAGE_SIZE)
        inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        for p in players:
            star = "⭐" if p["starter"] else "🪑"
            if p["injured"]: star = "🚑"
            if p["youth"]: star = "🌱" + star
            inner_ct = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
            inner_ct.add_widget(label(f"{star} [{p['pos']}] {p['name']}", size="15sp", bold=p["starter"]))
            extra = f" | 🏋️ {p['training_focus']}" if p["training_focus"] else ""
            inner_ct.add_widget(label(f"عمر {p['age']} | OVR {p['ovr']} ({p['pot']}) | {p['goals']}⚽ {p['assists']}🎯 | عقد {p['contract']}س{extra}", size="12sp", color=DIM))
            c = MDCard(orientation="vertical", padding=dp(6), size_hint_y=None, adaptive_height=True, radius=[10], md_bg_color=CARD_BG)
            c.add_widget(inner_ct)
            c.add_widget(MDFlatButton(text=ar("تفاصيل"), size_hint_y=None, height=dp(30), theme_text_color="Custom", text_color=BLUE, on_release=lambda w, pid=p["id"]: self.app.show_player(pid)))
            inner.add_widget(c)
        box.add_widget(scroll(inner))
        box.add_widget(paginator(self.page, total, PAGE_SIZE, self._prev, self._next))
        self.add_widget(box)
    def _prev(self): self.page = max(0, self.page - 1); self._render()
    def _next(self): self.page += 1; self._render()

class LineupScreen(MDScreen):
    def on_enter(self):
        self.selected = [p["id"] for p in self.app.engine.get_squad() if p["starter"] and not p["injured"]]
        self._render()
    def _render(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label(f"⚙️ التشكيلة ({len(self.selected)}/11)", size="20sp", bold=True))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(2), adaptive_height=True)
        for p in self.app.engine.get_squad():
            if p["injured"]: continue
            chosen = p["id"] in self.selected
            inner.add_widget(MDFlatButton(text=ar(f"{'✓' if chosen else '○'} [{p['pos']}] {p['name']} — {p['ovr']}"), size_hint_y=None, height=dp(42), theme_text_color="Custom", text_color=PRIMARY if chosen else DIM, on_release=lambda w, pid=p["id"]: self._toggle(pid)))
        box.add_widget(scroll(inner))
        box.add_widget(grid_buttons([("حفظ", self._save, PRIMARY), ("رجوع", lambda: setattr(self.app.sm, "current", "squad"), None)]))
        self.add_widget(box)
    def _toggle(self, pid):
        if pid in self.selected: self.selected.remove(pid)
        elif len(self.selected) < 11: self.selected.append(pid)
        else: self.app.alert("التشكيلة مكتملة"); return
        self._render()
    def _save(self):
        ok, msg = self.app.engine.set_lineup(self.selected)
        if ok: self.app.sm.current = "squad"
        else: self.app.alert(msg)

class TacticsScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(8), padding=dp(12))
        box.add_widget(label("🎯 التكتيك", size="22sp", bold=True, color=GOLD))
        d = self.app.engine.get_dashboard()
        for key, name, desc in [("attacking", "⚔️ هجومي", "هجوم +3 / دفاع -2"), ("balanced", "⚖️ متوازن", "بدون تعديل"), ("defensive", "🛡️ دفاعي", "هجوم -2 / دفاع +3")]:
            ic = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
            mark = "●" if key == d["tactic"] else "○"
            ic.add_widget(label(f"{mark} {name}", size="16sp", bold=key == d["tactic"]))
            ic.add_widget(label(desc, size="12sp", color=DIM))
            c = MDCard(orientation="vertical", padding=dp(8), size_hint_y=None, adaptive_height=True, radius=[10], md_bg_color=PRIMARY if key == d["tactic"] else CARD_BG)
            c.add_widget(ic)
            c.add_widget(MDFlatButton(text=ar("اختيار" if key != d["tactic"] else "الحالي"), theme_text_color="Custom", text_color=GOLD, on_release=lambda w, k=key: self._set(k)))
            box.add_widget(c)
        box.add_widget(button("رجوع", lambda: setattr(self.app.sm, "current", "squad")))
        self.add_widget(scroll(box))
    def _set(self, key): self.app.engine.set_tactic(key); self.on_enter()

class ContractsScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label("📝 إدارة العقود", size="20sp", bold=True))
        contracts = self.app.engine.get_expiring_contracts()
        if not contracts: box.add_widget(card(label("✅ لا عقود منتهية قريبًا", size="14sp", color=PRIMARY)))
        else:
            inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
            for p in contracts:
                ic = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
                color = RED if p["contract"] <= 0 else GOLD
                ic.add_widget(label(f"[{p['pos']}] {p['name']} — {p['ovr']}", size="15sp", bold=True))
                ic.add_widget(label(f"عمر {p['age']} | راتب {p['wage']:,.0f} | عقد {p['contract']}س", size="12sp", color=color))
                ic.add_widget(grid_buttons([("+1", lambda pid=p["id"]: self._renew(pid, 1), PRIMARY), ("+2", lambda pid=p["id"]: self._renew(pid, 2), PRIMARY), ("+3", lambda pid=p["id"]: self._renew(pid, 3), PRIMARY), ("تحرير", lambda pid=p["id"]: self._confirm_release(pid), RED)], cols=4))
                c = MDCard(orientation="vertical", padding=dp(8), size_hint_y=None, adaptive_height=True, radius=[10], md_bg_color=CARD_BG)
                c.add_widget(ic)
                inner.add_widget(c)
            box.add_widget(scroll(inner))
        box.add_widget(button("رجوع", lambda: setattr(self.app.sm, "current", "squad")))
        self.add_widget(box)
    def _renew(self, pid, years):
        ok, msg = self.app.engine.renew_contract(pid, years); self.app.alert(msg); self.on_enter()
    def _confirm_release(self, pid):
        def do(*_):
            dlg.dismiss(); ok, msg = self.app.engine.release_player(pid); self.app.alert(msg); self.on_enter()
        dlg = MDDialog(title=ar("تحرير لاعب"), text=ar("سيُصبح لاعبًا حرًّا وستدفع تعويضًا."), buttons=[MDFlatButton(text=ar("تحرير"), theme_text_color="Custom", text_color=RED, on_release=do), MDFlatButton(text=ar("إلغاء"), on_release=lambda *_: dlg.dismiss())])
        dlg.open()

class TrainingScreen(MDScreen):
    def on_enter(self): self.mode = getattr(self, "mode", "individual"); self.selected_ids = set(); self._render()
    def _render(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label("🏋️ التدريب", size="20sp", bold=True))
        box.add_widget(grid_buttons([("فردي", lambda: self._set_mode("individual"), PRIMARY if self.mode == "individual" else None), ("جماعي", lambda: self._set_mode("group"), PRIMARY if self.mode == "group" else None)]))
        if self.mode == "group": box.add_widget(label(f"مختار: {len(self.selected_ids)}", size="13sp", color=GOLD))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        for p in self.app.engine.get_squad():
            if p["injured"]: continue
            ic = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
            ic.add_widget(label(f"[{p['pos']}] {p['name']} — {p['ovr']} ({p['pot']})", size="14sp", bold=True))
            focus = p["training_focus"] or "—"
            ic.add_widget(label(f"التركيز: {focus}", size="12sp", color=GOLD if focus != "—" else DIM))
            if self.mode == "individual":
                ic.add_widget(grid_buttons([("سرعة", lambda pid=p["id"]: self._set_focus(pid, "pace"), PRIMARY if p["training_focus"] == "pace" else None), ("تسديد", lambda pid=p["id"]: self._set_focus(pid, "shooting"), PRIMARY if p["training_focus"] == "shooting" else None), ("تمرير", lambda pid=p["id"]: self._set_focus(pid, "passing"), PRIMARY if p["training_focus"] == "passing" else None), ("دفاع", lambda pid=p["id"]: self._set_focus(pid, "defending"), PRIMARY if p["training_focus"] == "defending" else None), ("بدنية", lambda pid=p["id"]: self._set_focus(pid, "physical"), PRIMARY if p["training_focus"] == "physical" else None)], cols=3))
            else:
                cb_row = MDBoxLayout(adaptive_height=True, spacing=dp(4), size_hint_y=None, height=dp(40))
                cb = MDCheckbox(active=p["id"] in self.selected_ids, size_hint=(None, None), size=(dp(40), dp(40)))
                cb.bind(active=lambda w, v, pid=p["id"]: self._toggle_no_render(pid, v))
                cb_row.add_widget(cb)
                cb_row.add_widget(label("تحديد", size="12sp"))
                ic.add_widget(cb_row)
            c = MDCard(orientation="vertical", padding=dp(6), size_hint_y=None, adaptive_height=True, radius=[10], md_bg_color=CARD_BG)
            c.add_widget(ic)
            inner.add_widget(c)
        box.add_widget(scroll(inner))
        if self.mode == "group":
            box.add_widget(label("اختر سمة للتدريب الجماعي:", size="13sp", color=GOLD))
            box.add_widget(grid_buttons([("سرعة", lambda: self._group_train("pace"), PRIMARY), ("تسديد", lambda: self._group_train("shooting"), PRIMARY), ("تمرير", lambda: self._group_train("passing"), PRIMARY), ("دفاع", lambda: self._group_train("defending"), PRIMARY), ("بدنية", lambda: self._group_train("physical"), PRIMARY)], cols=3))
        box.add_widget(button("رجوع", lambda: setattr(self.app.sm, "current", "squad")))
        self.add_widget(box)
    def _set_mode(self, mode): self.mode = mode; self.selected_ids = set(); self._render()
    def _toggle_no_render(self, pid, active):
        if active: self.selected_ids.add(pid)
        else: self.selected_ids.discard(pid)
    def _set_focus(self, pid, attr):
        ok, msg = self.app.engine.set_training_focus(pid, attr); self.app.alert(msg); self._render()
    def _group_train(self, attr):
        ok, msg = self.app.engine.group_train(list(self.selected_ids), attr); self.app.alert(msg); self.on_enter()

class StandingsScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label("🏆 ترتيب الدوري", size="20sp", bold=True))
        header = MDBoxLayout(size_hint_y=None, height=dp(32), spacing=dp(2))
        for t, w in [("#", 0.08), ("الفريق", 0.46), ("لعب", 0.1), ("ف", 0.09), ("ت", 0.09), ("خ", 0.09), ("نقاط", 0.09)]:
            header.add_widget(MDLabel(text=ar(t), size_hint_x=w, halign="center", bold=True, font_size=_s("11sp"), font_name=arabic_font if arabic_font else None))
        box.add_widget(header)
        inner = MDBoxLayout(orientation="vertical", spacing=dp(2), adaptive_height=True)
        for i, r in enumerate(self.app.engine.get_standings(), 1):
            user = r["club_id"] == self.app.engine.user_club_id
            row = MDBoxLayout(size_hint_y=None, height=dp(34), spacing=dp(2))
            if user: row.md_bg_color = (0.3, 0.7, 0.3, 0.3)
            for txt, w, bold in [(str(i), 0.08, False), (r["name"], 0.46, user), (str(r["p"]), 0.1, False), (str(r["w"]), 0.09, False), (str(r["d"]), 0.09, False), (str(r["l"]), 0.09, False), (str(r["pts"]), 0.09, True)]:
                row.add_widget(MDLabel(text=ar(txt), size_hint_x=w, halign="center", font_size=_s("12sp"), bold=bold, font_name=arabic_font if arabic_font else None))
            inner.add_widget(row)
        box.add_widget(scroll(inner))
        self.add_widget(box)

class CupsScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(grid_buttons([("🏆 كأس تونس", lambda: self._show('cup'), GOLD if self.app.cup_tab == 'cup' else None), ("🌍 القارية", lambda: self._show('continental'), GOLD if self.app.cup_tab == 'continental' else None)]))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        matches = (self.app.engine.get_cup() if self.app.cup_tab == 'cup' else self.app.engine.get_continental())
        for m in matches:
            score = (f"{m['home']} {m['hg']} - {m['ag']} {m['away']}" if m["status"] == "played" else f"{m['home']} × {m['away']}")
            inner.add_widget(card(label(f"[{m['round']}] — {m['date']}", size="12sp", color=GOLD), label(score, size="14sp", bold=True)))
        box.add_widget(scroll(inner))
        self.add_widget(box)
    def _show(self, tab): self.app.cup_tab = tab; self.on_enter()

class FixturesScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label("📋 المباريات", size="20sp", bold=True))
        tabs = []
        for key, lbl in [("all", "الكل"), ("league", "دوري"), ("cup", "كأس"), ("continental", "قارية")]:
            tabs.append((lbl, lambda k=key: self._filter(k), GOLD if self.app.fixtures_filter == key else None))
        box.add_widget(grid_buttons(tabs, cols=4))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        filt = None if self.app.fixtures_filter == 'all' else self.app.fixtures_filter
        for m in self.app.engine.get_fixtures(comp=filt):
            played = m["status"] == "played"
            score = (f"{m['home']} {m['hg']} - {m['ag']} {m['away']}" if played else f"{m['home']} × {m['away']}")
            icon = {"league": "⚽", "cup": "🏆", "continental": "🌍"}[m["comp"]]
            inner.add_widget(card(label(f"{icon} [{m['round']}] — {m['date']}", size="12sp", color=GOLD), label(score, size="14sp", bold=True), MDFlatButton(text=ar("تفاصيل"), size_hint_y=None, height=dp(30), theme_text_color="Custom", text_color=BLUE, on_release=lambda w, mid=m["match_id"]: self.app.show_match(mid))))
        box.add_widget(scroll(inner))
        self.add_widget(box)
    def _filter(self, key): self.app.fixtures_filter = key; self.on_enter()

class TransfersScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        d = self.app.engine.get_dashboard()
        box.add_widget(label(f"💼 الانتقالات — {d['budget']:,.0f}", size="16sp", bold=True))
        box.add_widget(button("📜 تاريخ الانتقالات", lambda: setattr(self.app.sm, "current", "transfer_history")))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        for p in self.app.engine.get_transfer_market(15):
            ic = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(2))
            ic.add_widget(label(f"[{p['pos']}] {p['name']} — {p['ovr']}", size="14sp", bold=True))
            ic.add_widget(label(f"{p['club']} | عمر {p['age']} | {p['value']:,.0f}", size="12sp", color=DIM))
            c = MDCard(orientation="vertical", padding=dp(6), size_hint_y=None, adaptive_height=True, radius=[10], md_bg_color=CARD_BG)
            c.add_widget(ic)
            c.add_widget(button("شراء", lambda pid=p["id"]: self._buy(pid), bg=PRIMARY))
            inner.add_widget(c)
        box.add_widget(scroll(inner))
        self.add_widget(box)
    def _buy(self, pid):
        ok, msg = self.app.engine.buy_player(pid); self.app.alert(msg)
        if ok: self.on_enter()

class FinancesScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        d = self.app.engine.get_dashboard()
        box.add_widget(label("💼 المالية", size="20sp", bold=True))
        box.add_widget(card(label(f"💰 {d['budget']:,.0f} د.ت", size="16sp", bold=True, color=PRIMARY if d['budget'] > 0 else RED), label(f"💸 رواتب: {d['weekly_wages']:,.0f} /أسبوع"), label(f"🏟️ سعة: {d['stadium']:,}")))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(2), adaptive_height=True)
        for r in self.app.engine.get_finances_log(20):
            color = PRIMARY if r["amount"] >= 0 else RED
            inner.add_widget(label(f"{r['date']} | {r['desc']} | {r['amount']:+,.0f}", size="12sp", color=color))
        box.add_widget(scroll(inner))
        self.add_widget(box)

class HistoryScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label("📜 تاريخ المواسم", size="20sp", bold=True))
        box.add_widget(button("🔄 تحديث", self.on_enter, bg=BLUE))
        history = self.app.engine.get_season_history()
        if not history: box.add_widget(card(label("لا يوجد تاريخ بعد.", size="14sp", color=DIM)))
        else:
            inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
            for h in history:
                pos = h["pos"]
                c = PRIMARY if pos and pos <= 3 else GOLD if pos and pos <= 5 else GREY
                inner.add_widget(card(label(h["season"], size="16sp", bold=True, color=GOLD), label(f"🏆 {h['league'] or '—'}", size="13sp"), label(f"🏆 {h['cup'] or '—'}", size="13sp"), label(f"🌍 {h['cont'] or '—'}", size="13sp"), label(f"⚽ {h['top'] or '—'}", size="13sp"), label(f"📊 #{pos}", size="14sp", bold=True, color=c)))
            box.add_widget(scroll(inner))
        self.add_widget(box)

class AchievementsScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        ach = self.app.engine.get_achievements()
        unlocked = sum(1 for a in ach if a["unlocked"])
        box.add_widget(label(f"🏅 الإنجازات ({unlocked}/{len(ach)})", size="20sp", bold=True))
        inner = MDBoxLayout(orientation="vertical", spacing=dp(4), adaptive_height=True)
        for a in ach:
            icon, color = ("✅", PRIMARY) if a["unlocked"] else ("🔒", GREY)
            inner.add_widget(card(label(f"{icon} {a['name']}", size="15sp", bold=a["unlocked"], color=color), label(a["desc"], size="12sp", color=DIM), label(f"📅 {a['date']}" if a["unlocked"] else "لم يُفتح", size="11sp", color=GOLD if a["unlocked"] else GREY), bg=CARD_BG if a["unlocked"] else get_color_from_hex("#151D26")))
        box.add_widget(scroll(inner))
        self.add_widget(box)

class SeasonSummaryScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        s = self.app.last_summary or {}
        box = MDBoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12), adaptive_height=True)
        box.add_widget(label("🎉 نهاية الموسم!", size="26sp", bold=True, color=GOLD))
        box.add_widget(label(s.get("season_name", ""), size="16sp", color=DIM))
        for icon, title, val in [("🏆", "بطل الدوري", s.get("league_champion")), ("🏆", "كأس تونس", s.get("cup_winner")), ("🌍", "البطولة القارية", s.get("continental_winner"))]:
            box.add_widget(card(label(f"{icon} {title}", size="14sp", color=DIM), label(val or "—", size="18sp", bold=True, color=GOLD)))
        top = s.get("top_scorer")
        if top: box.add_widget(card(label("⚽ هداف الموسم", size="14sp", color=DIM), label(top["name"], size="16sp", bold=True), label(f"{top['club']} — {top['goals']} هدف", size="13sp", color=DIM)))
        pos = s.get("user_position")
        if pos:
            c = PRIMARY if pos <= 3 else GOLD if pos <= 5 else GREY
            box.add_widget(card(label("📊 مركزك", size="14sp", color=DIM), label(f"#{pos}", size="24sp", bold=True, color=c)))
        box.add_widget(button("🚀 الموسم الجديد", self._next, bg=PRIMARY))
        self.add_widget(scroll(box))
    def _next(self):
        self.app.last_summary = None
        self.app.advance_log = []
        self.app.sm.current = "dashboard"

class TransferHistoryScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(4), padding=dp(8))
        box.add_widget(label("📜 تاريخ الانتقالات", size="20sp", bold=True))
        hist = self.app.engine.get_transfer_history(50)
        if not hist: box.add_widget(card(label("لا صفقات بعد.", size="14sp", color=DIM)))
        else:
            inner = MDBoxLayout(orientation="vertical", spacing=dp(3), adaptive_height=True)
            for t in hist:
                icon = "📥" if t["type"] == "buy" else "📤"
                c = RED if t["type"] == "buy" else PRIMARY
                inner.add_widget(card(label(f"{icon} {t['player']}", size="14sp", bold=True), label(f"{t['from']} → {t['to']}", size="12sp", color=DIM), label(f"{t['fee']:,.0f} د.ت | {t['date']}", size="12sp", color=c)))
            box.add_widget(scroll(inner))
        box.add_widget(button("رجوع", lambda: setattr(self.app.sm, "current", "transfers")))
        self.add_widget(box)

class SettingsScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(label("⚙️ الإعدادات", size="22sp", bold=True, color=GOLD))
        s = self.app.engine.settings if self.app.engine else {"font_scale":"1.0","auto_save":"1","confirm_delete":"1","confirm_release":"1"}
        box.add_widget(label("🔤 حجم الخط", size="16sp", bold=True))
        cs = float(s.get("font_scale", "1.0"))
        box.add_widget(grid_buttons([("صغير", lambda: self._set("font_scale", "0.85"), PRIMARY if cs < 0.95 else None), ("عادي", lambda: self._set("font_scale", "1.0"), PRIMARY if 0.95 <= cs <= 1.05 else None), ("كبير", lambda: self._set("font_scale", "1.2"), PRIMARY if cs > 1.05 else None)], cols=3))
        box.add_widget(label("⚙️ خيارات", size="16sp", bold=True))
        for key, name in [("auto_save", "💾 حفظ تلقائي"), ("confirm_delete", "🗑️ تأكيد الحذف"), ("confirm_release", "📝 تأكيد تحرير اللاعب")]:
            row = MDBoxLayout(adaptive_height=True, spacing=dp(4), size_hint_y=None, height=dp(44))
            cb = MDCheckbox(active=s.get(key, "1") == "1", size_hint=(None, None), size=(dp(40), dp(40)))
            cb.bind(active=lambda w, v, k=key: self._set(k, "1" if v else "0"))
            row.add_widget(cb)
            row.add_widget(label(name, size="14sp"))
            box.add_widget(row)
        if self.app.engine: box.add_widget(button("🗑️ إعادة تعيين اللعبة", self._confirm_reset, bg=RED))
        box.add_widget(grid_buttons([("📖 الدليل", lambda: setattr(self.app.sm, "current", "manual"), BLUE), ("رجوع", lambda: setattr(self.app.sm, "current", "dashboard"), None)]))
        self.add_widget(scroll(box))
    def _set(self, key, value):
        if self.app.engine: self.app.engine.save_setting(key, value)
        self.on_enter()
    def _confirm_reset(self):
        def do(*_):
            dlg.dismiss()
            if self.app.engine: self.app.engine.reset()
            self.app.sm.current = "saves"
        dlg = MDDialog(title=ar("إعادة تعيين"), text=ar("حذف كل بيانات هذه الفتحة؟"), buttons=[MDFlatButton(text=ar("إعادة"), theme_text_color="Custom", text_color=RED, on_release=do), MDFlatButton(text=ar("إلغاء"), on_release=lambda *_: dlg.dismiss())])
        dlg.open()

class ManualScreen(MDScreen):
    def on_enter(self):
        self.clear_widgets()
        box = MDBoxLayout(orientation="vertical", spacing=dp(6), padding=dp(10))
        box.add_widget(label("📖 دليل اللعبة", size="22sp", bold=True, color=GOLD))
        sections = [("🎯 الهدف", "قُد فريقك للفوز بالدوري والكأس والبطولة القارية. طوّر لاعبيك وأدر عقودهم وابنِ فريقًا لا يُقهر."), ("📅 التقدم في الوقت", "اضغط «أسبوع» لتقديم 7 أيام، أو «3 أيام»/«يوم» للتحكم الدقيق. المباريات تُلعب تلقائيًا حسب جدولها."), ("⚙️ التشكيلة والتكتيك", "اختر 11 لاعبًا يدويًا من شاشة «تشكيلة»، أو استخدم الاختيار التلقائي. التكتيك يؤثر على قوة الهجوم/الدفاع في المحاكاة."), ("💼 المالية والعقود", "تستقبل دخلًا من التذاكر. تُخصم رواتب يوميًا حسب الأيام المقدَّمة. راقب العقود—إن انتهت يصبح اللاعب حرًّا!"), ("🏋️ التدريب", "درّب لاعبيك أسبوعيًا على سمة (سرعة/تسديد/تمرير/دفاع/بدنية). التكلفة 800 د.ت/أسبوع لكل لاعب. الفرق كبير."), ("🌍 المسابقات", "الدوري: 14 مباراة لكل فريق. الكأس: 3 أدوار. القارية: 4 فرق، نصف + نهائي. الفائز يحصل على جوائز مالية."), ("🏅 الإنجازات", "12 إنجازًا تُفتح تلقائيًا عند تحقق الشروط. شاهدها في شاشة الإنجازات."), ("💾 الحفظ", "3 فتحات مستقلة. الحفظ تلقائي بعد كل تقدّم (إذا مُفعَّل في الإعدادات)."), ("🗑️ إعادة التعيين", "من الإعدادات ← «إعادة تعيين اللعبة» لبدء هذه الفتحة من جديد.")]
        for title, desc in sections: box.add_widget(card(label(title, size="16sp", bold=True, color=GOLD), label(desc, size="13sp")))
        box.add_widget(button("رجوع", lambda: setattr(self.app.sm, "current", "saves"), bg=PRIMARY))
        self.add_widget(scroll(box))

class FootballManagerApp(MDApp):
    advance_log = []
    last_summary = None
    cup_tab = 'cup'
    fixtures_filter = 'all'
    engine = None
    def build(self):
        self.title = "مدير كرة القدم"
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = "Dark"
        if (os.path.exists("football_manager.db") and not os.path.exists("football_manager_1.db")):
            try: shutil.move("football_manager.db", "football_manager_1.db")
            except Exception: pass
        self.sm = MDScreenManager()
        screens = [(WelcomeScreen, "welcome"), (SaveSelectionScreen, "saves"), (DashboardScreen, "dashboard"), (AdvanceScreen, "advance"), (SquadScreen, "squad"), (LineupScreen, "lineup"), (TacticsScreen, "tactics"), (ContractsScreen, "contracts"), (TrainingScreen, "training"), (StandingsScreen, "standings"), (CupsScreen, "cups"), (FixturesScreen, "fixtures"), (TransfersScreen, "transfers"), (FinancesScreen, "finances"), (HistoryScreen, "history"), (AchievementsScreen, "achievements"), (SeasonSummaryScreen, "season_summary"), (TransferHistoryScreen, "transfer_history"), (SettingsScreen, "settings"), (ManualScreen, "manual")]
        for cls, name in screens:
            s = cls(name=name); s.app = self; self.sm.add_widget(s)
        self.sm.current = "welcome"
        root = MDBoxLayout(orientation="vertical")
        root.add_widget(MDTopAppBar(title=ar("⚽ مدير كرة القدم"), elevation=2))
        root.add_widget(self.sm)
        nav = MDBoxLayout(size_hint_y=None, height=dp(60), md_bg_color=get_color_from_hex("#0A1219"))
        for icon, screen in [("wallet", "finances"), ("swap-horizontal", "transfers"), ("trophy", "cups"), ("chart-bar", "standings"), ("account-group", "squad"), ("home", "dashboard")]:
            nav.add_widget(MDIconButton(icon=icon, on_release=lambda w, s=screen: self._nav(s)))
        root.add_widget(nav)
        return root
    def _nav(self, screen):
        if self.engine is None and screen not in ("saves", "welcome", "manual", "settings"): self.sm.current = "saves"
        else: self.sm.current = screen
    def alert(self, msg):
        d = MDDialog(title=ar("تنبيه"), text=ar(msg), buttons=[MDFlatButton(text=ar("حسناً"), on_release=lambda *_: d.dismiss())])
        d.open()
    def show_player(self, pid):
        p = self.engine.get_player_details(pid)
        if not p: return
        content = MDBoxLayout(orientation="vertical", spacing=dp(3), adaptive_height=True, padding=dp(8), size_hint_y=None, height=dp(340))
        for txt in [f"المركز: {p['position']} | العمر: {p['age']}", f"التقييم: {p['overall_rating']} | الاحتمال: {p['potential_rating']}", f"سرعة {p['pace']} | تسديد {p['shooting']} | تمرير {p['passing']}", f"دفاع {p['defending']} | بدنية {p['physical']}", f"القيمة: {p['market_value']:,.0f} | راتب: {p['wage']:,.0f}", f"عقد: {p['contract_years']}س | مواسم: {p['seasons_at_club']}", f"ظهور: {p['appearances']} | أهداف: {p['goals']} | صناعة: {p['assists']}", f"رجل مباراة: {p['motm']} | صفراء: {p['yellow_cards']}", f"التركيز: {p['training_focus'] or '—'}", f"النادي: {p['club_name'] or 'حر'}"]: content.add_widget(label(txt, size="12sp"))
        buttons = []
        if p["club_id"] == self.engine.user_club_id: buttons.append(MDFlatButton(text=ar("بيع"), theme_text_color="Custom", text_color=RED, on_release=lambda *_: (self.engine.sell_player(pid), d.dismiss())))
        buttons.append(MDFlatButton(text=ar("إغلاق"), on_release=lambda *_: d.dismiss()))
        d = MDDialog(title=ar(f"{p['first_name']} {p['last_name']}"), type="custom", content_cls=content, buttons=buttons)
        d.open()
    def show_match(self, mid):
        events = self.engine.get_match_events(mid)
        content = MDBoxLayout(orientation="vertical", spacing=dp(2), adaptive_height=True, padding=dp(8), size_hint_y=None, height=dp(280))
        if not events: content.add_widget(label("لا توجد أحداث", size="13sp", color=DIM))
        else:
            for e in events[:20]:
                icon = {"goal": "⚽", "yellow": "🟨", "injury": "🚑"}.get(e["type"], "•")
                content.add_widget(label(f"{icon} {e['minute']}' — {e['detail']}", size="13sp"))
        d = MDDialog(title=ar("أحداث المباراة"), type="custom", content_cls=content, buttons=[MDFlatButton(text=ar("إغلاق"), on_release=lambda *_: d.dismiss())])
        d.open()

if __name__ == "__main__":
    try:
        FootballManagerApp().run()
    except Exception as e:
        import traceback
        with open("crash.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print("حدث خطأ! تم حفظ التفاصيل في ملف crash.log")