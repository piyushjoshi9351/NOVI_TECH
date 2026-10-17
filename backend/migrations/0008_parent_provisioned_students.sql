-- Parent-created student accounts and explicit link activation provenance.
-- Existing accounts retain password access (must_change_password=0) and start
-- at token_version=0. Only the new provisioning service will opt students into
-- a temporary password and set their creator and activation metadata.
--
-- No legacy relationship data is rewritten: pending, revoked, active, and
-- invitation-only rows retain their exact status, scopes, and timestamps.
-- In particular, automatic activation must never populate confirmed_at as if
-- the student approved the relationship. Unknown legacy provenance stays NULL.
--
-- Idempotent on existing databases, partial retries, and fresh databases whose
-- tables have already been created from the ORM metadata at startup.

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `must_change_password` BOOLEAN NOT NULL DEFAULT 0',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users'
      AND column_name = 'must_change_password'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `token_version` INTEGER NOT NULL DEFAULT 0',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users'
      AND column_name = 'token_version'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `created_by_parent_id` INTEGER NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users'
      AND column_name = 'created_by_parent_id'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD INDEX `ix_users_created_by_parent_id` (`created_by_parent_id`)',
        'SELECT 1'
    )
    FROM information_schema.statistics
    WHERE table_schema = DATABASE() AND table_name = 'users'
      AND index_name = 'ix_users_created_by_parent_id'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD CONSTRAINT `fk_users_created_by_parent_id` FOREIGN KEY (`created_by_parent_id`) REFERENCES `users` (`id`) ON DELETE SET NULL',
        'SELECT 1'
    )
    FROM information_schema.table_constraints
    WHERE constraint_schema = DATABASE() AND table_name = 'users'
      AND constraint_name = 'fk_users_created_by_parent_id'
      AND constraint_type = 'FOREIGN KEY'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `activation_source` VARCHAR(30) NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND column_name = 'activation_source'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `parent_student_links` ADD COLUMN `activated_at` DATETIME NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'parent_student_links'
      AND column_name = 'activated_at'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
