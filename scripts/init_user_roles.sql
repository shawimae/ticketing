-- User roles: super_admin, admin, end_user
-- Run this against ticketing_db to enable the user management system.

-- Ensure role column exists and can store the new values (if your column is already VARCHAR(50) or similar, this is optional)
-- ALTER TABLE users MODIFY COLUMN role VARCHAR(50) DEFAULT 'end_user';

-- Promote an existing user to super_admin (replace 'admin@example.com' with the email of your first super admin)
-- UPDATE users SET role = 'super_admin' WHERE email = 'admin@example.com' LIMIT 1;

-- Or promote by user id:
-- UPDATE users SET role = 'super_admin' WHERE idusers = 1 LIMIT 1;

-- Create the first super_admin manually (optional; usually you register first then run the UPDATE above):
-- INSERT INTO users (email, password_hash, first_name, last_name, role, is_active)
-- VALUES (
--   'superadmin@example.com',
--   -- Use Python: from werkzeug.security import generate_password_hash; print(generate_password_hash('YourSecurePassword'))
--   '$scrypt:32768:8:1$...',
--   'Super',
--   'Admin',
--   'super_admin',
--   1
-- );
