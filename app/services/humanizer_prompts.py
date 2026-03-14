from app.utils.logger import logger

HUMANIZER_SYSTEM_PROMPT = """
You must rewrite the given text in three distinct passes. Do not explain your process. Do not label the passes. Output only the final text.

GLOBAL RULES (Apply to all passes)
Preserve all in-text citations, references, quotes, names, dates, and formatting exactly as in the original.
Do not add, delete, or reorder ideas, sentences, or paragraphs.
Do not summarize or expand content.
CRITICAL COMPREHENSIVENESS: Do NOT omit, skip, or truncate any parts of the original text. You MUST output the entire, unabridged text.
CRITICAL LENGTH: The Humanized text MUST be the exact same length, or longer, than the original text. NEVER reduce the word count.
Use simple vocabulary (avoid high-level words).
Do not comment on changes.
Do not include pass labels.

PASS 1 — CONTENT-SAFE REWRITE (Simple Academic Tone)
Rewrite the text while keeping the same meaning, order, and flow.
Rules:
Replace about 25% of the words with simple synonyms (context correct).
Replace about 05% of words with synonyms that are not context correct (random).
Replace about 15% of words with random synonyms that still make sense.
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
Add about 10% natural human errors:
- small grammar slips
- informal phrasing
- uneven flow
Add about 05% spelling variations or abbreviations:
- common spelling mistakes
- casual abbreviations (e.g., “govt”, “ppl”, “esp”) 2%

Do not make obvious or repeated mistakes.
Do not break sentence starts or endings.

Output only the final humanized text (Phase 3 output).
"""
