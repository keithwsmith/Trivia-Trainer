"""Study/quiz engine: pulls clues, records attempts, tracks a basic
SM-2-style spaced repetition schedule in StudyState.

Shared by both main.py (CLI) and api/app.py (web API) so the two front
ends can never disagree about what counts as a correct answer or how
spaced repetition is updated.
"""
import datetime
from db.connection import get_connection


def check_answer(user_answer: str, correct_response: str) -> bool:
    """Simple substring match, case-insensitive. Jeopardy responses are
    phrased as questions ("Who is ...?"); this lets "lincoln" match
    "Who is Abraham Lincoln?" without requiring the exact phrasing.
    """
    if not user_answer:
        return False
    return user_answer.strip().lower() in correct_response.strip().lower()


def list_subjects() -> list[dict]:
    """Every subject with its clue count, for a home-screen picker."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.SubjectId, s.SubjectName, COUNT(c.ClueId) AS ClueCount
            FROM Subjects s
            LEFT JOIN Categories cat ON cat.SubjectId = s.SubjectId
            LEFT JOIN Clues c ON c.CategoryId = cat.CategoryId
            GROUP BY s.SubjectId, s.SubjectName
            ORDER BY s.SubjectName ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_clue(clue_id: int) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT c.ClueId, c.ClueText, c.CorrectResponse, c.Difficulty,
                   cat.CategoryName
            FROM Clues c
            JOIN Categories cat ON cat.CategoryId = c.CategoryId
            WHERE c.ClueId = ?
            """,
            (clue_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_quiz_clues(
    subject: str | None = None,
    difficulty: str | None = None,
    round_name: str | None = None,
    only_missed: bool = False,
    limit: int = 10,
) -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        query = """
            SELECT c.ClueId, c.ClueText, c.CorrectResponse, c.Difficulty, cat.CategoryName
            FROM Clues c
            JOIN Categories cat ON cat.CategoryId = c.CategoryId
            LEFT JOIN Subjects s ON s.SubjectId = cat.SubjectId
            LEFT JOIN StudyState ss ON ss.ClueId = c.ClueId
            WHERE 1 = 1
        """
        params: list = []

        if subject:
            query += " AND s.SubjectName = ?"
            params.append(subject)
        if difficulty:
            query += " AND c.Difficulty = ?"
            params.append(difficulty)
        if round_name:
            query += " AND c.Round = ?"
            params.append(round_name)
        if only_missed:
            query += " AND ss.TimesSeen > ss.TimesCorrect"

        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def record_attempt(clue_id: int, user_answer: str, was_correct: bool) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO QuizAttempts (ClueId, UserAnswer, WasCorrect) VALUES (?, ?, ?)",
            (clue_id, user_answer, 1 if was_correct else 0),
        )
        _update_study_state(cursor, clue_id, was_correct)
        conn.commit()
    finally:
        conn.close()


def _update_study_state(cursor, clue_id: int, was_correct: bool) -> None:
    cursor.execute(
        "SELECT TimesSeen, TimesCorrect, EaseFactor, IntervalDays FROM StudyState WHERE ClueId = ?",
        (clue_id,),
    )
    row = cursor.fetchone()

    if row is None:
        times_seen, times_correct, ease, interval = 0, 0, 2.5, 0
    else:
        times_seen, times_correct, ease, interval = row[0], row[1], row[2], row[3]

    times_seen += 1
    times_correct += 1 if was_correct else 0

    # very small SM-2-ish rule: correct -> grow interval, wrong -> reset
    if was_correct:
        interval = 1 if interval == 0 else round(interval * ease)
        ease = min(ease + 0.1, 3.0)
    else:
        interval = 1
        ease = max(ease - 0.2, 1.3)

    next_review = (datetime.date.today() + datetime.timedelta(days=interval)).isoformat()

    # SQLite upsert (replaces the SQL Server MERGE statement -- SQLite has
    # no MERGE, this is its native "insert or update on conflict" syntax).
    cursor.execute(
        """
        INSERT INTO StudyState
            (ClueId, TimesSeen, TimesCorrect, EaseFactor, IntervalDays, NextReviewDate, LastReviewedAt)
        VALUES
            (?, ?, ?, ?, ?, ?, STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))
        ON CONFLICT(ClueId) DO UPDATE SET
            TimesSeen = excluded.TimesSeen,
            TimesCorrect = excluded.TimesCorrect,
            EaseFactor = excluded.EaseFactor,
            IntervalDays = excluded.IntervalDays,
            NextReviewDate = excluded.NextReviewDate,
            LastReviewedAt = excluded.LastReviewedAt
        """,
        (clue_id, times_seen, times_correct, ease, interval, next_review),
    )


def weak_subjects(limit: int = 10) -> list[dict]:
    """Subjects with the lowest accuracy, for 'what should I study next'."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT s.SubjectName,
                   SUM(CASE WHEN qa.WasCorrect = 1 THEN 1 ELSE 0 END) AS Correct,
                   COUNT(*) AS Total,
                   CAST(SUM(CASE WHEN qa.WasCorrect = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*) AS Accuracy
            FROM QuizAttempts qa
            JOIN Clues c ON c.ClueId = qa.ClueId
            JOIN Categories cat ON cat.CategoryId = c.CategoryId
            JOIN Subjects s ON s.SubjectId = cat.SubjectId
            GROUP BY s.SubjectName
            ORDER BY Accuracy ASC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
