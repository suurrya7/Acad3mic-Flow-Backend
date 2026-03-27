-- Acad3mic-Flow Database Schema (Final V1)

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. User Profiles (Extends Supabase Auth)
CREATE TABLE public.user_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    word_balance INTEGER DEFAULT 2000,
    grading_balance INTEGER DEFAULT 3, -- Default for Free tier
    subscription_tier TEXT CHECK (subscription_tier IN ('Free', 'Basic', 'Standard', 'Premium', 'Ultimate')) DEFAULT 'Free',
    is_admin BOOLEAN DEFAULT FALSE,
    is_banned BOOLEAN DEFAULT FALSE,
    last_reset_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Function to handle new user creation
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.user_profiles (id, email, word_balance, grading_balance, subscription_tier, last_reset_date)
    VALUES (new.id, new.email, 2000, 2, 'Free', CURRENT_DATE);
    RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user creation
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ATOMIC RPCS FOR BALANCE MANAGEMENT
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

-- 2. Chats (with Memory)
CREATE TABLE public.chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE NOT NULL,
    title TEXT DEFAULT 'New Chat',
    summary TEXT DEFAULT '', -- Rolling summary for long-term memory
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Messages
CREATE TABLE public.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id UUID REFERENCES public.chats(id) ON DELETE CASCADE NOT NULL,
    role TEXT CHECK (role IN ('user', 'assistant')) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Assignments
CREATE TABLE public.assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE NOT NULL,
    status TEXT CHECK (status IN ('pending', 'processing', 'completed', 'failed')) DEFAULT 'pending',
    title TEXT,
    input_text TEXT, -- Optional raw input
    output_text TEXT, -- Final generated content
    document_ids UUID[], -- Array of linked document IDs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Documents
CREATE TABLE public.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE NOT NULL,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL, -- Path in Supabase Storage
    content_extracted TEXT, -- Text extracted from PDF/DOCX
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. Transactions (PayU)
CREATE TABLE public.transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.user_profiles(id) ON DELETE CASCADE NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    words_purchased INTEGER NOT NULL,
    status TEXT CHECK (status IN ('pending', 'success', 'failed')) DEFAULT 'pending',
    provider_ref TEXT, -- PayU Transaction ID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Row Level Security (RLS) Policies

ALTER TABLE public.user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

-- Policies for User Profiles
CREATE POLICY "Users can view own profile" ON public.user_profiles
    FOR SELECT USING (auth.uid() = id);
-- CRITICAL: No UPDATE/INSERT/DELETE policy for users on user_profiles.
-- This ensures 'word_balance', 'subscription_tier', etc. are immutable by the frontend.
-- Backend (Service Role) bypasses RLS to manage these fields.

-- Policies for Chats
CREATE POLICY "Users can manage their own chats" ON public.chats
    FOR ALL USING (auth.uid() = user_id);

-- Policies for Messages
CREATE POLICY "Users can manage messages in their chats" ON public.messages
    FOR ALL USING (
        EXISTS (
            SELECT 1 FROM public.chats
            WHERE public.chats.id = public.messages.chat_id
            AND public.chats.user_id = auth.uid()
        )
    );

-- Policies for Assignments
CREATE POLICY "Users can manage their own assignments" ON public.assignments
    FOR ALL USING (auth.uid() = user_id);

-- Policies for Documents
CREATE POLICY "Users can manage their own documents" ON public.documents
    FOR ALL USING (auth.uid() = user_id);

-- Policies for Transactions
CREATE POLICY "Users can view their own transactions" ON public.transactions
    FOR SELECT USING (auth.uid() = user_id);

-- 7. Storage Policies (assignments bucket)
-- Enable RLS on storage.objects if not already
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- Policy: Upload (Insert)
CREATE POLICY "Users can upload own assignments" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'assignments' AND
        (storage.foldername(name))[1] = auth.uid()::text
    );

-- Policy: Read (Select)
CREATE POLICY "Users can view own assignments" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'assignments' AND
        (storage.foldername(name))[1] = auth.uid()::text
    );

-- Policy: Delete
CREATE POLICY "Users can delete own assignments" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'assignments' AND
        (storage.foldername(name))[1] = auth.uid()::text
    );

-- 8. Performance Indexes
CREATE INDEX IF NOT EXISTS idx_chats_user_id ON public.chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_updated_at ON public.chats(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON public.messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at);
CREATE INDEX IF NOT EXISTS idx_assignments_user_id ON public.assignments(user_id);
CREATE INDEX IF NOT EXISTS idx_assignments_created_at ON public.assignments(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON public.documents(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON public.transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_provider_ref ON public.transactions(provider_ref);

-- Additional Composite Indexes for Common Queries
-- For chat message fetching with user verification
CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON public.messages(chat_id, created_at);

-- For user profile lookups with reset date checks
CREATE INDEX IF NOT EXISTS idx_user_profiles_tier_reset ON public.user_profiles(subscription_tier, last_reset_date) 
  WHERE subscription_tier != 'Free';

-- For recent assignments by user
CREATE INDEX IF NOT EXISTS idx_assignments_user_created ON public.assignments(user_id, created_at DESC, status);

-- For transaction history queries
CREATE INDEX IF NOT EXISTS idx_transactions_user_status ON public.transactions(user_id, status, created_at DESC);

-- 9. Blog Automation System
CREATE TABLE public.blog_topics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    status TEXT CHECK (status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
    source TEXT CHECK (source IN ('ai_generated', 'admin_suggested')) DEFAULT 'ai_generated',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE public.blog_posts (
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

-- Blog RLS
ALTER TABLE public.blog_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.blog_posts ENABLE ROW LEVEL SECURITY;

-- Public can read published blog posts
CREATE POLICY "Public can view published blogs" ON public.blog_posts
    FOR SELECT USING (is_published = TRUE);

-- 10. Admin Logging System
CREATE TABLE public.admin_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID REFERENCES auth.users(id),
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Note: Admin logs usually shouldn't be readable by regular users
ALTER TABLE public.admin_logs ENABLE ROW LEVEL SECURITY;

-- RPC for Admin Actions (used by AdminService)
CREATE OR REPLACE FUNCTION public.log_admin_action(
    admin_uuid UUID,
    action_name TEXT,
    target_type_val TEXT,
    target_id_val TEXT,
    details_val JSONB
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO public.admin_logs (admin_id, action, target_type, target_id, details)
    VALUES (admin_uuid, action_name, target_type_val, target_id_val, details_val);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
