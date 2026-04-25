# Epic Provisioning Engine

> A full-stack browser automation suite for bulk Epic Games account management — built with Python, botasaurus-driver, and ADB-based mobile IP rotation.

---

## Overview

Epic Provisioning Engine is a modular automation platform with three independent operational modes, all controlled through a unified dark-themed GUI dashboard. The system handles the complete Epic Games account lifecycle: **registration**, **free game claiming**, and **receipt verification** — with built-in anti-detection, CAPTCHA pause handling, 2FA resolution via IMAP, and dynamic IP rotation over USB-tethered Android devices.

---

## Architecture

```
epic-engine/
├── gui.py                  # CustomTkinter dashboard — unified control panel
├── create_epic_acc.py      # Mode 1: Bulk account registration engine
├── claim_games.py          # Mode 2: Free game claim automation
├── check_games.py          # Mode 3: IMAP-based receipt verification
├── human_simulator.py      # Browser abstraction layer (botasaurus-driver)
├── ip_rotator.py           # ADB/Android airplane-mode IP rotation
├── mail_reader.py          # Rambler IMAP — Epic 2FA code extractor
├── requirements.txt        # Python dependencies
├── accounts/               # Output: registered accounts (DisplayName:Email:Password)
├── game_accounts/<slug>/   # Output: per-game claim & check results
├── logs/                   # Session terminal dumps
├── cookies/ & profiles/    # Browser persistence
└── screenshots/            # Debug captures
```

---

## Modules

### `gui.py` — Dashboard
CustomTkinter-based control panel with live metrics: Network IP (auto-refreshed every 5s), loaded account count, success/fail counters, uptime timer, and ETA estimate. Redirects `stdout` to an embedded terminal widget. Supports Start / Pause / Resume / Emergency Stop with per-module shared state flags propagated to all three engines simultaneously.

Smart filtering on engine start: already-processed accounts are skipped automatically based on per-mode success file lookups, preventing duplicate work across sessions.

### `create_epic_acc.py` — Account Creator
Automates the full Epic Games registration flow end-to-end:

1. Date-of-birth page (randomized DOB, 1990–2003 range)
2. Email submission via React-compatible JS `InputEvent` injection
3. Registration form: random Turkish first/last name from curated lists, unique display name generation (16 formats, deduplication against existing success file)
4. Terms of service acceptance
5. Email verification code retrieval via `mail_reader`
6. CAPTCHA detection with human pause (waits for manual solve, then continues automatically)

Retry logic: up to 2 attempts per account with a fresh browser instance per retry. Auto-retry pass runs at the end of the batch for all failures.

### `claim_games.py` — Game Claimer
Logs into existing accounts and claims a target free game by Epic Store URL:

1. Login with React-safe JS value injection (handles special characters via `json.dumps`)
2. Post-login flow: CAPTCHA handling, 2FA code injection (digit-by-digit via `mail_reader`), EULA auto-accept, age gate bypass
3. Game page navigation with modal cleanup loop
4. "Get" button click → smart "Place Order" searcher (scans both main DOM and iframes)
5. Order confirmation detection (`Thanks for your order!` / `Ready to install`)

Session drop detection (redirect back to `/id/login`) triggers retry. Already-owned games are marked as success and skipped.

### `check_games.py` — Receipt Checker
IMAP-based receipt verification without opening a browser. Connects to Rambler accounts, scans the last 15 emails across `INBOX`, `Spam`, `Junk`, and `Чеки` (Russian "Receipts" folder) for Epic Games invoice keywords (`receipt`, `invoice`, `order id`). Auto-skips already-verified emails within and across sessions using an in-memory set synced to the success file.

### `human_simulator.py` — Browser Abstraction Layer
Wraps `botasaurus-driver` with human-behavior primitives:

- `human_type()`: Gaussian-distributed per-character delay (WPM-based), extra pauses on punctuation/spaces
- `clear_and_type()`: React-safe input clearing via JS property descriptor override + `InputEvent` dispatch
- `think_pause()`, `micro_pause()`: randomized wait helpers
- Cookie save/load, screenshot capture, element waiting with graceful `None` returns
- Profile persistence via `botasaurus-driver` profile paths

### `ip_rotator.py` — Mobile IP Rotator
Controls an ADB-connected Android device (tested on Samsung S24 / Android 11+) using real airplane mode commands:

```
adb shell cmd connectivity airplane-mode enable/disable
```

Rotation strategy: aggressive retry loop with escalating airplane-mode hold duration (base 5s + 10s per attempt). Verifies IP change via `api.ipify.org` before confirming success. Triggers every N accounts (configurable, default: 3). First rotation is forced on system startup.

### `mail_reader.py` — IMAP 2FA Extractor
Connects to `imap.rambler.ru:993` (SSL). Records current mail IDs across all folders before the verification email is triggered, then polls only for genuinely new messages — eliminating false positives from old Epic emails. Extracts 6-digit codes via a priority-ordered regex chain covering multiple Epic email HTML layouts.

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up ADB

`adb.exe` is **not included** in this repository (binary files should not be version-controlled).  
Download the Android Platform Tools from the official source:

**→ https://developer.android.com/tools/releases/platform-tools**

Extract and either place `adb` in the project root or add it to your system `PATH`.  
USB Debugging must be enabled on your Android device.

### 3. Account file format

Prepare a `.txt` file with one account per line:

```
# Create Accounts mode
email@rambler.ru:password

# Claim / Check mode
DisplayName:email@rambler.ru:password
```

---

## Usage

```bash
python gui.py
```

1. Load account file via **📁 Load Account File**
2. Select operation mode (Create / Claim / Check)
3. For Claim/Check: paste the Epic Store game URL
4. Toggle **Mobile IP Rotator** if ADB device is connected
5. Click **▶ START ENGINE**

Results are written to:
- `accounts/successfull_accounts.txt` (Create mode)
- `game_accounts/<game-slug>/successfull_accounts.txt` (Claim mode)
- `game_accounts/<game-slug>/checked_accounts.txt` (Check mode)

---

## Tech Stack

| Layer | Technology |
|---|---|
| GUI | Python · CustomTkinter |
| Browser Automation | botasaurus-driver (Chromium) |
| Anti-Detection | Human typing simulation · Gaussian delay · JS React-safe input injection |
| CAPTCHA Handling | Pause-and-resume with visual GUI signal |
| Email / 2FA | Python imaplib · Rambler IMAP SSL |
| IP Rotation | ADB · Android airplane mode · api.ipify.org |
| Concurrency | Python threading (daemon worker thread per session) |
| Persistence | Plain-text account logs · pickle cookies · botasaurus profiles |

---

## Key Design Decisions

**React-safe input injection** — Standard `element.send_keys()` fails on React-controlled inputs because React's synthetic event system ignores direct DOM value writes. The engine uses the native `HTMLInputElement` value setter via `Object.getOwnPropertyDescriptor` and dispatches `input`/`change`/`blur` events manually, keeping React state in sync.

**Stateful skip filtering** — On each engine start, already-successful account emails are loaded from the output files into a `set` and filtered out before the batch begins. This makes runs fully idempotent — safe to stop and restart at any point without duplicate processing.

**Escalating airplane-mode rotation** — Mobile operators often reassign the same IP on short reconnects. The rotator combats this by holding airplane mode for progressively longer intervals (15s → 25s → 35s...) until a genuinely different IP is confirmed.

**Per-module SharedState** — Each engine module (`create_epic_acc`, `claim_games`, `check_games`) exposes its own `SharedState` class with `is_running` and `is_paused` flags. The GUI propagates Stop/Pause signals to all three simultaneously, allowing safe interruption at any point in the automation loop without thread killing.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
