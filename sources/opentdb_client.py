"""Client for the Open Trivia Database (https://opentdb.com).

Data returned by this API is licensed CC BY-SA 4.0. When you display or
publish it (beyond personal study use), keep attribution to Open Trivia DB.

Docs: https://opentdb.com/api_config.php

response_code reference (returned in every /api.php response):
  0 = Success
  1 = No Results   -- query has no more matching questions available
  2 = Invalid Parameter
  3 = Token Not Found
  4 = Token Empty  -- this session token has exhausted every question for
                      this query; request a new token to see them again
  5 = Rate Limit    -- too many requests; wait and retry
"""
import html
import time
import requests
from config import Config

BASE = Config.OPENTDB_BASE_URL

# response_codes that mean "this query is genuinely out of questions",
# as opposed to a transient problem worth retrying.
EXHAUSTED_CODES = {1, 4}


class OpenTDBRateLimitError(Exception):
    """Raised when opentdb returns response_code 5 after all retries are used."""


class OpenTDBClient:
    def __init__(self, delay_seconds: float = None, max_retries: int = 3):
        self.delay = delay_seconds or Config.OPENTDB_REQUEST_DELAY_SECONDS
        self.max_retries = max_retries
        self._session_token = None

    def _get(self, path: str, params: dict) -> dict:
        resp = requests.get(f"{BASE}{path}", params=params, timeout=15)
        resp.raise_for_status()
        time.sleep(self.delay)  # respect the 1-request-per-5-seconds rate limit
        return resp.json()

    def get_categories(self) -> list[dict]:
        """Returns [{id, name}, ...] for every opentdb category."""
        data = self._get("/api_category.php", {})
        return data.get("trivia_categories", [])

    def get_session_token(self, force_new: bool = False) -> str:
        if force_new or not self._session_token:
            data = self._get("/api_token.php", {"command": "request"})
            self._session_token = data.get("token")
        return self._session_token

    def fetch_questions(
        self,
        amount: int = 50,
        category_id: int | None = None,
        difficulty: str | None = None,
        q_type: str | None = None,
    ) -> tuple[list[dict], int]:
        """Fetch up to 50 questions at a time (opentdb's per-call max).

        Returns (results, response_code). An empty results list can mean
        either "no more questions for this query" (response_code 1 or 4)
        or a real problem -- check response_code, don't just check len().
        Rate limiting (code 5) is retried automatically up to max_retries
        with an extra backoff sleep on top of the normal per-call delay.
        """
        params = {"amount": min(amount, 50), "token": self.get_session_token()}
        if category_id is not None:
            params["category"] = category_id
        if difficulty:
            params["difficulty"] = difficulty
        if q_type:
            params["type"] = q_type

        attempt = 0
        while True:
            data = self._get("/api.php", params)
            code = data.get("response_code", 0)

            if code == 5 and attempt < self.max_retries:
                attempt += 1
                time.sleep(self.delay * attempt)  # back off a bit more each retry
                continue

            if code == 5:
                raise OpenTDBRateLimitError(
                    f"Still rate-limited after {self.max_retries} retries."
                )

            results = data.get("results", [])
            for r in results:
                r["question"] = html.unescape(r["question"])
                r["correct_answer"] = html.unescape(r["correct_answer"])
                r["incorrect_answers"] = [html.unescape(a) for a in r["incorrect_answers"]]
                r["category"] = html.unescape(r["category"])

            return results, code

    def fetch_all_for_category(
        self, category_id: int, target_count: int = 200, on_progress=None
    ) -> list[dict]:
        """Repeatedly pulls batches of 50 until target_count is reached or
        the category is genuinely out of questions (response_code 1 or 4).

        Never raises: if this category hits a persistent rate limit even
        after fetch_questions' internal retries, it stops and returns
        whatever was collected so far rather than aborting the whole run
        -- important for an unattended multi-category preload.

        on_progress: optional callback(collected_count, target_count) called
        after each batch, useful for printing progress during a long pull.
        """
        collected: list[dict] = []
        while len(collected) < target_count:
            try:
                batch, code = self.fetch_questions(amount=50, category_id=category_id)
            except OpenTDBRateLimitError:
                break

            if code in EXHAUSTED_CODES or not batch:
                break

            collected.extend(batch)
            if on_progress:
                on_progress(len(collected), target_count)

        return collected[:target_count]
