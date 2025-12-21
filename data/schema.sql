-- POSTGRESQL
-- CREATE TYPE gender_enum AS ENUM ('Female', 'Male');
-- USE blogWriter;
CREATE TABLE IF NOT EXISTS BlogData (
    blogID INT PRIMARY KEY,
    blogText TEXT NOT NULL ,
    keywords TEXT DEFAULT NULL 
);
-- 7 parts
CREATE TABLE IF NOT EXISTS PromptData (
    promptID INT PRIMARY KEY,
    writing TEXT NOT NULL,
    intro TEXT NOT NULL ,
    final_cta TEXT NOT NULL ,
    FAQs TEXT NOT NULL ,
    business_description TEXT NOT NULL ,
    integrate_references TEXT DEFAULT NULL,
    short_cta TEXT NOT NULL 
);
CREATE TABLE IF NOT EXISTS BlogParts (
    blogID INT PRIMARY KEY,
    intro TEXT NOT NULL ,
    final_cta TEXT NOT NULL ,
    FAQs TEXT NOT NULL ,
    business_description TEXT NOT NULL ,
    integrate_references TEXT DEFAULT NULL,
    short_cta TEXT NOT NULL ,
    FOREIGN KEY (blogID) REFERENCES BlogData(blogID) ON DELETE CASCADE ON UPDATE CASCADE
);

-- 1) Ensure Progress exists with better defaults
CREATE TABLE IF NOT EXISTS progress (
    id BIGSERIAL PRIMARY KEY,
    entry_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    entry TIMESTAMPTZ NOT NULL,
    writing BOOLEAN DEFAULT FALSE,
    intro BOOLEAN DEFAULT FALSE,
    final_cta BOOLEAN DEFAULT FALSE,
    faqs BOOLEAN DEFAULT FALSE,
    integrate_references BOOLEAN DEFAULT FALSE,
    business_description BOOLEAN DEFAULT FALSE,
    short_cta BOOLEAN DEFAULT FALSE
);
-- 2) Enforce 1 row per day
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'progress_entry_date_uniq'
    ) THEN
        ALTER TABLE progress
        ADD CONSTRAINT progress_entry_date_uniq UNIQUE (entry_date);
    END IF;
END $$;
-- 3) function
CREATE OR REPLACE FUNCTION entry_filler()
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    -- Insert a row for today if it doesn't exist.
    -- If it already exists, do nothing and do NOT update "entry".
    INSERT INTO progress (entry, entry_date)
    VALUES (NOW(), CURRENT_DATE)
    ON CONFLICT (entry_date) DO NOTHING;
END;
$$;
-- Function: mark an agent column as TRUE for today
CREATE OR REPLACE FUNCTION mark_progress_column(p_column_name TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    valid_columns TEXT[] := ARRAY[
        'writing',
        'intro',
        'final_cta',
        'faqs',
        'business_description',
        'short_cta'
    ];
BEGIN
    -- Ensure a row for today exists
    PERFORM entry_filler();

    -- Validate column name
    IF NOT p_column_name = ANY (valid_columns) THEN
        RAISE EXCEPTION
            'Invalid column name: %. Allowed values are: %',
            p_column_name,
            array_to_string(valid_columns, ', ');
    END IF;

    -- Dynamically update the requested column for today
    EXECUTE format(
        'UPDATE progress
         SET %I = TRUE
         WHERE entry_date = CURRENT_DATE',
        p_column_name
    );
END;
$$;
-- Mark "intro" as completed today
SELECT mark_progress_column('intro');