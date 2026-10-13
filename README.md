# Every day is a new day

A one-screen nightly check-in. Three small things, a note to yourself, a streak.

No account, no internet, no sync. It is a single Python file and a single JSON
file on this laptop.

## Running it

```
python "daily_reset.py"
```

Or double-click **Every day is a new day.bat** — drag it to the desktop or pin
it to the taskbar if you want it one click away. It opens the window with no
console behind it.

On the laptop this was built on there is also an `Every day is a new day.lnk`
shortcut, which starts it without even a flicker of a console. That one isn't in
the repo: it hardcodes an absolute path to `C:\Python314\pythonw.exe`, so it
would break for anyone else and the moment Python is reinstalled. Recreate it by
pointing a new shortcut at `pythonw.exe` with `daily_reset.py` as the argument.

Needs Python 3.10+ with tkinter, which the standard Windows installer includes.

## What it tracks

| | |
|---|---|
| **Moved my body** | yes / no |
| **Applications sent** | counter, counts as met at 3 |
| **Stayed inside my gaming limit** | yes / no |

A day counts toward the streak when **at least 2 of the 3** are done. The strip
at the bottom shows the last 14 days: green for 2+, amber for 1, clay for 0, and
an empty square for a day with no entry. Hover a square to see that day's score
and note.

Yesterday's note is shown just under today's note box, so you start the evening
by reading what happened the day before.

The streak counts back from today, or from yesterday if today isn't done yet —
so it doesn't read 0 every morning before you've checked in.

## Your data

Everything lives in `~/.daily_reset/entries.json` — on this machine,
`C:\Users\GR\.daily_reset\entries.json`. Plain JSON, one object per day:

```json
{
  "2026-09-12": {
    "moved": true,
    "applications": 2,
    "gaming": true,
    "note": "Two applications and a long walk. Tired but fine."
  }
}
```

Every toggle, counter change, and keystroke saves itself — there is no save
button. Writes go to a temp file in the same folder and are then swapped in, so
closing the laptop mid-write can't leave a half-written file. If the file is
ever unreadable, it's copied to `entries.json.corrupt` rather than overwritten.

Days where nothing was logged aren't written at all, so the file stays small and
an untouched day is genuinely "no entry" rather than a zeroed-out one.

To back it up or move it to another machine, copy that one file.

## Deliberately not here

No cloud sync, no accounts, no reminders or notifications, no editing past days,
and no habits beyond the three above. The point is to make checking in cheap
enough to survive months, not to build a dashboard.

## Changing the rules

The knobs are at the top of `daily_reset.py`:

```python
APP_TARGET = 3     # applications that count as "met"
GOOD_DAY = 2       # items needed for a day to count toward the streak
HISTORY_DAYS = 14
```

The palette is right above them.
