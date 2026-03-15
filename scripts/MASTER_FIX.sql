-- ACAD3MIC FLOW - MASTER DATABASE FIX (PRODUCTION RECOVERY)
-- v4: Fixes target_id type mismatch (UUID vs TEXT) and improves robustness.

-- 1. Create missing Humanizer Prompts table
CREATE TABLE IF NOT EXISTS public.humanizer_prompts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id),
    notes TEXT
);

-- 2. Robust Drop/Recreate for admin_logs to handle type changes
DO $$ 
BEGIN
    -- If the table exists but has target_id as UUID, we drop it to reset to TEXT
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'admin_logs' 
        AND column_name = 'target_id' 
        AND data_type = 'uuid'
    ) THEN
        DROP TABLE public.admin_logs CASCADE;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.admin_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID REFERENCES auth.users(id),
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT, -- Reset to TEXT for maximum flexibility
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Create/Update Admin Action Logging RPC
DO $$ 
BEGIN
    EXECUTE (
        SELECT 'DROP FUNCTION ' || string_agg(oid::regprocedure::text, '; DROP FUNCTION ')
        FROM pg_proc
        WHERE proname = 'log_admin_action'
        AND pronamespace = 'public'::regnamespace
    );
EXCEPTION WHEN OTHERS THEN 
END $$;

CREATE OR REPLACE FUNCTION public.log_admin_action(
    admin_uuid UUID,
    action_name TEXT,
    target_type_val TEXT,
    target_id_val TEXT,
    details_val JSONB DEFAULT '{}'::jsonb
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO public.admin_logs (admin_id, action, target_type, target_id, details)
    VALUES (admin_uuid, action_name, target_type_val, target_id_val, details_val);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 4. Create/Update Dashboard Statistics RPC
DROP FUNCTION IF EXISTS public.get_dashboard_stats();
CREATE OR REPLACE FUNCTION public.get_dashboard_stats()
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

-- 5. Create atomic balance adjustment RPCs
DROP FUNCTION IF EXISTS public.deduct_user_words(UUID, INTEGER);
DROP FUNCTION IF EXISTS public.add_user_words(UUID, INTEGER);
DROP FUNCTION IF EXISTS public.deduct_grading_check(UUID);

CREATE OR REPLACE FUNCTION public.deduct_user_words(user_id_uuid UUID, amount INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE public.user_profiles
    SET word_balance = word_balance - amount
    WHERE id = user_id_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.add_user_words(user_id_uuid UUID, amount INTEGER)
RETURNS VOID AS $$
BEGIN
    UPDATE public.user_profiles
    SET word_balance = word_balance + amount
    WHERE id = user_id_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION public.deduct_grading_check(user_id_uuid UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE public.user_profiles
    SET grading_balance = grading_balance - 1
    WHERE id = user_id_uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 6. Grant permissions
GRANT EXECUTE ON FUNCTION get_dashboard_stats TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION log_admin_action TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION deduct_user_words TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION add_user_words TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION deduct_grading_check TO authenticated, service_role;

-- 7. Ensure Blog tables exist
CREATE TABLE IF NOT EXISTS public.blog_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    status TEXT CHECK (status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
    source TEXT CHECK (source IN ('ai_generated', 'admin_suggested')) DEFAULT 'ai_generated',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.blog_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id UUID REFERENCES public.blog_topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    meta_description TEXT,
    is_published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE public.blog_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_posts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public can view published blogs" ON public.blog_posts;
CREATE POLICY "Public can view published blogs" ON public.blog_posts
    FOR SELECT USING (is_published = TRUE);
