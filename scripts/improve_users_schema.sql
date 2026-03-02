-- Optional: improve users table schema for clarity and constraints
-- Run against ticketing_db. Back up first if you have important data.

USE ticketing_db;

-- 1. role: NOT NULL + default so every user has a role
UPDATE users SET role = 'end_user' WHERE role IS NULL;
ALTER TABLE users MODIFY COLUMN role VARCHAR(45) NOT NULL DEFAULT 'end_user';

-- 2. is_active: TINYINT(1) as boolean (0 = inactive, 1 = active)
--    Normalize VARCHAR to '0'/'1' then change type (MySQL converts on ALTER)
UPDATE users SET is_active = IF(TRIM(LOWER(COALESCE(is_active, ''))) IN ('1', 'true', 'yes'), '1', '0');
ALTER TABLE users MODIFY COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1;

-- 3. (Optional) first_name / last_name: NOT NULL — only if you have no NULLs
-- UPDATE users SET first_name = '' WHERE first_name IS NULL;
-- UPDATE users SET last_name = '' WHERE last_name IS NULL;
-- ALTER TABLE users MODIFY COLUMN first_name VARCHAR(45) NOT NULL DEFAULT '';
-- ALTER TABLE users MODIFY COLUMN last_name VARCHAR(45) NOT NULL DEFAULT '';
