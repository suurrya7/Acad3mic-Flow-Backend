-- Acad3mic-Flow Database Functions
-- Run this in Supabase SQL Editor after running schema.sql

-- Function to atomically deduct words from user balance
-- This prevents race conditions when multiple requests happen simultaneously
CREATE OR REPLACE FUNCTION deduct_user_words(user_uuid UUID, words_to_deduct INT)
RETURNS INT AS $$
DECLARE
  new_balance INT;
BEGIN
  -- Atomically update and return new balance
  UPDATE public.user_profiles
  SET word_balance = GREATEST(0, word_balance - words_to_deduct)
  WHERE id = user_uuid
  RETURNING word_balance INTO new_balance;
  
  IF NOT FOUND THEN
    RAISE EXCEPTION 'User not found: %', user_uuid;
  END IF;
  
  RETURN new_balance;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user has sufficient balance
CREATE OR REPLACE FUNCTION check_user_balance(user_uuid UUID, required_words INT)
RETURNS BOOLEAN AS $$
DECLARE
  current_balance INT;
BEGIN
  SELECT word_balance INTO current_balance
  FROM public.user_profiles
  WHERE id = user_uuid;
  
  IF NOT FOUND THEN
    RETURN FALSE;
  END IF;
  
  RETURN current_balance >= required_words;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION deduct_user_words(UUID, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION check_user_balance(UUID, INT) TO authenticated;
