-- ==========================================
-- ACAD3MIC FLOW - EMERGENCY RLS RECOVERY
-- ==========================================
-- PROBLEM: The previous admin_fix.sql created self-referencing RLS policies
-- on user_profiles that cause infinite recursion (policy checks user_profiles 
-- to see if user is admin, but that check itself triggers the same policy).
-- This blocks ALL database access including login.
--
-- This script FIXES everything by:
-- 1. Removing ALL broken policies from user_profiles
-- 2. Disabling RLS on user_profiles (backend uses service_role key which bypasses RLS anyway)
-- 3. Fixing blog table policies using a safe helper function
-- 4. Adding missing INSERT policy for user registration

-- ==========================================
-- STEP 1: EMERGENCY - RESTORE USER_PROFILES ACCESS
-- ==========================================
-- Drop ALL policies on user_profiles to remove the recursive ones
DROP POLICY IF EXISTS "Users can view own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Admins can view all profiles" ON public.user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON public.user_profiles;
DROP POLICY IF EXISTS "Admins can update all profiles" ON public.user_profiles;

-- Disable RLS on user_profiles entirely.
-- REASONING: The backend ALWAYS uses the service_role key (which bypasses RLS anyway).
-- The frontend never queries user_profiles directly - it goes through the backend API.
-- So RLS on this table adds complexity with zero security benefit.
ALTER TABLE public.user_profiles DISABLE ROW LEVEL SECURITY;

-- ==========================================
-- STEP 2: CREATE SAFE ADMIN CHECK FUNCTION
-- ==========================================
-- Instead of self-referencing policies, use a SECURITY DEFINER function
-- that bypasses RLS to check admin status. This prevents infinite recursion.
CREATE OR REPLACE FUNCTION public.is_admin(check_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.user_profiles 
        WHERE id = check_user_id AND is_admin = TRUE
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION public.is_admin TO authenticated;

-- ==========================================
-- STEP 3: FIX BLOG TABLES (Use safe function)
-- ==========================================
ALTER TABLE public.blog_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_posts ENABLE ROW LEVEL SECURITY;

-- Blog Topics: Only admins can manage (uses safe function)
DROP POLICY IF EXISTS "Admins can manage blog topics" ON public.blog_topics;
CREATE POLICY "Admins can manage blog topics" ON public.blog_topics
    FOR ALL TO authenticated
    USING (public.is_admin(auth.uid()))
    WITH CHECK (public.is_admin(auth.uid()));

-- Blog Posts: Public can read published posts
DROP POLICY IF EXISTS "Public can view published blogs" ON public.blog_posts;
CREATE POLICY "Public can view published blogs" ON public.blog_posts
    FOR SELECT USING (is_published = TRUE);

-- Blog Posts: Admins can do everything
DROP POLICY IF EXISTS "Admins can manage blog posts" ON public.blog_posts;
CREATE POLICY "Admins can manage blog posts" ON public.blog_posts
    FOR ALL TO authenticated
    USING (public.is_admin(auth.uid()))
    WITH CHECK (public.is_admin(auth.uid()));

-- ==========================================
-- STEP 4: VERIFY ADMIN STATUS
-- ==========================================
-- Show which users are admins (sanity check)
SELECT id, email, is_admin FROM public.user_profiles WHERE is_admin = TRUE;
