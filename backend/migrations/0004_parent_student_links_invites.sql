-- parent_student_links: consent-based linking + email invitations.
--
-- Turns the old "link instantly by known email" table into a real consent flow:
--   * student_id becomes NULLABLE so a parent can invite an email that has no
--     Novi account yet (an invitation-only link, resolved on the student's first
--     verified signup/login -- see app/services/parent_links.py).
--   * status / confirmed_at / revoked_at carry the pending -> active -> revoked
--     lifecycle. Nothing is ever auto-activated.
--   * invited_email + invite_token_hash + expires_at identify an outstanding
--     invite. Only a SHA-256 HASH of the token is stored, the raw token is only
--     ever handed to the invite sender (stubbed -- see app/services/parent_invites.py).
--   * scopes holds the student-chosen sharing consent, e.g. {"basic": true}.
--
-- Existing rows are grandfathered as ACTIVE with the default scope so current
-- parents keep working, they were only ever created by an explicit action.
--
-- Idempotent: safe on a fresh DB that already got the schema from ORM
-- create_all/init_db, and on an existing DB that has not been migrated yet.
--
-- NOTE: app/db/run_migrations.py splits this file on "," and strips "--" lines,
-- so never use a semicolon inside a string literal below, and never put
-- meaningful content on a comment line that must survive.

-- --------------------------------------------------------------- new columns
SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `status` VARCHAR(30) NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'status'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `invited_email` VARCHAR(255) NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'invited_email'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `invite_token_hash` VARCHAR(64) NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'invite_token_hash'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `expires_at` DATETIME NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'expires_at'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `confirmed_at` DATETIME NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'confirmed_at'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `revoked_at` DATETIME NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'revoked_at'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `scopes` JSON NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'scopes'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------------------------------- student_id -> nullable
-- One row per (parent, email-or-student) target, NULL student_id means "invite
-- not yet claimed by a real account".
SET @ddl := (
    SELECT IF(
        COUNT(*) > 0,
        'ALTER TABLE `parent_student_links` MODIFY COLUMN `student_id` INTEGER NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND column_name = 'student_id' AND is_nullable = 'NO'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Raw/legacy inserts that omit `label` would otherwise fail on NOT NULL.
SET @ddl := (
    SELECT IF(
        COUNT(*) > 0,
        'ALTER TABLE `parent_student_links` MODIFY COLUMN `label` VARCHAR(100) NOT NULL DEFAULT ''Child''',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links' AND column_name = 'label'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ----------------------------------------------------------------- backfill
-- Grandfather pre-existing links as ACTIVE with the default consent scope.
-- JSON_OBJECT keeps the literal out of a quoted string so the naive "," split
-- in run_migrations cannot break.
UPDATE `parent_student_links`
SET `status` = 'active',
    `scopes` = JSON_OBJECT('basic', TRUE),
    `confirmed_at` = COALESCE(`confirmed_at`, `created_at`)
WHERE `status` IS NULL;

-- ------------------------------------------------------------- final typing
SET @ddl := (
    SELECT IF(
        COUNT(*) > 0,
        'ALTER TABLE `parent_student_links` MODIFY COLUMN `status` VARCHAR(30) NOT NULL DEFAULT ''pending''',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND column_name = 'status' AND is_nullable = 'YES'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) > 0,
        'ALTER TABLE `parent_student_links` MODIFY COLUMN `scopes` JSON NOT NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND column_name = 'scopes' AND is_nullable = 'YES'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------- de-dup before UQs
-- Defensive: an older DB could contain duplicate (parent_id, student_id) rows,
-- which would make the UNIQUE index below fail and block the whole migration.
-- Keeps the lowest id, only ever removes exact duplicates.
SET @dupe := (
    SELECT COUNT(*) FROM (
        SELECT `parent_id`, `student_id`
        FROM `parent_student_links`
        WHERE `student_id` IS NOT NULL
        GROUP BY `parent_id`, `student_id`
        HAVING COUNT(*) > 1
    ) d
);
SET @ddl := (
    SELECT IF(
        @dupe > 0,
        'DELETE p1 FROM `parent_student_links` p1 JOIN `parent_student_links` p2 ON p1.`parent_id` = p2.`parent_id` AND p1.`student_id` = p2.`student_id` AND p1.`id` > p2.`id`',
        'SELECT 1'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @dupe := (
    SELECT COUNT(*) FROM (
        SELECT `parent_id`, `invited_email`
        FROM `parent_student_links`
        WHERE `invited_email` IS NOT NULL
        GROUP BY `parent_id`, `invited_email`
        HAVING COUNT(*) > 1
    ) d
);
SET @ddl := (
    SELECT IF(
        @dupe > 0,
        'DELETE p1 FROM `parent_student_links` p1 JOIN `parent_student_links` p2 ON p1.`parent_id` = p2.`parent_id` AND p1.`invited_email` = p2.`invited_email` AND p1.`id` > p2.`id`',
        'SELECT 1'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ------------------------------------------------------------ constraints
SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD UNIQUE KEY `uq_parent_student_links_parent_student` (`parent_id`, `student_id`)',
        'SELECT 1'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND index_name = 'uq_parent_student_links_parent_student'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD UNIQUE KEY `uq_parent_student_links_parent_invited` (`parent_id`, `invited_email`)',
        'SELECT 1'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND index_name = 'uq_parent_student_links_parent_invited'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD INDEX `ix_parent_student_links_student_status` (`student_id`, `status`)',
        'SELECT 1'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND index_name = 'ix_parent_student_links_student_status'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD INDEX `ix_parent_student_links_invited_email` (`invited_email`)',
        'SELECT 1'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND index_name = 'ix_parent_student_links_invited_email'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- A link must always have something to resolve to: a real student account, or
-- an email address we are waiting on.
SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD CONSTRAINT `ck_parent_student_links_target` CHECK (`student_id` IS NOT NULL OR `invited_email` IS NOT NULL)',
        'SELECT 1'
    )
    FROM information_schema.table_constraints
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND constraint_name = 'ck_parent_student_links_target'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
