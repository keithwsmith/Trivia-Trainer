"""Inserts categories, subjects, and clues into the SQLite database."""
import json
from db.connection import get_connection


def get_or_create_subject(cursor, subject_name: str) -> int:
    cursor.execute("SELECT SubjectId FROM Subjects WHERE SubjectName = ?", (subject_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute(
        "INSERT INTO Subjects (SubjectName) VALUES (?)",
        (subject_name,),
    )
    return cursor.lastrowid


def get_or_create_category(
    cursor, category_name: str, subject_id: int | None, source: str, external_id: str | None = None
) -> int:
    cursor.execute(
        "SELECT CategoryId, ExternalId FROM Categories WHERE CategoryName = ? AND Source = ?",
        (category_name, source),
    )
    row = cursor.fetchone()
    if row:
        category_id, existing_external_id = row[0], row[1]
        # Backfill ExternalId on rows created before this was tracked.
        if existing_external_id is None and external_id is not None:
            cursor.execute(
                "UPDATE Categories SET ExternalId = ? WHERE CategoryId = ?",
                (external_id, category_id),
            )
        return category_id
    cursor.execute(
        """INSERT INTO Categories (CategoryName, SubjectId, Source, ExternalId)
           VALUES (?, ?, ?, ?)""",
        (category_name, subject_id, source, external_id),
    )
    return cursor.lastrowid


def get_or_create_tag(cursor, tag_name: str) -> int:
    cursor.execute("SELECT TagId FROM Tags WHERE TagName = ?", (tag_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO Tags (TagName) VALUES (?)", (tag_name,))
    return cursor.lastrowid


def insert_clue(
    cursor,
    category_id: int,
    clue_text: str,
    correct_response: str,
    source: str,
    incorrect_options: list[str] | None = None,
    value: int | None = None,
    round_name: str | None = None,
    difficulty: str | None = None,
    air_date: str | None = None,
    keywords: list[str] | None = None,
) -> int:
    cursor.execute(
        """INSERT INTO Clues
           (CategoryId, ClueText, CorrectResponse, IncorrectOptions, Value,
            Round, Difficulty, AirDate, Source, Keywords)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            category_id,
            clue_text,
            correct_response,
            json.dumps(incorrect_options) if incorrect_options else None,
            value,
            round_name,
            difficulty,
            air_date,
            source,
            ", ".join(keywords) if keywords else None,
        ),
    )
    clue_id = cursor.lastrowid

    for kw in keywords or []:
        tag_id = get_or_create_tag(cursor, kw.lower().strip())
        cursor.execute(
            "INSERT INTO ClueTags (ClueId, TagId) VALUES (?, ?)", (clue_id, tag_id)
        )

    return clue_id


def load_opentdb_results(
    results: list[dict],
    subject_name: str | None = None,
    category_name_to_id: dict[str, int] | None = None,
) -> int:
    """Loads a list of opentdb question dicts. Returns count inserted.

    category_name_to_id: optional {opentdb category name: opentdb numeric id}
    map (see OpenTDBClient.get_categories()). When given, each category's
    ExternalId column is populated/backfilled with opentdb's own id, so you
    can join back to opentdb without a name-string lookup.
    """
    conn = get_connection()
    inserted = 0
    try:
        cursor = conn.cursor()
        subject_id = get_or_create_subject(cursor, subject_name) if subject_name else None

        for r in results:
            external_id = None
            if category_name_to_id:
                opentdb_id = category_name_to_id.get(r["category"])
                external_id = str(opentdb_id) if opentdb_id is not None else None

            category_id = get_or_create_category(
                cursor, r["category"], subject_id, source="opentdb", external_id=external_id
            )
            insert_clue(
                cursor,
                category_id=category_id,
                clue_text=r["question"],
                correct_response=r["correct_answer"],
                source="opentdb",
                incorrect_options=r.get("incorrect_answers"),
                difficulty=r.get("difficulty"),
                keywords=[r["category"].lower()],
            )
            inserted += 1

        conn.commit()
    finally:
        conn.close()
    return inserted


def load_manual_clues(clues: list[dict], subject_name: str) -> int:
    """Loads clues you supply yourself -- e.g. typed in by hand, or from
    your own legally-obtained data. Each dict needs: category, clue_text,
    correct_response, and optionally difficulty, keywords.
    """
    conn = get_connection()
    inserted = 0
    try:
        cursor = conn.cursor()
        subject_id = get_or_create_subject(cursor, subject_name)

        for c in clues:
            category_id = get_or_create_category(
                cursor, c["category"], subject_id, source="manual"
            )
            insert_clue(
                cursor,
                category_id=category_id,
                clue_text=c["clue_text"],
                correct_response=c["correct_response"],
                source="manual",
                difficulty=c.get("difficulty"),
                keywords=c.get("keywords"),
            )
            inserted += 1

        conn.commit()
    finally:
        conn.close()
    return inserted
