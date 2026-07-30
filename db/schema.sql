-- Jeopardy Trainer database schema
-- Run this against the "Jeopardy" database on KEITH-PERSONAL before loading any data.

IF DB_ID('Jeopardy') IS NULL
BEGIN
    RAISERROR('Database "Jeopardy" does not exist. Create it first, then re-run this script inside it.', 16, 1);
END
GO

-- ---------------------------------------------------------------------
-- Subjects: broad study areas (Presidents, Geography, Literature, ...)
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.Subjects', 'U') IS NULL
CREATE TABLE dbo.Subjects (
    SubjectId       INT IDENTITY(1,1) PRIMARY KEY,
    SubjectName     NVARCHAR(100) NOT NULL UNIQUE,
    Description     NVARCHAR(400) NULL
);
GO

-- ---------------------------------------------------------------------
-- Categories: a named Jeopardy category, tied to a broad subject
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.Categories', 'U') IS NULL
CREATE TABLE dbo.Categories (
    CategoryId      INT IDENTITY(1,1) PRIMARY KEY,
    CategoryName    NVARCHAR(200) NOT NULL,
    SubjectId       INT NULL REFERENCES dbo.Subjects(SubjectId),
    Source          NVARCHAR(50) NOT NULL,      -- 'opentdb' | 'ai_generated' | 'manual'
    ExternalId      NVARCHAR(100) NULL,         -- id from the source system, if any
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ---------------------------------------------------------------------
-- Clues: the actual clue/response pairs
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.Clues', 'U') IS NULL
CREATE TABLE dbo.Clues (
    ClueId          INT IDENTITY(1,1) PRIMARY KEY,
    CategoryId      INT NOT NULL REFERENCES dbo.Categories(CategoryId),
    ClueText        NVARCHAR(MAX) NOT NULL,
    CorrectResponse NVARCHAR(500) NOT NULL,
    IncorrectOptions NVARCHAR(MAX) NULL,        -- JSON array, mainly for opentdb multiple-choice items
    Value           INT NULL,                   -- dollar value, if known
    Round           NVARCHAR(30) NULL,           -- 'Jeopardy' | 'Double Jeopardy' | 'Final Jeopardy' | NULL
    Difficulty      NVARCHAR(20) NULL,           -- 'easy' | 'medium' | 'hard'
    AirDate         DATE NULL,
    IsDailyDouble   BIT NOT NULL DEFAULT 0,
    IsFinalJeopardy BIT NOT NULL DEFAULT 0,
    Source          NVARCHAR(50) NOT NULL,       -- 'opentdb' | 'ai_generated' | 'manual'
    Keywords        NVARCHAR(500) NULL,
    CreatedAt       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

CREATE INDEX IX_Clues_CategoryId ON dbo.Clues(CategoryId);
CREATE INDEX IX_Clues_Source ON dbo.Clues(Source);
GO

-- ---------------------------------------------------------------------
-- Keyword tags, many-to-many with Clues (lets you search "Shakespeare" etc.)
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.Tags', 'U') IS NULL
CREATE TABLE dbo.Tags (
    TagId   INT IDENTITY(1,1) PRIMARY KEY,
    TagName NVARCHAR(100) NOT NULL UNIQUE
);
GO

IF OBJECT_ID('dbo.ClueTags', 'U') IS NULL
CREATE TABLE dbo.ClueTags (
    ClueId INT NOT NULL REFERENCES dbo.Clues(ClueId),
    TagId  INT NOT NULL REFERENCES dbo.Tags(TagId),
    PRIMARY KEY (ClueId, TagId)
);
GO

-- ---------------------------------------------------------------------
-- Quiz attempts: every time the user is quizzed on a clue
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.QuizAttempts', 'U') IS NULL
CREATE TABLE dbo.QuizAttempts (
    AttemptId    INT IDENTITY(1,1) PRIMARY KEY,
    ClueId       INT NOT NULL REFERENCES dbo.Clues(ClueId),
    UserAnswer   NVARCHAR(500) NULL,
    WasCorrect   BIT NOT NULL,
    AttemptedAt  DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- ---------------------------------------------------------------------
-- Spaced repetition state, one row per clue the user has seen
-- ---------------------------------------------------------------------
IF OBJECT_ID('dbo.StudyState', 'U') IS NULL
CREATE TABLE dbo.StudyState (
    ClueId          INT PRIMARY KEY REFERENCES dbo.Clues(ClueId),
    TimesSeen       INT NOT NULL DEFAULT 0,
    TimesCorrect    INT NOT NULL DEFAULT 0,
    EaseFactor      FLOAT NOT NULL DEFAULT 2.5,
    IntervalDays    INT NOT NULL DEFAULT 0,
    NextReviewDate  DATE NULL,
    LastReviewedAt  DATETIME2 NULL
);
GO
