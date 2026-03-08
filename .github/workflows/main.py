"""
ThermalWatch — Cyberpunk thermal monitor for Samsung A50
Requires: Shizuku + rish, Kivy 2.x
"""

import subprocess, re, threading
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import (
    Color, Ellipse, Line, Rectangle, RoundedRectangle
)
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.uix.widget import Widget
from kivy.properties import NumericProperty, StringProperty, ListProperty

# ── Cyberpunk palette ──────────────────────────────────────────────────────────
BG        = (0.04, 0.02, 0.08, 1)       # near-black purple
PANEL     = (0.07, 0.04, 0.13, 1)
CYAN      = (0.0,  0.95, 1.0,  1)
MAGENTA   = (1.0,  0.08, 0.58, 1)
YELLOW    = (1.0,  0.88, 0.0,  1)

COLD      = [0.0,  0.95, 0.45, 1]       # green
WARM      = [1.0,  0.55, 0.0,  1]       # orange
HOT       = [1.0,  0.08, 0.18, 1]       # red

RISH_CMD  = "sh /data/data/com.termux/files/home/rish -c \"dumpsys thermalservice\""

Window.clearcolor = BG


# ── helpers ────────────────────────────────────────────────────────────────────
def lerp_color(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(4)]


def temp_color(val, lo=30, mid=50, hi=70):
    if val <= lo:
        return COLD[:]
    if val <= mid:
        t = (val - lo) / (mid - lo)
        return lerp_color(COLD, WARM, t)
    t = min(1.0, (val - mid) / (hi - mid))
    return lerp_color(WARM, HOT, t)


def parse_temps(raw: str):
    """Return (cpu_temp, battery_temp) from dumpsys thermalservice output."""
    cpu_val = bat_val = None
    for line in raw.splitlines():
        l = line.lower()
        m = re.search(r"[-+]?\d+\.?\d*", line)
        if not m:
            continue
        try:
            val = float(m.group())
        except ValueError:
            continue
        if cpu_val is None and any(k in l for k in
                ("cpu", "skin", "soc", "tsens_tz_sensor0", "ap_")):
            cpu_val = val
        if bat_val is None and "battery" in l:
            bat_val = val
    return (cpu_val or 0.0, bat_val or 0.0)


# ── Arc gauge widget ───────────────────────────────────────────────────────────
class ArcGauge(Widget):
    value    = NumericProperty(0)      # current temp
    max_val  = NumericProperty(100)
    label    = StringProperty("CPU")
    unit     = StringProperty("°C")
    arc_col  = ListProperty(COLD)
    rim_col  = ListProperty(list(CYAN))

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(value=self._redraw, size=self._redraw, pos=self._redraw,
                  arc_col=self._redraw, rim_col=self._redraw)

    def _redraw(self, *_):
        self.canvas.clear()
        cx, cy = self.center
        r = min(self.width, self.height) * 0.38
        thick = max(14, r * 0.18)
        sweep = 270
        start = 135

        with self.canvas:
            # ── dim track ────────────────────────────────────────────────────
            Color(0.15, 0.1, 0.25, 1)
            Line(circle=(cx, cy, r), width=thick,
                 cap="none")

            # glow rim
            Color(*self.rim_col[:3], 0.18)
            Line(circle=(cx, cy, r + thick * 0.55), width=3)

            # ── value arc ────────────────────────────────────────────────────
            ratio = min(1.0, max(0.0, self.value / self.max_val))
            arc_angle = sweep * ratio
            Color(*self.arc_col)
            if arc_angle > 1:
                Line(ellipse=(cx - r, cy - r, r * 2, r * 2,
                              start, start + arc_angle),
                     width=thick, cap="round")

            # ── inner panel ──────────────────────────────────────────────────
            panel_r = r - thick * 0.7
            Color(*PANEL)
            Ellipse(pos=(cx - panel_r, cy - panel_r),
                    size=(panel_r * 2, panel_r * 2))

            # ── tick marks ───────────────────────────────────────────────────
            import math
            Color(*self.rim_col[:3], 0.5)
            for i in range(11):
                angle_deg = start + sweep * (i / 10)
                angle_rad = math.radians(angle_deg)
                tick_len  = thick * (0.9 if i % 5 == 0 else 0.5)
                x1 = cx + (r - thick * 0.4) * math.cos(angle_rad)
                y1 = cy + (r - thick * 0.4) * math.sin(angle_rad)
                x2 = cx + (r - thick * 0.4 - tick_len) * math.cos(angle_rad)
                y2 = cy + (r - thick * 0.4 - tick_len) * math.sin(angle_rad)
                Line(points=[x1, y1, x2, y2], width=1.2)

        # ── text layers (Labels updated separately) ───────────────────────────
        self._update_labels()

    def _update_labels(self):
        # We manage labels as canvas instructions (simpler than child widgets
        # for dynamic redraws)
        pass  # Text drawn via child Label widgets created once in ThermalScreen


# ── Main screen ───────────────────────────────────────────────────────────────
class ThermalScreen(FloatLayout):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._build_bg()
        self._build_header()
        self._build_gauges()
        self._build_status()
        self._build_scanlines()
        Clock.schedule_interval(self._fetch, 3)
        self._fetch()

    # ── static background decorations ─────────────────────────────────────────
    def _build_bg(self):
        with self.canvas.before:
            Color(*BG)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
            # horizontal neon lines
            Color(*MAGENTA[:3], 0.25)
            self._h1 = Line(points=[0, 0, 0, 0], width=1)
            Color(*CYAN[:3], 0.18)
            self._h2 = Line(points=[0, 0, 0, 0], width=1)
        self.bind(size=self._update_bg, pos=self._update_bg)

    def _update_bg(self, *_):
        self._bg_rect.pos  = self.pos
        self._bg_rect.size = self.size
        w, h = self.size
        self._h1.points = [0, h * 0.55, w, h * 0.55]
        self._h2.points = [0, h * 0.45, w, h * 0.45]

    # ── scanline overlay (purely aesthetic) ───────────────────────────────────
    def _build_scanlines(self):
        # thin repeating horizontal lines every 6 px — drawn after children
        Clock.schedule_once(self._draw_scanlines, 0.1)

    def _draw_scanlines(self, *_):
        with self.canvas.after:
            Color(0, 0, 0, 0.06)
            y = 0
            while y < self.height:
                Line(points=[0, y, self.width, y], width=1)
                y += 6

    # ── header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        self.title_lbl = Label(
            text="[color=00f2ff]THERMAL[/color][color=ff1493]WATCH[/color]",
            markup=True,
            font_size="26sp",
            bold=True,
            size_hint=(1, None),
            height="50dp",
            pos_hint={"top": 1},
            halign="center",
        )
        self.add_widget(self.title_lbl)

        self.sub_lbl = Label(
            text="[color=888888]Samsung A50  ·  Shizuku Monitor[/color]",
            markup=True,
            font_size="11sp",
            size_hint=(1, None),
            height="22dp",
            pos_hint={"top": 0.93},
            halign="center",
        )
        self.add_widget(self.sub_lbl)

        # separator line
        with self.canvas:
            Color(*CYAN[:3], 0.6)
            self._sep = Line(points=[0, 0, 0, 0], width=1.2)
        self.bind(size=self._update_sep, pos=self._update_sep)

    def _update_sep(self, *_):
        w, h = self.size
        y = h * 0.88
        self._sep.points = [w * 0.05, y, w * 0.95, y]

    # ── gauges ────────────────────────────────────────────────────────────────
    def _build_gauges(self):
        # CPU gauge — left half
        self.cpu_gauge = ArcGauge(
            max_val=90,
            label="CPU",
            size_hint=(0.5, 0.45),
            pos_hint={"x": 0, "top": 0.87},
        )
        self.add_widget(self.cpu_gauge)

        # Battery gauge — right half
        self.bat_gauge = ArcGauge(
            max_val=60,
            label="BAT",
            rim_col=list(MAGENTA),
            size_hint=(0.5, 0.45),
            pos_hint={"right": 1, "top": 0.87},
        )
        self.add_widget(self.bat_gauge)

        # Value labels inside each gauge
        self.cpu_val_lbl = Label(
            text="--°C", font_size="22sp", bold=True, markup=True,
            size_hint=(0.5, 0.12),
            pos_hint={"x": 0, "top": 0.66},
            halign="center",
        )
        self.add_widget(self.cpu_val_lbl)

        self.bat_val_lbl = Label(
            text="--°C", font_size="22sp", bold=True, markup=True,
            size_hint=(0.5, 0.12),
            pos_hint={"right": 1, "top": 0.66},
            halign="center",
        )
        self.add_widget(self.bat_val_lbl)

        # Name labels
        self.cpu_name_lbl = Label(
            text="[color=00f2ff]▸ CPU[/color]", markup=True,
            font_size="13sp",
            size_hint=(0.5, 0.07),
            pos_hint={"x": 0, "top": 0.56},
            halign="center",
        )
        self.add_widget(self.cpu_name_lbl)

        self.bat_name_lbl = Label(
            text="[color=ff1493]▸ BATTERY[/color]", markup=True,
            font_size="13sp",
            size_hint=(0.5, 0.07),
            pos_hint={"right": 1, "top": 0.56},
            halign="center",
        )
        self.add_widget(self.bat_name_lbl)

    # ── status / raw readout ──────────────────────────────────────────────────
    def _build_status(self):
        self.status_lbl = Label(
            text="[color=444466]Initializing...[/color]",
            markup=True,
            font_size="10sp",
            size_hint=(0.9, 0.08),
            pos_hint={"center_x": 0.5, "y": 0.18},
            halign="center",
            valign="middle",
        )
        self.status_lbl.bind(size=self.status_lbl.setter("text_size"))
        self.add_widget(self.status_lbl)

        self.last_update_lbl = Label(
            text="",
            markup=True,
            font_size="9sp",
            size_hint=(0.9, 0.06),
            pos_hint={"center_x": 0.5, "y": 0.10},
            halign="center",
        )
        self.add_widget(self.last_update_lbl)

        # warning label (appears when HOT)
        self.warn_lbl = Label(
            text="",
            markup=True,
            font_size="14sp",
            bold=True,
            size_hint=(1, 0.08),
            pos_hint={"center_x": 0.5, "y": 0.02},
            halign="center",
        )
        self.add_widget(self.warn_lbl)

    # ── data fetch ────────────────────────────────────────────────────────────
    def _fetch(self, *_):
        threading.Thread(target=self._run_cmd, daemon=True).start()

    def _run_cmd(self):
        try:
            result = subprocess.run(
                RISH_CMD, shell=True, capture_output=True,
                text=True, timeout=8
            )
            raw = result.stdout + result.stderr
            if not raw.strip():
                raise RuntimeError("Empty output — is Shizuku running?")
            cpu, bat = parse_temps(raw)
            Clock.schedule_once(lambda _: self._update_ui(cpu, bat, raw), 0)
        except Exception as exc:
            msg = str(exc)
            Clock.schedule_once(lambda _: self._show_error(msg), 0)

    def _update_ui(self, cpu, bat, raw):
        from kivy.utils import get_color_from_hex
        import time

        # Animate gauge values
        Animation(value=cpu, duration=0.8, t="out_cubic").start(self.cpu_gauge)
        Animation(value=bat, duration=0.8, t="out_cubic").start(self.bat_gauge)

        cpu_c = temp_color(cpu, 35, 60, 80)
        bat_c = temp_color(bat, 30, 42, 55)

        self.cpu_gauge.arc_col = cpu_c
        self.bat_gauge.arc_col = bat_c

        hex_cpu = "%02x%02x%02x" % (int(cpu_c[0]*255),
                                     int(cpu_c[1]*255),
                                     int(cpu_c[2]*255))
        hex_bat = "%02x%02x%02x" % (int(bat_c[0]*255),
                                     int(bat_c[1]*255),
                                     int(bat_c[2]*255))

        self.cpu_val_lbl.text = f"[color={hex_cpu}]{cpu:.1f}°C[/color]"
        self.bat_val_lbl.text = f"[color={hex_bat}]{bat:.1f}°C[/color]"

        # status: last two meaningful lines from raw
        lines = [l.strip() for l in raw.splitlines() if l.strip()][:6]
        preview = "  |  ".join(lines[:3])
        self.status_lbl.text = f"[color=334466]{preview}[/color]"

        ts = time.strftime("%H:%M:%S")
        self.last_update_lbl.text = f"[color=222244]Last refresh: {ts}[/color]"

        # warning
        if cpu >= 75 or bat >= 50:
            self.warn_lbl.text = "[color=ff2244]⚠  HIGH TEMPERATURE  ⚠[/color]"
            anim = (Animation(opacity=0.2, duration=0.4) +
                    Animation(opacity=1.0, duration=0.4))
            anim.repeat = True
            anim.start(self.warn_lbl)
        else:
            self.warn_lbl.text = ""
            Animation.cancel_all(self.warn_lbl)
            self.warn_lbl.opacity = 1

    def _show_error(self, msg):
        self.status_lbl.text = (
            f"[color=ff4444]ERROR: {msg}[/color]"
        )
        self.cpu_val_lbl.text = "[color=444466]N/A[/color]"
        self.bat_val_lbl.text = "[color=444466]N/A[/color]"


# ── App entry ─────────────────────────────────────────────────────────────────
class ThermalWatchApp(App):
    def build(self):
        Window.clearcolor = BG
        return ThermalScreen()


if __name__ == "__main__":
    ThermalWatchApp().run()
