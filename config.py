"""Central config, loaded from environment variables (see .env.example)."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Path to the SQLite database file. Created automatically on first
    # `python main.py init-db` run (or on web server startup) if missing.
    SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "jeopardy.db")

    # Shared-secret header required for /api/admin/* endpoints (pulling
    # opentdb data). Leave unset to disable these endpoints entirely --
    # the default for a public deployment.
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))

    OPENTDB_BASE_URL = "https://opentdb.com"
    # opentdb rate limit is 1 request per 5 seconds per IP - keep this >= 5
    OPENTDB_REQUEST_DELAY_SECONDS = 5.5
