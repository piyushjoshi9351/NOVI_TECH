-- onboarding_answers.reply: Novi's warm, LLM-written transition line for the
-- student's answer (e.g. reassurance after "I don't know"). NULL when the step
-- got no empathetic reply. Written when the answer is recorded and rendered
-- back in the flow transcript (app/routers/onboarding.py), so it survives
-- page reloads and intermediate state refreshes.
--
-- Idempotent: checked against information_schema before altering.
SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `onboarding_answers` ADD COLUMN `reply` TEXT NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE()
      AND table_name = 'onboarding_answers'
      AND column_name = 'reply'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;