-- ==========================================
-- ACAD3MIC FLOW - ADMIN SYSTEM SETUP SCRIPT
-- ==========================================
-- 
-- INSTRUCTIONS:
-- 1. Replace 'your-email@example.com' at the bottom with your signup email
-- 2. Run this entire script in Supabase SQL Editor
-- 3. Check the "Results" tab for success messages

-- SECTION 1: CREATE ADMIN TABLES & COLUMNS
-- ==========================================

-- 1. Admin Users Support
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_user_profiles_admin ON user_profiles(is_admin) WHERE is_admin = TRUE;

-- 2. Humanizer Prompts Table (Version Control)
CREATE TABLE IF NOT EXISTS humanizer_prompts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version INT NOT NULL,
    prompt_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES auth.users(id), -- Changed to auth.users for safety
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    test_results JSONB
);

CREATE INDEX IF NOT EXISTS idx_humanizer_prompts_active ON humanizer_prompts(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_humanizer_prompts_version ON humanizer_prompts(version DESC);

-- Ensure only one active prompt at a time
DROP INDEX IF EXISTS idx_humanizer_prompts_one_active;
CREATE UNIQUE INDEX idx_humanizer_prompts_one_active 
    ON humanizer_prompts(is_active) 
    WHERE is_active = TRUE;

-- 3. Admin Logs Table (Audit Trail)
CREATE TABLE IF NOT EXISTS admin_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID REFERENCES auth.users(id), -- Changed to auth.users for safety
    action TEXT NOT NULL,
    target_type TEXT,
    target_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_admin_logs_created ON admin_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_logs_admin ON admin_logs(admin_id);

-- 4. System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_by UUID REFERENCES auth.users(id),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Insert default system settings
INSERT INTO system_settings (key, value) VALUES
    ('rate_limits', '{"chat": 20, "assignment": 5, "upload": 10}'::jsonb),
    ('subscription_plans', '{"basic": {"price": 699, "words": 20000}, "standard": {"price": 1499, "words": 60000}, "premium": {"price": 2999, "words": 150000}}'::jsonb),
    ('feature_flags', '{"streaming_enabled": true, "assignments_enabled": true, "chat_enabled": true}'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- SECTION 2: HELPER FUNCTIONS
-- ==========================================

CREATE OR REPLACE FUNCTION log_admin_action(
    admin_uuid UUID,
    action_name TEXT,
    target_type_val TEXT,
    target_id_val UUID,
    details_val JSONB DEFAULT NULL,
    ip_val INET DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    log_id UUID;
BEGIN
    INSERT INTO admin_logs (admin_id, action, target_type, target_id, details, ip_address)
    VALUES (admin_uuid, action_name, target_type_val, target_id_val, details_val, ip_val)
    RETURNING id INTO log_id;
    RETURN log_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION get_dashboard_stats()
RETURNS JSONB AS $$
DECLARE
    stats JSONB;
BEGIN
    SELECT jsonb_build_object(
        'total_users', (SELECT COUNT(*) FROM user_profiles),
        'paid_users', (SELECT COUNT(*) FROM user_profiles WHERE subscription_tier != 'Free'),
        'total_revenue', (SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE status = 'success'),
        'revenue_this_month', (
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE status = 'success' 
            AND created_at >= date_trunc('month', NOW())
        ),
        'total_chats', (SELECT COUNT(*) FROM chats),
        'total_assignments', (SELECT COUNT(*) FROM assignments),
        'completed_assignments', (SELECT COUNT(*) FROM assignments WHERE status = 'completed'),
        'active_users_24h', (
            SELECT COUNT(DISTINCT user_id) 
            FROM chats 
            WHERE updated_at > NOW() - INTERVAL '24 hours'
        )
    ) INTO stats;
    RETURN stats;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant permissions
GRANT EXECUTE ON FUNCTION log_admin_action TO authenticated;
GRANT EXECUTE ON FUNCTION get_dashboard_stats TO authenticated;

-- SECTION 3: MAKE USER ADMIN
-- ==========================================

-- REPLACE 'your-email@example.com' WITH YOUR ACTUAL EMAIL BELOW
UPDATE user_profiles
SET is_admin = TRUE
WHERE email = 'your-email@example.com'; 

-- Verify Update
SELECT email, is_admin FROM user_profiles WHERE is_admin = TRUE;
