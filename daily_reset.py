#!/usr/bin/env python3
"""Every day is a new day - a one-screen nightly check-in.

Three small things, a note to yourself, a streak. Everything lives in a
JSON file under ~/.daily_reset and saves itself as you go.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import font as tkfont

# ---------------------------------------------------------------- palette --

BG = "#EDE7DD"        # warm off-white
CARD = "#F5F1EA"      # inputs / empty checkboxes
INK = "#1B1B1A"       # primary text
MUTED = "#5B5650"     # secondary text
LINE = "#D8D0C2"      # hairlines
SAGE = "#5C7A5C"      # done
AMBER = "#C98A2C"     # partial
CLAY = "#B6624A"      # missed
EMPTY = "#E2DBCD"     # no entry at all

# ------------------------------------------------------------------ rules --

APP_TARGET = 3        # applications that count as "met"
GOOD_DAY = 2          # items needed for a day to count toward the streak
HISTORY_DAYS = 14

DATA_DIR = Path.home() / ".daily_reset"
DATA_FILE = DATA_DIR / "entries.json"


def blank_entry() -> dict:
    return {"moved": False, "applications": 0, "gaming": False, "note": ""}


def score(entry: dict) -> int:
    """How many of the three tracked items were completed."""
    return (
        int(bool(entry["moved"]))
        + int(int(entry["applications"]) >= APP_TARGET)
        + int(bool(entry["gaming"]))
    )


def is_blank(entry: dict) -> bool:
    return entry == blank_entry()


# ------------------------------------------------------------------ store --

class Store:
    """Entries keyed by ISO date, persisted atomically."""

    def __init__(self, path: Path | None = None):
        self.path = path or DATA_FILE
        self.entries: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Keep whatever was there rather than quietly overwriting it.
            try:
                shutil.copy2(self.path, self.path.with_suffix(".json.corrupt"))
            except OSError:
                pass
            return
        if not isinstance(raw, dict):
            return
        defaults = blank_entry()
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            entry = blank_entry()
            for field, default in defaults.items():
                given = value.get(field)
                if isinstance(default, bool):
                    if isinstance(given, bool):
                        entry[field] = given
                elif isinstance(default, int):
                    if isinstance(given, int) and not isinstance(given, bool):
                        entry[field] = max(0, given)
                elif isinstance(given, str):
                    entry[field] = given
            self.entries[key] = entry

    def get(self, day: date) -> dict:
        return self.entries.setdefault(day.isoformat(), blank_entry())

    def peek(self, day: date) -> dict | None:
        """Read a day without creating an entry for it."""
        return self.entries.get(day.isoformat())

    def save(self) -> None:
        """Write to a temp file in the same directory, then swap it in, so a
        crash mid-write can never leave a half-written entries.json."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            key: entry
            for key, entry in sorted(self.entries.items())
            if not is_blank(entry)
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent,
            prefix=".entries-", suffix=".tmp", delete=False,
        )
        try:
            with handle as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(handle.name, self.path)
        except OSError:
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise

    def streak(self, today: date) -> int:
        """Consecutive good days ending today - or yesterday, if today is
        still in progress, so the count doesn't read 0 until you check in."""
        day = today
        entry = self.peek(today)
        if entry is None or score(entry) < GOOD_DAY:
            day = today - timedelta(days=1)
        count = 0
        while True:
            entry = self.peek(day)
            if entry is None or score(entry) < GOOD_DAY:
                return count
            count += 1
            day -= timedelta(days=1)


# ------------------------------------------------------------------ scale --

SCALE = 1.0  # device pixels per design unit; set once from the screen's DPI


def px(units: float) -> int:
    """Design units -> device pixels."""
    return int(round(units * SCALE))


def enable_dpi_awareness() -> None:
    """Draw at the screen's real resolution instead of being stretched by
    Windows on a scaled display. No-op off Windows."""
    try:
        import ctypes
    except ImportError:
        return
    for call in (
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(1),
        lambda: ctypes.windll.user32.SetProcessDPIAware(),
    ):
        try:
            call()
            return
        except (AttributeError, OSError):
            continue


# ------------------------------------------------------------- primitives --

def rounded_rect(canvas: tk.Canvas, x0, y0, x1, y1, r, **kw):
    points = [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


class Toggle(tk.Canvas):
    """A checkbox. Clickable when it owns its state, flat when it mirrors one."""

    def __init__(self, parent, command=None):
        self.box = px(28)
        super().__init__(parent, width=self.box, height=self.box, bg=BG,
                         highlightthickness=0, bd=0)
        self.command = command
        self.value = False
        if command is not None:
            self.configure(cursor="hand2")
            self.bind("<Button-1>", lambda _e: self.command())
        self.redraw()

    def set(self, value: bool) -> None:
        if value != self.value:
            self.value = value
            self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        edge, radius = px(2), px(8)
        far = self.box - edge
        if self.value:
            rounded_rect(self, edge, edge, far, far, radius,
                         fill=SAGE, outline=SAGE)
            self.create_line(px(9), px(14), px(13), px(19), px(20), px(9),
                             fill=CARD, width=px(3),
                             capstyle="round", joinstyle="round")
        else:
            rounded_rect(self, edge, edge, far, far, radius,
                         fill=CARD, outline=LINE)


class StepButton(tk.Canvas):
    """Small round minus / plus button."""

    def __init__(self, parent, glyph: str, command, font):
        self.box = px(30)
        super().__init__(parent, width=self.box, height=self.box, bg=BG,
                         highlightthickness=0, bd=0, cursor="hand2")
        self.glyph = glyph
        self.command = command
        self.font = font
        self.enabled = True
        self.hover = False
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.redraw()

    def _click(self, _event):
        if self.enabled:
            self.command()

    def _enter(self, _event):
        self.hover = True
        self.redraw()

    def _leave(self, _event):
        self.hover = False
        self.redraw()

    def set_enabled(self, enabled: bool) -> None:
        if enabled != self.enabled:
            self.enabled = enabled
            self.configure(cursor="hand2" if enabled else "arrow")
            self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        if not self.enabled:
            fill, ink, edge = BG, LINE, LINE
        elif self.hover:
            fill, ink, edge = SAGE, CARD, SAGE
        else:
            fill, ink, edge = CARD, INK, LINE
        inset = px(1)
        self.create_oval(inset, inset, self.box - inset, self.box - inset,
                         fill=fill, outline=edge)
        self.create_text(self.box / 2, self.box / 2, text=self.glyph,
                         fill=ink, font=self.font)


FLAME_OUTER = [(15, 1), (15, 1), (15, 3), (20, 9), (27, 17), (29, 26), (23, 37),
               (15, 40), (7, 37), (1, 26), (8, 16), (12, 8)]
FLAME_INNER = [(15, 15), (20, 21), (21, 28), (17, 35), (12, 34),
               (9, 28), (11, 22)]


def draw_flame(canvas: tk.Canvas, x: int, y: int, lit: bool) -> None:
    """A small flame in a 30x40 design-unit box anchored at (x, y)."""
    def points(units):
        flat = []
        for ux, uy in units:
            flat += [x + px(ux), y + px(uy)]
        return flat

    if lit:
        canvas.create_polygon(points(FLAME_OUTER), smooth=True, fill=CLAY,
                              outline="")
        canvas.create_polygon(points(FLAME_INNER), smooth=True, fill=AMBER,
                              outline="")
    else:
        canvas.create_polygon(points(FLAME_OUTER), smooth=True, fill=EMPTY,
                              outline=LINE)


# --------------------------------------------------------------------- app --

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Every day is a new day")
        self.configure(bg=BG)
        self.resizable(False, False)

        global SCALE
        dpi = self.winfo_fpixels("1i")
        SCALE = dpi / 96.0
        self.tk.call("tk", "scaling", dpi / 72.0)  # size fonts by real DPI

        self.pad = px(28)
        self.content_width = px(440) - 2 * self.pad

        self.store = Store()
        self.today = date.today()
        self._note_job = None

        self._build_fonts()
        self._build_ui()
        self._load_day()
        self._refresh()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(20_000, self._tick)
        self._center()

    # -- chrome ------------------------------------------------------------

    def _build_fonts(self):
        serif = "Georgia"
        sans = "Segoe UI"
        self.f_title = tkfont.Font(family=serif, size=24)
        self.f_date = tkfont.Font(family=sans, size=10)
        self.f_streak = tkfont.Font(family=serif, size=32)
        self.f_caption = tkfont.Font(family=sans, size=10)
        self.f_item = tkfont.Font(family=sans, size=12)
        self.f_sub = tkfont.Font(family=sans, size=9)
        self.f_count = tkfont.Font(family=sans, size=12)
        self.f_step = tkfont.Font(family=sans, size=14)
        self.f_label = tkfont.Font(family=sans, size=9)
        self.f_note = tkfont.Font(family=sans, size=10)
        self.f_tiny = tkfont.Font(family=sans, size=8)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = max(0, (self.winfo_screenheight() - h) // 2 - px(30))
        self.geometry(f"+{x}+{y}")

    def _rule(self, parent, pady):
        # Hairlines stay one physical pixel at any scale.
        tk.Frame(parent, bg=LINE, height=1).pack(fill="x", pady=pady)

    def _build_ui(self):
        root = tk.Frame(self, bg=BG, padx=self.pad, pady=px(16))
        root.pack(fill="both", expand=True)

        # header
        tk.Label(root, text="Every day is a new day", bg=BG, fg=INK,
                 font=self.f_title, anchor="w").pack(fill="x")
        self.lbl_date = tk.Label(root, bg=BG, fg=MUTED, font=self.f_date,
                                 anchor="w")
        self.lbl_date.pack(fill="x", pady=(px(4), 0))

        # streak
        streak = tk.Frame(root, bg=BG)
        streak.pack(fill="x", pady=(px(14), 0))
        self.flame = tk.Canvas(streak, width=px(30), height=px(42), bg=BG,
                               highlightthickness=0, bd=0)
        self.flame.pack(side="left")
        numbers = tk.Frame(streak, bg=BG)
        numbers.pack(side="left", padx=(px(12), 0))
        self.lbl_streak = tk.Label(numbers, bg=BG, fg=INK, font=self.f_streak,
                                   anchor="w")
        self.lbl_streak.pack(anchor="w")
        self.lbl_streak_caption = tk.Label(numbers, bg=BG, fg=MUTED,
                                           font=self.f_caption, anchor="w")
        self.lbl_streak_caption.pack(anchor="w", pady=(px(2), 0))

        self._rule(root, pady=(px(16), px(2)))

        self.tog_moved = self._bool_row(
            root,
            "Moved my body",
            "Push-ups, a walk, anything - doesn't matter how small.",
            lambda: self._toggle("moved"),
        )
        self._rule(root, pady=(px(2), px(2)))

        self._apps_row(root)
        self._rule(root, pady=(px(2), px(2)))

        self.tog_gaming = self._bool_row(
            root,
            "Stayed inside my gaming limit",
            "Not zero - just didn't let it swallow the day.",
            lambda: self._toggle("gaming"),
        )
        self._rule(root, pady=(px(2), px(14)))

        # note
        tk.Label(root, text="What actually happened today", bg=BG, fg=INK,
                 font=self.f_item, anchor="w").pack(fill="x")
        # width=1 stops Text's 80-character default from setting the window
        # width; pack(fill="x") stretches it to the column.
        self.note = tk.Text(root, height=3, width=1, wrap="word",
                            font=self.f_note, bg=CARD, fg=INK,
                            insertbackground=INK, relief="flat",
                            padx=px(10), pady=px(8), highlightthickness=1,
                            highlightbackground=LINE, highlightcolor=SAGE,
                            borderwidth=0)
        self.note.pack(fill="x", pady=(px(8), 0))
        self.note.bind("<KeyRelease>", self._note_changed)
        self.note.bind("<FocusOut>", lambda _e: self._commit_note())

        self.lbl_yesterday = tk.Label(root, bg=BG, fg=MUTED, font=self.f_tiny,
                                      anchor="w", justify="left",
                                      wraplength=self.content_width)
        self.lbl_yesterday.pack(fill="x", pady=(px(8), 0))

        self._rule(root, pady=(px(14), px(10)))

        # history
        tk.Label(root, text="Last 14 days", bg=BG, fg=MUTED, font=self.f_label,
                 anchor="w").pack(fill="x")
        self.history = tk.Canvas(root, width=self.content_width, height=px(46),
                                 bg=BG, highlightthickness=0, bd=0)
        self.history.pack(fill="x", pady=(px(8), 0))
        self.history.bind("<Leave>", lambda _e: self._set_history_detail(None))
        self.lbl_detail = tk.Label(root, bg=BG, fg=MUTED, font=self.f_tiny,
                                   anchor="w", justify="left",
                                   wraplength=self.content_width)
        self.lbl_detail.pack(fill="x", pady=(px(6), 0))

    def _bool_row(self, parent, title, subtitle, command) -> Toggle:
        row = tk.Frame(parent, bg=BG, cursor="hand2")
        row.pack(fill="x", pady=px(9))
        toggle = Toggle(row, command)
        toggle.pack(side="left", anchor="n")
        col = tk.Frame(row, bg=BG, cursor="hand2")
        col.pack(side="left", fill="x", expand=True, padx=(px(14), 0))
        head = tk.Label(col, text=title, bg=BG, fg=INK, font=self.f_item,
                        anchor="w", cursor="hand2")
        head.pack(fill="x")
        sub = tk.Label(col, text=subtitle, bg=BG, fg=MUTED, font=self.f_sub,
                       anchor="w", justify="left", cursor="hand2",
                       wraplength=self.content_width - px(46))
        sub.pack(fill="x", pady=(px(2), 0))
        # The whole row is the hit target - one click, anywhere.
        for widget in (row, col, head, sub):
            widget.bind("<Button-1>", lambda _e: command())
        return toggle

    def _apps_row(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", pady=px(9))
        self.tog_apps = Toggle(row)
        self.tog_apps.pack(side="left", anchor="n")

        controls = tk.Frame(row, bg=BG)
        controls.pack(side="right", anchor="n")
        self.btn_minus = StepButton(controls, "−", lambda: self._bump(-1),
                                    self.f_step)
        self.btn_minus.pack(side="left")
        self.lbl_count = tk.Label(controls, bg=BG, fg=INK, font=self.f_count,
                                  width=5)
        self.lbl_count.pack(side="left")
        self.btn_plus = StepButton(controls, "+", lambda: self._bump(1),
                                   self.f_step)
        self.btn_plus.pack(side="left")

        col = tk.Frame(row, bg=BG)
        col.pack(side="left", fill="x", expand=True, padx=(px(14), 0))
        tk.Label(col, text="Applications sent", bg=BG, fg=INK, font=self.f_item,
                 anchor="w").pack(fill="x")
        tk.Label(col, text=f"Target {APP_TARGET} a day.", bg=BG, fg=MUTED,
                 font=self.f_sub, anchor="w").pack(fill="x", pady=(px(2), 0))

    # -- state -------------------------------------------------------------

    @property
    def entry(self) -> dict:
        return self.store.get(self.today)

    def _load_day(self):
        """Pull the stored note into the box (on launch and at rollover)."""
        self.note.delete("1.0", "end")
        self.note.insert("1.0", self.entry["note"])

    def _toggle(self, field: str):
        self.entry[field] = not self.entry[field]
        self._save()
        self._refresh()

    def _bump(self, delta: int):
        self.entry["applications"] = max(0, self.entry["applications"] + delta)
        self._save()
        self._refresh()

    def _note_changed(self, _event):
        # Debounced so a long note is one write, not one per keystroke.
        if self._note_job is not None:
            self.after_cancel(self._note_job)
        self._note_job = self.after(400, self._commit_note)

    def _commit_note(self):
        if self._note_job is not None:
            self.after_cancel(self._note_job)
            self._note_job = None
        text = self.note.get("1.0", "end-1c")
        if text != self.entry["note"]:
            self.entry["note"] = text
            self._save()

    def _save(self):
        try:
            self.store.save()
        except OSError as exc:
            self.lbl_detail.configure(text=f"Couldn't save: {exc}", fg=CLAY)

    # -- rendering ---------------------------------------------------------

    def _refresh(self):
        entry = self.entry
        self.lbl_date.configure(
            text=self.today.strftime("%A, %d %B").replace(", 0", ", "))

        count = self.store.streak(self.today)
        self.lbl_streak.configure(text=str(count))
        self.lbl_streak_caption.configure(
            text="no streak yet - tonight starts one" if count == 0
            else "day streak")
        self.flame.delete("all")
        draw_flame(self.flame, 0, px(1), lit=count > 0)

        self.tog_moved.set(entry["moved"])
        self.tog_gaming.set(entry["gaming"])
        self.tog_apps.set(entry["applications"] >= APP_TARGET)
        self.lbl_count.configure(text=f"{entry['applications']} / {APP_TARGET}")
        self.btn_minus.set_enabled(entry["applications"] > 0)

        self._draw_history()
        self._show_yesterday()

    def _show_yesterday(self):
        prev = self.store.peek(self.today - timedelta(days=1))
        note = " ".join((prev or {}).get("note", "").split())
        self.lbl_yesterday.configure(
            text=f"Yesterday - {note}" if note else "", fg=MUTED)

    def _day_color(self, day: date) -> str:
        entry = self.store.peek(day)
        if entry is None or is_blank(entry):
            return EMPTY
        points = score(entry)
        if points >= GOOD_DAY:
            return SAGE
        if points == 1:
            return AMBER
        return CLAY

    def _draw_history(self):
        self.history.delete("all")
        size, gap = px(18), px(8)
        span = HISTORY_DAYS * size + (HISTORY_DAYS - 1) * gap
        left = max(0, (self.content_width - span) // 2)
        top = px(2)
        start = self.today - timedelta(days=HISTORY_DAYS - 1)
        for index in range(HISTORY_DAYS):
            day = start + timedelta(days=index)
            x = left + index * (size + gap)
            colour = self._day_color(day)
            square = rounded_rect(self.history, x, top, x + size, top + size,
                                  px(5), fill=colour,
                                  outline=LINE if colour == EMPTY else colour)
            label = self.history.create_text(
                x + size / 2, top + size + px(13), text=day.strftime("%a")[0],
                fill=INK if day == self.today else MUTED, font=self.f_tiny)
            if day == self.today:
                self.history.create_line(
                    x + px(4), top + size + px(21), x + size - px(4),
                    top + size + px(21), fill=INK, width=1)
            for item in (square, label):
                self.history.tag_bind(
                    item, "<Enter>",
                    lambda _e, d=day: self._set_history_detail(d))

    def _set_history_detail(self, day: date | None):
        if day is None:
            self.lbl_detail.configure(text="", fg=MUTED)
            return
        entry = self.store.peek(day)
        stamp = day.strftime("%a %d %b").replace(" 0", " ")
        if entry is None or is_blank(entry):
            self.lbl_detail.configure(text=f"{stamp} - nothing logged", fg=MUTED)
            return
        note = " ".join(entry["note"].split())
        detail = f"{stamp} - {score(entry)}/3"
        if note:
            detail += f"  -  {note}"
        self.lbl_detail.configure(text=detail, fg=MUTED)

    # -- lifecycle ---------------------------------------------------------

    def _tick(self):
        """Roll over to the new day if the app is left open past midnight."""
        current = date.today()
        if current != self.today:
            self._commit_note()
            self.today = current
            self._load_day()
            self._refresh()
        self.after(20_000, self._tick)

    def _on_close(self):
        self._commit_note()
        self.destroy()


if __name__ == "__main__":
    enable_dpi_awareness()
    App().mainloop()
