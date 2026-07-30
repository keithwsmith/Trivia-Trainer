# Trivia Trainer

A self-hosted trivia study app: pull questions from a legitimate open API
and study them with basic spaced repetition — from any browser, on any
device. No AI model required to run it.

Runs as a single web app (FastAPI backend + a plain HTML/CSS/JS frontend,
no build step). Because it's a web app rather than a native app per
platform, it works identically on **Windows, macOS, Linux, and iOS/iPadOS
Safari** — one deployment, no App Store, no per-platform builds.

## Why this exists

This project intentionally does **not** scrape J! Archive or the official
jeopardy.com practice tests — both explicitly prohibit scraping/republication
in their terms, and Jeopardy! content is copyrighted by Jeopardy
Productions/Sony. Instead it uses **[Open Trivia DB](https://opentdb.com)**
— a free, keyless API built explicitly for use in programming projects,
licensed CC BY-SA 4.0.

If you have your own legally-obtained clue data (typed in by hand, or
otherwise), you can load it directly with `load_manual_clues()` in
`db/loader.py`.

## Quick start (local, no Docker)

```bash
pip install -r requirements.txt
cp .env.example .env        # then edit .env, see below
uvicorn api.app:app --reload
```

Open `http://localhost:8000` in a browser on the same machine, or
`http://<your-machine's-LAN-IP>:8000` from your phone on the same
Wi-Fi network (see "Access from your iPhone" below).

## Quick start (Docker)

```bash
cp .env.example .env        # then edit .env
docker compose up --build
```

The SQLite database persists in a named Docker volume across restarts.

## Configuration (`.env`)

| Variable | Purpose |
|---|---|
| `SQLITE_DB_PATH` | Where the SQLite file lives (default `jeopardy.db`) |
| `ADMIN_TOKEN` | **Required to enable the data-loading endpoint.** Leave unset to disable it (safe default for a public deployment) |
| `HOST` / `PORT` | Bind address for `uvicorn`, if not using `--reload` directly |

Set a strong, random `ADMIN_TOKEN` before exposing this publicly — it's
the only thing gating who can trigger opentdb pulls (rate-limited, but
still an external call on your behalf) on your deployment.

## Using it

- Open the site, pick a subject tile, answer clues one at a time.
- The gear icon (top right) opens the admin panel — paste in your
  `ADMIN_TOKEN` to pull Open Trivia DB questions for a subject.
- "Focus areas" on the home screen shows your lowest-accuracy subjects
  across all past quiz attempts.

There's also a CLI (`main.py`) if you'd rather script data loading instead
of using the admin panel — see `python main.py --help`.

## Access from your iPhone (or any device on your network)

1. Find your computer's LAN IP (e.g. `ipconfig` on Windows,
   `ifconfig`/`ip addr` on macOS/Linux — look for something like
   `192.168.x.x`).
2. Run the server with `--host 0.0.0.0` (already the Docker default; for
   local runs use `uvicorn api.app:app --host 0.0.0.0 --port 8000`).
3. On your iPhone, visit `http://192.168.x.x:8000` in Safari, on the same
   Wi-Fi network. For genuine public/internet access instead of just your
   home network, deploy it to any host that can run a Docker container
   (Fly.io, Railway, a VPS, etc.) and use its public URL instead.

## Architecture

```
api/app.py          FastAPI backend: REST API + serves web/ as static files
web/                 Vanilla HTML/CSS/JS frontend, no build step
db/                  SQLite schema + connection + insert logic
sources/             Open Trivia DB client
study/               Quiz logic, spaced repetition, shared by API and CLI
main.py              CLI alternative to the admin panel
```

### Why SQLite

SQLite is a single file with no server process, and Python's `sqlite3`
module is built in on every platform this targets — nothing extra to
install for the app to run cross-platform. The FastAPI backend is the only
thing that ever touches the database file directly; every device (phone,
laptop, whatever) talks to it over HTTP, so there's one source of truth
and no client-side sync logic to write. WAL mode and a busy-timeout are
enabled (`db/connection.py`) so concurrent requests from multiple
devices don't collide.

If you outgrow a single SQLite file (heavy concurrent writes, multiple
server instances), swapping `db/connection.py` for Postgres via
`sqlalchemy` is a contained change — everything else talks to the
database only through `db/loader.py` and `study/quiz.py`.

## Schema overview

- `Subjects` — broad study areas (Presidents, Geography, ...)
- `Categories` — a named category, tagged with a subject and its source
- `Clues` — clue text, correct response, difficulty, round, source
- `Tags` / `ClueTags` — keyword search
- `QuizAttempts` — every time you're quizzed on a clue
- `StudyState` — simple SM-2-style spaced repetition schedule per clue

## Contributing

Issues and PRs welcome. The CI workflow (`.github/workflows/ci.yml`) runs
a byte-compile check and an API smoke test on every push/PR — please make
sure both pass locally (`python -m py_compile ...` and the smoke test
snippet in the workflow file) before opening a PR.

## License

MIT — see `LICENSE`.
