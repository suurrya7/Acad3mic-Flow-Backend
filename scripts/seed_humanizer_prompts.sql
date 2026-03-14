
-- ==========================================
-- SEED INITIAL HUMANIZER PROMPT
-- ==========================================

-- Insert the default prompt from code into the database
-- We use a subquery to find an admin user to attribute this to.
-- If no admin is found, it will result in NULL which is allowed or we default to the first user.

INSERT INTO humanizer_prompts (
    version,
    prompt_text,
    is_active,
    created_by,
    notes,
    test_results
) 
VALUES (
    1,
    $$You must rewrite the given text in three distinct passes. Do not explain your process. Do not label the passes. Output only the final text.

GLOBAL RULES (Apply to all passes)
Preserve all in-text citations, references, quotes, names, dates, and formatting exactly as in the original.
Do not add, delete, or reorder ideas, sentences, or paragraphs.
Do not summarize or expand content.
Use simple vocabulary (avoid high-level words).
Do not comment on changes.
Do not include pass labels.

PASS 1 — CONTENT-SAFE REWRITE (Simple Academic Tone)
Rewrite the text while keeping the same meaning, order, and flow.
Rules:
Replace about 50% of the words with simple synonyms (context correct).
Replace about 5% of words with synonyms that are not context correct (random).
Replace about 10% of words with random synonyms that still make sense.
Maintain clear readability.
Do not change citations, quotes, references, or formatting.
Output the full rewritten text.

PASS 2 — STRUCTURAL VARIATION (Random Paragraph + Sentence Lengths)
Using Pass 1 output, change structure but keep meaning.
Rules:
Randomly vary paragraph lengths.
Some short, some long.
No predictable pattern.
Randomly vary sentence lengths.
Mix short, medium, and long sentences.
Include some choppy sentences.
Every paragraph must start and end with a full sentence.
Vary sentence rhythm and structure without changing meaning.
Keep citations and references unchanged.
Output the revised text.

PASS 3 — HUMAN IMPERFECTION LAYER (Simple Academic Tone)
Using Pass 2 output, add human imperfections.
Rules:
Reduce grammar quality below 80% while staying readable.
Add about 20% natural human errors:
- small grammar slips
- informal phrasing
- uneven flow
Add about 20% spelling variations or abbreviations:
- common spelling mistakes
- casual abbreviations (e.g., “govt”, “ppl”, “esp”)

Do not make obvious or repeated mistakes.
Do not break sentence starts or endings.

Output only the final humanized text.$$::text,
    TRUE,
    (SELECT id FROM user_profiles WHERE is_admin = TRUE LIMIT 1),
    'Initial default prompt seeded from system settings',
    '{"status": "untested"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Verify insertion
SELECT id, version, is_active FROM humanizer_prompts WHERE is_active = TRUE;
