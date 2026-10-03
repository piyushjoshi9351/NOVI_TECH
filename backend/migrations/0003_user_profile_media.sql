-- LinkedIn-style profile media + About copy on `users`.
--
-- Images are stored as data URLs (base64) so the app needs no object storage.
-- MediumText is required: MySQL TEXT caps at 64 KB, far too small for a photo.
--
-- Idempotent: safe against a fresh DB that got the schema from ORM
-- create_all/init_db, and against an existing DB that has not been migrated.

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `profile_photo` MEDIUMTEXT NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'profile_photo'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `banner_photo` MEDIUMTEXT NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'banner_photo'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `about_me` TEXT NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'about_me'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `headline` VARCHAR(255) NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'headline'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `location` VARCHAR(255) NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'location'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl := (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE `users` ADD COLUMN `links` JSON NULL',
        'SELECT 1'
    )
    FROM information_schema.columns
    WHERE table_schema = DATABASE() AND table_name = 'users' AND column_name = 'links'
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;