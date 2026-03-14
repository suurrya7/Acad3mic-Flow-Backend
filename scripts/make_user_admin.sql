-- RUN THIS IN SUPABASE SQL EDITOR

-- 1. Replace 'your-email@example.com' with the email you used to sign up
-- 2. Click "Run"

UPDATE user_profiles
SET is_admin = TRUE
WHERE email = 'your-email@example.com';  -- <--- CHANGE THIS EMAIL

-- Verify the update
SELECT email, is_admin FROM user_profiles WHERE is_admin = TRUE;
