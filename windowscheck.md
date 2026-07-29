# Windows verification — SAAT v2.1

The six things CI cannot check. Nobody has done these yet; the release notes
say so. Takes about ten minutes.

**When you are on Windows: paste this whole file back to me, with the results
block at the bottom filled in.** Put `PASS`, `FAIL` or `SKIP` on each line and
add whatever you saw. A one-word answer is fine; a screenshot of anything odd
is better.

Download `SAAT-v2.1-windows-x64-setup.exe` from
<https://github.com/sudo-megas/SAAT/releases/tag/v2.1>

---

### 1. Installer runs and completes

Run the .exe. SmartScreen will say **"Windows protected your PC"** — click
**More info**, then **Run anyway**. That is expected and documented.

- Pass: it installs without ever asking for administrator rights (no UAC prompt).
- Fail: a UAC prompt appears, or it errors out.

Tick the **desktop shortcut** option during install so check 2 can test both.

### 2. Shortcuts appear and launch

- Pass: SAAT is in the Start Menu **with its icon**, and clicking it opens the
  app. Same for the desktop shortcut.
- Fail: missing entry, generic/blank icon, or nothing happens on click.

### 3. Fonts render

Open a watch list or the empty state.

- Pass: text looks like Ubuntu (the bundled font), and numbers line up in
  columns.
- Fail: text looks like generic Arial/Segoe, or numbers are ragged — that means
  font loading failed silently.

No Japanese to check: milestone 21 deferred it, so no CJK font ships.

### 4. Tray icon and close-to-tray

- Pass: a SAAT icon sits in the notification area; right-click gives a menu;
  enabling close-to-tray and then closing the window hides it to the tray
  instead of quitting, and clicking the tray icon brings it back.
- Fail: no tray icon, or closing quits the app outright.

### 5. Data lands in the right place

**This is the important one.** Add a watch (any brand/model — it is yours, keep
it or delete it after).

Open Explorer and paste `%LOCALAPPDATA%\SAAT` into the address bar.

- Pass: `watches\<something>\watch.toml` is there.
- **Fail: the folder does not exist.** Then check
  `%LOCALAPPDATA%\Programs\SAAT` — if the watch is in there instead, the
  `.installed` marker did not get written and it is running in portable mode.
  That is the one failure the audit flagged as genuinely breaking.

### 6. Uninstall leaves the collection intact

Settings → Apps → SAAT → Uninstall.

- Pass: `%LOCALAPPDATA%\SAAT` **still exists** with your watch still in it.
- Fail: it is gone. Tell me immediately — that is the single most serious bug
  this app could have.

---

## Results — fill this in and send it back

```
1. installer completes, no admin prompt   ...
2. Start Menu + desktop shortcuts launch  ...
3. fonts render correctly                 ...
4. tray icon + close-to-tray              ...
5. data in %LOCALAPPDATA%\SAAT            ...
6. collection survives uninstall          ...

Windows version:
Anything odd:
```

Any `FAIL` and I will fix it and ship a 2.1.1.
