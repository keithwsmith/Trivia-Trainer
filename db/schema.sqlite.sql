-- Jeopardy Trainer database schema (SQLite version)
-- Converted from db/schema.sql (SQL Server). Run via: python main.py init-db
--
-- Key differences from the SQL Server version:
--   * IDENTITY(1,1)      -> INTEGER PRIMARY KEY (auto-increments implicitly in SQLite)
--   * NVARCHAR/DATETIME2 -> TEXT (SQLite is dynamically typed; column types are advisory)
--   * BIT                -> INTEGER (0/1)
--   * SYSUTCDATETIME()   -> STRFTIME('%Y-%m-%d %H:%M:%f', 'now')
--   * Foreign keys are NOT enforced unless PRAGMA foreign_keys = ON is set per
--     connection -- db/connection.py does this automatically on every connect.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Subjects: broad study areas (Presidents, Geography, Literature, ...)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Subjects (
    SubjectId       INTEGER PRIMARY KEY AUTOINCREMENT,
    SubjectName     TEXT NOT NULL UNIQUE,
    Description     TEXT
);

-- ---------------------------------------------------------------------
-- Categories: a named Jeopardy category, tied to a broad subject
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Categories (
    CategoryId      INTEGER PRIMARY KEY AUTOINCREMENT,
    CategoryName    TEXT NOT NULL,
    SubjectId       INTEGER REFERENCES Subjects(SubjectId),
    Source          TEXT NOT NULL,          -- 'opentdb' | 'ai_generated' | 'manual'
    ExternalId      TEXT,                   -- id from the source system, if any
    CreatedAt       TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))
);

-- ---------------------------------------------------------------------
-- Clues: the actual clue/response pairs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Clues (
    ClueId          INTEGER PRIMARY KEY AUTOINCREMENT,
    CategoryId      INTEGER NOT NULL REFERENCES Categories(CategoryId),
    ClueText        TEXT NOT NULL,
    CorrectResponse TEXT NOT NULL,
    IncorrectOptions TEXT,                  -- JSON array, mainly for opentdb multiple-choice items
    Value           INTEGER,                -- dollar value, if known
    Round           TEXT,                   -- 'Jeopardy' | 'Double Jeopardy' | 'Final Jeopardy' | NULL
    Difficulty      TEXT,                   -- 'easy' | 'medium' | 'hard'
    AirDate         TEXT,                   -- ISO date string 'YYYY-MM-DD'
    IsDailyDouble   INTEGER NOT NULL DEFAULT 0,
    IsFinalJeopardy INTEGER NOT NULL DEFAULT 0,
    Source          TEXT NOT NULL,          -- 'opentdb' | 'ai_generated' | 'manual'
    Keywords        TEXT,
    CreatedAt       TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))
);

CREATE INDEX IF NOT EXISTS IX_Clues_CategoryId ON Clues(CategoryId);
CREATE INDEX IF NOT EXISTS IX_Clues_Source ON Clues(Source);

-- ---------------------------------------------------------------------
-- Keyword tags, many-to-many with Clues (lets you search "Shakespeare" etc.)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS Tags (
    TagId   INTEGER PRIMARY KEY AUTOINCREMENT,
    TagName TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ClueTags (
    ClueId INTEGER NOT NULL REFERENCES Clues(ClueId),
    TagId  INTEGER NOT NULL REFERENCES Tags(TagId),
    PRIMARY KEY (ClueId, TagId)
);

-- ---------------------------------------------------------------------
-- Quiz attempts: every time the user is quizzed on a clue
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS QuizAttempts (
    AttemptId    INTEGER PRIMARY KEY AUTOINCREMENT,
    ClueId       INTEGER NOT NULL REFERENCES Clues(ClueId),
    UserAnswer   TEXT,
    WasCorrect   INTEGER NOT NULL,
    AttemptedAt  TEXT NOT NULL DEFAULT (STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))
);

-- ---------------------------------------------------------------------
-- Spaced repetition state, one row per clue the user has seen
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS StudyState (
    ClueId          INTEGER PRIMARY KEY REFERENCES Clues(ClueId),
    TimesSeen       INTEGER NOT NULL DEFAULT 0,
    TimesCorrect    INTEGER NOT NULL DEFAULT 0,
    EaseFactor      REAL NOT NULL DEFAULT 2.5,
    IntervalDays    INTEGER NOT NULL DEFAULT 0,
    NextReviewDate  TEXT,
    LastReviewedAt  TEXT
);
