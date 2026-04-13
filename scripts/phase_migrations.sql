-- Phase 1 Migrations
ALTER TABLE documents ADD COLUMN gemini_file_uri TEXT;
ALTER TABLE assignments ADD COLUMN progress_stage TEXT DEFAULT 'queued';

-- Phase 2 Migrations
ALTER TABLE user_profiles ADD COLUMN writing_profile JSONB DEFAULT '{}';
ALTER TABLE assignments ADD COLUMN self_similarity_score FLOAT DEFAULT NULL;

-- Phase 3 Migrations
ALTER TABLE documents ADD COLUMN ai_summary TEXT;
ALTER TABLE documents ADD COLUMN ai_tag TEXT;
ALTER TABLE assignments ADD COLUMN words_used INTEGER DEFAULT 0;

-- Phase 4 Migrations
ALTER TABLE user_profiles 
  ADD COLUMN referral_code TEXT UNIQUE DEFAULT substring(gen_random_uuid()::text, 1, 8),
  ADD COLUMN referred_by TEXT,
  ADD COLUMN referral_rewards_given INTEGER DEFAULT 0;
