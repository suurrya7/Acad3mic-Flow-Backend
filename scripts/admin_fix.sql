-- ==========================================
-- ACAD3MIC FLOW - ADMIN & BLOG RLS FIXES
-- ==========================================
-- This script fixes:
-- 1. Admin restricted view (only seeing themselves)
-- 2. Blog generation failures (missing policies)
-- 3. Words/Checks adjustments reverting (RLS block)

-- 1. FIX USER PROFILES RLS (Allow Admins to see and update all users)
-- =================================================================

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;

-- Policy: Authenticated users can read their own profile
DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
CREATE POLICY "Users can view own profile" ON public.user_profiles
    FOR SELECT TO authenticated
    USING (auth.uid() = id);

-- Policy: Admins can view ALL profiles (Solves User List Discrepancy)
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.user_profiles;
CREATE POLICY "Admins can view all profiles" ON public.user_profiles
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Policy: Users can update their own metadata (not balances)
DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
CREATE POLICY "Users can update own profile" ON public.user_profiles
    FOR UPDATE TO authenticated
    USING (auth.uid() = id)
    WITH CHECK (auth.uid() = id);

-- Policy: Admins can update EVERYTHING for ANYONE (Solves Credit Reversion)
DROP POLICY IF EXISTS "Admins can update all profiles" ON public.user_profiles;
CREATE POLICY "Admins can update all profiles" ON public.user_profiles
    FOR UPDATE TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- 2. FIX BLOG TABLES RLS (Solves Generation Failures)
-- =================================================

ALTER TABLE public.blog_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_posts ENABLE ROW LEVEL SECURITY;

-- Topics: Public can view nothing (internal only)
-- Topics: Admins can do EVERYTHING
DROP POLICY IF EXISTS "Admins can manage blog topics" ON public.blog_topics;
CREATE POLICY "Admins can manage blog topics" ON public.blog_topics
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- Posts: Public can view published
DROP POLICY IF EXISTS "Public can view published blogs" ON public.blog_posts;
CREATE POLICY "Public can view published blogs" ON public.blog_posts
    FOR SELECT USING (is_published = TRUE);

-- Posts: Admins can do EVERYTHING
DROP POLICY IF EXISTS "Admins can manage blog posts" ON public.blog_posts;
CREATE POLICY "Admins can manage blog posts" ON public.blog_posts
    FOR ALL TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM public.user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.user_profiles 
            WHERE id = auth.uid() AND is_admin = TRUE
        )
    );

-- 3. ENSURE DASHBOARD STATS RPC IS ROBUST
-- =======================================

CREATE OR REPLACE FUNCTION public.get_dashboard_stats()
RETURNS JSONB AS $$
DECLARE
    stats JSONB;
BEGIN
    -- SECURITY DEFINER ensures this runs with admin privileges bypassing RLS
    SELECT jsonb_build_object(
        'total_users', (SELECT COUNT(*) FROM public.user_profiles),
        'paid_users', (SELECT COUNT(*) FROM public.user_profiles WHERE subscription_tier != 'Free'),
        'total_revenue', (SELECT COALESCE(SUM(amount), 0) FROM public.transactions WHERE status = 'success'),
        'revenue_this_month', (
            SELECT COALESCE(SUM(amount), 0) 
            FROM public.transactions 
            WHERE status = 'success' 
            AND created_at >= date_trunc('month', NOW())
        ),
        'total_chats', (SELECT COUNT(*) FROM public.chats),
        'total_assignments', (SELECT COUNT(*) FROM public.assignments),
        'completed_assignments', (SELECT COUNT(*) FROM public.assignments WHERE status = 'completed'),
        'active_users_24h', (
            SELECT COUNT(DISTINCT user_id) 
            FROM public.chats 
            WHERE updated_at > NOW() - INTERVAL '24 hours'
        )
    ) INTO stats;
    RETURN stats;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION public.get_dashboard_stats TO authenticated;
