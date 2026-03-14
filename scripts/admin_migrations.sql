-- Admin System Database Migration
-- Run this in Supabase SQL Editor after database_functions.sql

-- 1. Admin Users Table
CREATE TABLE IF NOT EXISTS admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'admin' CHECK (role IN ('admin', 'super_admin')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_admin_users_email ON admin_users(email);
CREATE INDEX idx_admin_users_active ON admin_users(is_active) WHERE is_active = TRUE;

-- 2. Humanizer Prompts Table (Version Control)
CREATE TABLE IF NOT EXISTS humanizer_prompts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version INT NOT NULL,
    prompt_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    test_results JSONB
);

CREATE INDEX idx_humanizer_prompts_active ON humanizer_prompts(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_humanizer_prompts_version ON humanizer_prompts(version DESC);

-- Ensure only one active prompt at a time
CREATE UNIQUE INDEX idx_humanizer_prompts_one_active 
    ON humanizer_prompts(is_active) 
    WHERE is_active = TRUE;

-- 3. Admin Logs Table (Audit Trail)
CREATE TABLE IF NOT EXISTS admin_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID REFERENCES admin_users(id),
    action TEXT NOT NULL,
    target_type TEXT,
    target_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_admin_logs_created ON admin_logs(created_at DESC);
CREATE INDEX idx_admin_logs_admin ON admin_logs(admin_id);
CREATE INDEX idx_admin_logs_action ON admin_logs(action);

-- 4. System Settings Table
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_by UUID REFERENCES admin_users(id),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Update user_profiles for admin role
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_user_profiles_admin ON user_profiles(is_admin) WHERE is_admin = TRUE;

-- 6. Insert default system settings
INSERT INTO system_settings (key, value) VALUES
    ('rate_limits', '{"chat": 20, "assignment": 5, "upload": 10}'::jsonb),
    ('subscription_plans', '{"basic": {"price": 699, "words": 20000}, "standard": {"price": 1499, "words": 60000}, "premium": {"price": 2999, "words": 150000}}'::jsonb),
    ('feature_flags', '{"streaming_enabled": true, "assignments_enabled": true, "chat_enabled": true}'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- 7. Admin Helper Functions

-- Function to log admin actions
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

-- Function to get dashboard stats
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
        'assignments_this_week', (
            SELECT COUNT(*) 
            FROM assignments 
            WHERE created_at > NOW() - INTERVAL '7 days'
        ),
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

-- 8. Row Level Security for Admin Tables

-- Admin users can only be accessed by admins
ALTER TABLE admin_users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view all admin users" ON admin_users
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Admin logs are read-only for admins
ALTER TABLE admin_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can view all logs" ON admin_logs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Humanizer prompts accessible by admins
ALTER TABLE humanizer_prompts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage prompts" ON humanizer_prompts
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- System settings accessible by admins
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage settings" ON system_settings
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Success message
DO $$
BEGIN
    RAISE NOTICE '✓ Admin system tables created successfully';
    RAISE NOTICE '✓ Indexes and constraints created';
    RAISE NOTICE '✓ Helper functions created';
    RAISE NOTICE '✓ RLS policies enabled';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '1. Create your first admin user:';
    RAISE NOTICE '   INSERT INTO user_profiles (email, is_admin) VALUES (''admin@example.com'', true);';
    RAISE NOTICE '2. Deploy backend admin API';
END $$;
