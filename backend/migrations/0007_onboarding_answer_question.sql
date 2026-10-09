-- onboarding_answers.question: the exact question text shown to the student
-- when this step was asked. Since questions are now personalized from earlier
-- answers (e.g. "What makes {career} interesting to you?"), we persist what was
-- displayed so the transcript and history keep showing verbatim prompts.
-- NULL for answers recorded before this column existed.
--
-- Idempotent: checked against information_schema before altering.
SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `onboarding_answers` ADD COLUMN `question` TEXT NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'onboarding_answers'
      AND column_name = 'question'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;