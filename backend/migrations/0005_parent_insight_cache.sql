-- parent_insight_cache: cache for the parent-facing "Novi's insight" card.
--
-- One row per (student_id, snapshot_hash). snapshot_hash is a SHA-256 over the
-- CONSENTED parent-safe snapshot only (see app/services/parent_projection.py),
-- so a student revoking a consent section changes the hash and the previously
-- generated insight is never served again. That is the invalidation mechanism.
--
-- This is a cache, not an audit record: it holds no consent state, no access log
-- and no raw student data. Dropping every row only costs one extra LLM call, so
-- there is nothing here worth migrating -- the table starts empty by design.
--
-- Idempotent: safe on a fresh DB that already got the table from ORM
-- create_all/init_db, and on an existing DB that has not been migrated yet.
--
-- NOTE: app/db/run_migrations.py splits this file on ";" and strips "--" lines,
-- so never put a semicolon inside a string literal below, and don't put SQL on
-- a comment line.

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'CREATE TABLE IF NOT EXISTS `parent_insight_cache` (
            `id` INTEGER NOT NULL AUTO_INCREMENT,
            `student_id` INTEGER NOT NULL,
            `snapshot_hash` VARCHAR(64) NOT NULL,
            `insight` TEXT NOT NULL,
            `source` VARCHAR(16) NOT NULL DEFAULT ''template'',
            `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `expires_at` DATETIME NOT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY `uq_parent_insight_snapshot` (`student_id`, `snapshot_hash`),
            KEY `ix_parent_insight_expires` (`expires_at`),
            KEY `ix_parent_insight_cache_student_id` (`student_id`),
            CONSTRAINT `fk_parent_insight_cache_user` FOREIGN KEY (`student_id`)
                REFERENCES `users` (`id`) ON DELETE CASCADE
        )',
        'SELECT 1'
    )
    FROM information_schema.tables
    WHERE table_schema = DATABASE() AND table_name = 'parent_insight_cache'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;