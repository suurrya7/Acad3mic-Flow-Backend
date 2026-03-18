import asyncio
import os
import google.generativeai as genai
from app.config import get_settings
from app.utils.logger import logger
from app.services.humanizer_prompts import HUMANIZER_SYSTEM_PROMPT

settings = get_settings()

# Configure the internal model
# CRITICAL: This is the ONLY place where the model name is defined.
# Configure the internal model from env or use default
INTERNAL_MODEL_NAME = settings.GEMINI_MODEL_NAME

try:
    # Use default transport (gRPC) which is more robust for streaming
    # unless REST is explicitly needed.
    genai.configure(api_key=settings.GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Failed to configure AI provider: {str(e)}")

class AIService:
    def __init__(self):
        # Always get fresh settings to ensure we pick up environment overrides
        current_settings = get_settings()
        self.model = genai.GenerativeModel(current_settings.GEMINI_MODEL_NAME)

    def extract_json_from_text(self, text: str) -> str:
        """
        Extracts raw JSON string from AI-generated text.
        Handles markdown blocks (```json ... ```) and leading/trailing whitespace.
        """
        if not text:
            return ""
            
        json_str = text.strip()
        
        # Check for markdown code blocks
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            # Fallback for generic code blocks
            json_str = json_str.split("```")[1].split("```")[0].strip()
            
        # If it's still containing markdown headers or garbage after a JSON structure, 
        # try to find the actual start and end of the JSON object/array
        start_idx = json_str.find('{')
        if start_idx == -1:
            start_idx = json_str.find('[')
            
        end_idx = json_str.rfind('}')
        if end_idx == -1:
            end_idx = json_str.rfind(']')
            
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = json_str[start_idx:end_idx+1]
            
        return json_str

    async def generate_content(self, prompt: str, system_instruction: str = None, timeout: int = 120) -> str:
        """
        Generates content using the internal AI model with timeout protection.
        Returns ONLY the text content.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system-level instructions
            timeout: Maximum time to wait for response (default 120s)
        """
        import asyncio
        
        try:
            # Construct the full prompt if system instruction is provided
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"System Instruction:\n{system_instruction}\n\nUser Request:\n{prompt}"

            # Log prompt size for debugging
            logger.info(f"Sending AI Request: prompt_len={len(full_prompt)} chars, timeout={timeout}s")

            # Wrap synchronous call with asyncio timeout and add retries
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # Pass the timeout to allow full length responses
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.model.generate_content, 
                            full_prompt,
                            request_options={"timeout": timeout}
                        ),
                        timeout=timeout + 5  # Give SDK a bit more room than our local timeout
                    )
                    
                    if not response.candidates or not response.candidates[0].content.parts:
                        logger.error(f"AI returned no content. Finish reason: {response.candidates[0].finish_reason if response.candidates else 'Unknown'}")
                        raise ValueError("AI provided no content (possibly due to safety filters)")
                        
                    return response.text

                except (asyncio.TimeoutError, Exception) as e:
                    last_error = e
                    error_str = str(e)
                    
                    # If it's a rate limit (429) or overloaded (503/500), retry with backoff
                    if ("429" in error_str or "503" in error_str or "quota" in error_str.lower()) and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 2s, 4s
                        logger.warning(f"AI rate limit/error hit. Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # For other errors or final attempt failure
                    if isinstance(e, asyncio.TimeoutError):
                        logger.error(f"AI generation timed out after {timeout}s")
                        raise Exception("Request took too long. Please try a shorter prompt or try again.")
                    
                    logger.error(f"AI Generation failed: {error_str}")
                    if attempt == max_retries - 1:
                        logger.error(f"AI Quota Exceeded: {error_str}")
                        raise Exception("AI quota exceeded for today. Please try again later or upgrade your plan.")
                        case_msg = "capacity limits" if "503" in error_str else "an unknown error"
                        raise Exception(f"AI processing failed due to {case_msg}. Please try again.")
                    raise e
            
        except Exception as e:
            # Final fallback to ensure consistent error message
            error_msg = str(e)
            error_msg_lower = error_msg.lower()
            
            # Pass through specific known errors
            if any(key in error_msg_lower for key in ["capacity", "too long", "quota", "safety", "blocked"]):
                raise e
            
            # For other errors, include the context so we can debug on Render
            logger.error(f"AI Service Internal Error: {error_msg}")
            raise Exception(f"AI processing failed: {error_msg}")


    async def humanize_text(self, text: str) -> str:
        """
        Applies the mandatory 3-pass humanization layer.
        Now uses a chunking strategy for large documents (up to 30k+ words) 
        to avoid AI output token limits and truncation.
        """
        try:
            # Import here to avoid circular dependency
            from app.services.prompt_manager import prompt_manager
            
            # 1. Get active prompt from database
            active_prompt = await prompt_manager.get_active_prompt()
            system_instruction = active_prompt.get("prompt_text", HUMANIZER_SYSTEM_PROMPT)
            
            # 2. Check if we need chunking (Threshold: ~2000 words or ~10,000 chars)
            words = text.split()
            if len(words) <= 2200:
                # Small enough for a single pass
                prompt = f"Original Text to Humanize:\n\n{text}"
                return await self.generate_content(prompt, system_instruction=system_instruction)

            # 3. Large Document Path: Chunking
            logger.info(f"Large document detected ({len(words)} words). Starting chunked humanization.")
            
            # Split by paragraphs to avoid cutting mid-sentence
            paragraphs = text.split('\n')
            chunks = []
            current_chunk = []
            current_word_count = 0
            
            for p in paragraphs:
                p_words = p.split()
                if current_word_count + len(p_words) > 1800 and current_chunk:
                    # Seal current chunk
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [p]
                    current_word_count = len(p_words)
                else:
                    current_chunk.append(p)
                    current_word_count += len(p_words)
            
            if current_chunk:
                chunks.append('\n'.join(current_chunk))

            logger.info(f"Split document into {len(chunks)} chunks for humanization.")
            
            # 4. Process Chunks (Iteratively to avoid rate limits and for memory safety)
            humanized_chunks = []
            for i, chunk_text in enumerate(chunks):
                logger.info(f"Humanizing chunk {i+1}/{len(chunks)} ({len(chunk_text.split())} words)...")
                prompt = f"Original Text to Humanize (Part {i+1} of {len(chunks)}):\n\n{chunk_text}"
                
                # Use a slightly longer timeout for humanization if needed
                h_chunk = await self.generate_content(prompt, system_instruction=system_instruction, timeout=180)
                humanized_chunks.append(h_chunk.strip())
                
                # Small sleep to be kind to the API
                await asyncio.sleep(1)

            # 5. Stitching back together
            return "\n\n".join(humanized_chunks)

        except Exception as e:
            # Final fallback to ensure consistent error message or default behavior
            logger.error(f"Failed to humanize text: {str(e)}")
            # If everything fails, we MUST return the original text at minimum so the user doesn't lose data
            return text


    async def generate_chat_title(self, user_message: str) -> str:
        """
        Generates a short, relevant title for the chat based on the first message.
        """
        system_prompt = """
        You are a helpful assistant that generates chat titles.
        Generate a concise (3-5 words) title for a chat based on the user's first message.
        - Do NOT use quotes.
        - Do NOT include "Title:".
        - Just the raw title text.
        """
        
        try:
            # Pass truncated message to generate title
            prompt = f"User Message: {user_message[:500]}\n\nGenerate Title:"
            title = await self.generate_content(prompt, system_instruction=system_prompt)
            return title.strip().replace('"', '')
        except Exception as e:
            logger.error(f"Title generation failed: {str(e)}")
            return "New Chat"

    async def analyze_assignment_intent(self, topic: str, instructions: str, files_content: str) -> str:
        """
        Analyzes the assignment to determine type, level, and intent.
        """
        system_prompt = """
        You are an expert academic strategist. 
        Analyze the incoming request to determine:
        1. Assignment Type (e.g., Argumentative Essay, Lab Report, Literature Review, etc.)
        2. Academic Level (Detect based on complexity: High School, Undergraduate, Master's, PhD)
        3. Grading Intent (What are the key grading criteria implied?)
        4. Structural Requirements
        
        Output a concise summary of these 4 points to guide the writer.
        Do NOT generate the assignment yet. Just the strategy.
        """
        
        user_prompt = f"Topic: {topic}\nInstructions: {instructions}\nReference Content: {files_content[:1000]}"
        
        # Intent analysis can be slow with documents
        strategy = await self.generate_content(user_prompt, system_instruction=system_prompt, timeout=300)
        return strategy

    async def generate_assignment(self, topic: str, instructions: str, files_content: str = "", researched_data: str = "", assignment_id: str = None) -> str:
        """
        Generates the initial academic content before humanization.
        Uses a chunk-based strategy to enforce accurate word counts and instruction adherence.
        """
        import json
        import math
        
        # ---------------------------------------------------------
        # PHASE 1: Generate Strategic Outline & Chunk Word Counts
        # ---------------------------------------------------------
        outline_prompt = f"""
        You are the Head Academic Strategist. Analyze the incoming request and create a detailed structural outline for an assignment.
        
        USER TOPIC: {topic}
        INSTRUCTIONS: {instructions}
        
        YOUR JOB:
        1. Identify the requested Total Word Count from the instructions (assume 2000 words if not explicitly stated).
        2. Break the assignment down into logical, comprehensive sections (e.g., Introduction, Literature Review, Methodology, Discussion, Conclusion).
        3. Assign a strict target word count to each section so that they mathematically sum to the Total Word Count.
        
        OUTPUT FORMAT (STRICT JSON):
        {{
            "total_target_words": 2000,
            "sections": [
                {{
                    "heading": "Introduction",
                    "focus": "Introduce the context, define key terms, and state the thesis.",
                    "target_words": 200
                }},
                {{
                    "heading": "Literature Review",
                    "focus": "Analyze current research...",
                    "target_words": 800
                }}
            ]
        }}
        """
        
        try:
            outline_res = await self.generate_content(
                outline_prompt, 
                system_instruction="You are a JSON-only structural outline generator. Output only valid JSON without markdown blocks.",
                timeout=60
            )
            
            # Clean JSON
            json_str = outline_res.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            
            outline_data = json.loads(json_str)
            sections = outline_data.get("sections", [])
            
        except Exception as e:
            logger.error(f"Outline generation failed: {str(e)}")
            # Fallback Outline
            sections = [
                {"heading": "Introduction", "focus": "Introduce the topic and outline the essay.", "target_words": 300},
                {"heading": "Main Body", "focus": "Discuss the core concepts, provide evidence, and analyze the topic deeply.", "target_words": 1400},
                {"heading": "Conclusion", "focus": "Summarize key findings and conclude.", "target_words": 300}
            ]
            
        # ---------------------------------------------------------
        # PHASE 2: Iterative Chunk Generation
        # ---------------------------------------------------------
        full_academic_text = ""
        
        for index, section in enumerate(sections):
            heading = section.get("heading", f"Section {index+1}")
            focus = section.get("focus", "Discuss the required topic.")
            target_words = section.get("target_words", 500)
            
            chunk_system_prompt = f"""
            You are Acad3mic-Flow AI, an advanced academic assistant.
            Your task is to generate ONE specific section of a larger academic assignment.
            
            RULES:
            - Use formal academic tone.
            - Include citations where appropriate.
            - Structure with clear sub-headings and paragraphs.
            - NO Emojis.
            - CRITICAL INSTRUCTIONS ADHERENCE: You MUST strictly adhere to ALL instructions provided in the Reference Material.
            
            EXTREME LENGTH & STRUCTURE DIRECTIVE:
            - You are writing the "{heading}" section.
            - You MUST write EXACTLY {target_words} words for this section. Do NOT fall short.
            - To achieve this exact length naturally, use deeply nested structures, exhaustive multi-paragraph arguments, robust examples, counter-arguments, and deep theoretical analyses.
            - NEVER output abbreviated, truncated, or summarized content. Provide the full, unabridged text required.
            """
            
            chunk_user_prompt = f"""
            OVERALL ASSIGNMENT TOPIC: {topic}
            OVERALL INSTRUCTIONS: {instructions}
            
            YOUR CURRENT TASK: Write the "{heading}" section ONLY.
            SECTION FOCUS: {focus}
            MANDATORY WORD COUNT FOR THIS SECTION: {target_words} words.
            """
            
            if files_content:
                chunk_user_prompt += f"\n\nReference Material (Full Content):\n{files_content}"
            
            if researched_data:
                chunk_user_prompt += f"\n\nExtracted Online Research Data:\n{researched_data}"
                
            # Generate the specific section (with checkpoint support)
            try:
                # --- If assignment_id provided, check if chunk already exists (resumption) ---
                if assignment_id:
                    from app.db.supabase import get_supabase_admin
                    supabase = get_supabase_admin()
                    existing = supabase.table("assignment_chunks") \
                        .select("content") \
                        .eq("assignment_id", assignment_id) \
                        .eq("chunk_index", index) \
                        .execute()
                    if existing.data:
                        logger.info(f"Resuming: chunk {index} ('{heading}') already exists.")
                        full_academic_text += f"\n\n# {heading}\n\n{existing.data[0]['content']}"
                        continue  # Skip AI call for this section

                section_text = await self.generate_content(
                    chunk_user_prompt, 
                    system_instruction=chunk_system_prompt, 
                    timeout=120
                )
                
                # --- Checkpoint: save section to DB immediately ---
                if assignment_id:
                    try:
                        supabase.table("assignment_chunks").upsert({
                            "assignment_id": assignment_id,
                            "chunk_index": index,
                            "heading": heading,
                            "content": section_text.strip(),
                            "target_words": target_words,
                            "is_humanized": False
                        }, on_conflict="assignment_id,chunk_index").execute()
                        logger.info(f"Checkpointed chunk {index} ('{heading}') for assignment {assignment_id}")
                    except Exception as db_err:
                        logger.warning(f"Failed to checkpoint chunk {index}: {str(db_err)}")

                # Append to full document
                full_academic_text += f"\n\n# {heading}\n\n{section_text.strip()}"
                
            except Exception as e:
                logger.error(f"Failed to generate section {heading}: {str(e)}")
                full_academic_text += f"\n\n# {heading}\n\n[Generation failed for this section due to technical error.]"

            # Rate limit protection between chunks
            await asyncio.sleep(2)
            
        # ---------------------------------------------------------
        # PHASE 3: Humanize the Stitched Document
        # ---------------------------------------------------------
        # Note: Depending on total length, humanizing a massive string might hit token limits.
        # But for now we pass the stitched result to the humanizer as one block.
        final_text = await self.humanize_text(full_academic_text)
        
        return final_text

    async def chat_with_memory(self, current_summary: str, history: list, new_message: str) -> dict:
        """
        Handles chat interactions with memory.
        Returns a dict: {"assistant_reply": str, "updated_summary": str}
        """
        import json
        
        # 1. Format History for Prompt
        # history is list of dicts {role, content}
        formatted_history = ""
        for msg in history[-10:]: # Keep last 10 messages for context
            role = "User" if msg['role'] == "user" else "Assistant"
            formatted_history += f"{role}: {msg['content']}\n"
            
        # 2. Construct System Prompt
        system_prompt = f"""
        You are Acad3mic-Flow AI.
        
        CONTEXT:
        1. Existing Chat Summary: "{current_summary}"
        2. Recent Chat History:
        {formatted_history}
        
        USER REQUEST: "{new_message}"
        
        YOUR JOB:
        1. Use the summary as long-term memory and history as short-term context.
        2. Respond naturally to the user.
        3. Update the summary to include important new information (facts, goals, preferences).
        
        RULES FOR MEMORY:
        - Preserve important facts/decisions.
        - Do NOT repeat messages verbatim.
        - Concise (max 200 words).
        - Update if contradictory, otherwise keep.
        
        OUTPUT FORMAT (STRICT JSON):
        {{
            "assistant_reply": "your response here",
            "updated_summary": "revised summary here"
        }}
        """
        
        try:
            # Wrap synchronous call with asyncio.to_thread
            response = await asyncio.to_thread(
                self.model.generate_content,
                system_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            if not response.candidates or not response.candidates[0].content.parts:
                raise ValueError("Missing content in AI JSON response")
                
            # Parse JSON
            try:
                result = json.loads(response.text)
                if "assistant_reply" not in result or "updated_summary" not in result:
                    # Fallback if structure is wrong but valid json
                    raise ValueError("Missing keys")
                return result
            except json.JSONDecodeError:
                # Fallback if model didn't return JSON (should be rare with mime_type)
                # Try to regex extract if needed, or fail safe
                logger.error("Failed to parse JSON from AI memory response")
                return {
                    "assistant_reply": "I processed your request but had trouble with my internal memory. " + response.text[:100],
                    "updated_summary": current_summary
                }
                
        except Exception as e:
            logger.error(f"Chat memory processing failed: {str(e)}")
            raise Exception("AI processing failed.")

    async def detect_assignment_intent(self, message: str) -> dict:
        """
        Detects if user message is requesting assignment help.
        Returns: {is_assignment: bool, confidence: float, assignment_type: str}
        """
        import json
        
        system_prompt = """
        You are an intent classifier for Acad3mic-Flow.
        Analyze the user message and determine if they are requesting academic assignment help.
        
        ASSIGNMENT indicators:
        - Mentions essays, reports, papers, research, thesis
        - Asks to "write", "complete", "help with", "generate" assignments
        - Provides academic requirements, rubrics, word counts
        - Mentions citations, formatting, academic structure
        - Contains phrases like "due date", "professor wants", "assignment requirements"
        
        NOT assignments:
        - General questions about topics (e.g., "What is photosynthesis?")
        - Casual conversation
        - Clarification requests
        - Simple explanations
        
        OUTPUT FORMAT (STRICT JSON):
        {
            "is_assignment": true/false,
            "confidence": 0.0-1.0,
            "assignment_type": "essay|report|research|thesis|none"
        }
        """
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                f"User message: {message}\n\nAnalyze and classify:",
                generation_config={"response_mime_type": "application/json"}
            )
            
            if not response.candidates or not response.candidates[0].content.parts:
                # Default to not assignment
                return {"is_assignment": False, "confidence": 0.0, "assignment_type": "none"}
            
            result = json.loads(response.text)
            
            # Ensure keys exist with defaults
            if not isinstance(result, dict):
                result = {}
            
            return {
                "is_assignment": result.get("is_assignment", False),
                "confidence": result.get("confidence", 0.0),
                "assignment_type": result.get("assignment_type", "none")
            }
        except Exception as e:
            logger.error(f"Intent detection failed: {str(e)}")
            # Safe default - treat as regular chat
            return {"is_assignment": False, "confidence": 0.0, "assignment_type": "none"}

    async def chat_with_memory_stream(self, current_summary: str, history: list, new_message: str, files_content: str = ""):
        """
        Streaming version of chat_with_memory.
        Yields chunks of AI response as they're generated.
        """
        # Format History
        formatted_history = ""
        for msg in history[-10:]:
            role = "User" if msg['role'] == "user" else "Assistant"
            formatted_history += f"{role}: {msg['content']}\n"
        
        # Construct Prompt
        system_prompt = f"""
        You are Acad3mic-Flow AI, an advanced academic assistant. Be helpful, clear, and informative.
        
        CONTEXT:
        1. Existing Chat Summary: "{current_summary}"
        2. Recent Chat History:
        {formatted_history}
        
        USER REQUEST: "{new_message}"
        """
        
        if files_content:
            system_prompt += f"\n\nATTACHED DOCUMENTS:\n{files_content}"
        
        system_prompt += """
        
        YOUR JOB:
        1. Use the summary as long-term memory and history as short-term context.
        2. Respond naturally and helpfully to the user.
        3. If documents are attached, reference them in your response.
        """
        
        try:
            # CRITICAL: Capture the running event loop BEFORE entering any thread.
            # asyncio.get_event_loop() inside a thread is broken in Python 3.10+ —
            # it may return a different/closed loop, causing run_coroutine_threadsafe to fail silently.
            loop = asyncio.get_running_loop()
            chunk_queue = asyncio.Queue()
            _sentinel = object()
            
            def _sync_stream():
                """Runs in a thread pool. Puts chunks into queue using the captured loop."""
                try:
                    response = self.model.generate_content(
                        system_prompt, 
                        stream=True
                    )
                    for chunk in response:
                        try:
                            # Safely check for text to avoid ValueError from safety filters
                            text = ""
                            try:
                                text = chunk.text
                            except (ValueError, IndexError):
                                # If text is unavailable, check why (usually safety)
                                if hasattr(chunk, 'candidates') and chunk.candidates:
                                    reason = chunk.candidates[0].finish_reason
                                    logger.warning(f"Chunk blocked or finished early: {reason}")
                                continue

                            if text:
                                asyncio.run_coroutine_threadsafe(
                                    chunk_queue.put(text),
                                    loop
                                ).result(timeout=5)
                        except Exception as put_err:
                            logger.warning(f"Failed to put chunk in queue: {put_err}")
                except Exception as e:
                    error_str = str(e)
                    logger.error(f"Streaming chat failed in thread: {error_str}")
                    
                    # Try to extract more detail if it's a 400 error
                    final_msg = f"Stream error: {error_str}"
                    if "400" in error_str:
                        final_msg += " (This usually means the prompt was blocked or the model name is incorrect for streaming)"
                        
                    try:
                        asyncio.run_coroutine_threadsafe(
                            chunk_queue.put(Exception(final_msg)),
                            loop
                        ).result(timeout=5)
                    except Exception:
                        pass
                finally:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            chunk_queue.put(_sentinel),
                            loop
                        ).result(timeout=5)
                    except Exception:
                        pass
            
            # Run the sync streaming in a thread
            stream_task = asyncio.ensure_future(asyncio.to_thread(_sync_stream))
            
            # Yield chunks as they arrive in the queue
            while True:
                item = await chunk_queue.get()
                if item is _sentinel:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
                await asyncio.sleep(0)  # Yield control to flush SSE
            
            await stream_task

        except Exception as e:
            error_msg = f"AI streaming failed: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)





    async def update_summary(self, current_summary: str, user_message: str, assistant_reply: str) -> str:
        """
        Lightweight summary updater — does NOT generate a reply, only updates the rolling summary.
        Used after streaming to avoid a second full chat_with_memory() call.
        """
        system_prompt = """
        You maintain a rolling summary of a chat conversation.
        Given the existing summary, the latest user message, and the assistant reply,
        return ONLY a concise updated summary (max 200 words).
        Preserve important facts/decisions. Do NOT repeat messages verbatim.
        Output ONLY the summary text, no JSON, no labels.
        """
        try:
            prompt = (
                f"Current Summary: {current_summary}\n\n"
                f"User: {user_message[:2000]}\n"
                f"Assistant: {assistant_reply[:2000]}\n\n"
                f"Updated Summary:"
            )
            return await self.generate_content(prompt, system_instruction=system_prompt, timeout=20)
        except Exception as e:
            logger.error(f"Summary update failed: {str(e)}")
            return current_summary  # Safe fallback — keep old summary

    async def evaluate_data_sufficiency(self, topic: str, instructions: str, files_content: str = "") -> dict:
        """
        Analyzes assignment requirements to identify missing data or instructions.
        Returns a dict with 'is_sufficient', 'missing_items', and 'action' (ask_user|search_web|none).
        """
        import json
        
        system_prompt = """
        You are an Academic Integrity & Data Sufficiency validator.
        Your job is to determine if the provided assignment topic, instructions, and documents are enough to generate a high-quality (Distinction/A+) response.
        
        Check for:
        1. Specific Datasets: Are there mentions of files/CSV/Excel data that are NOT in the reference content?
        2. Proprietary Case Studies: Does it mention a specific company/scenario that isn't fully described?
        3. Missing Rubrics: Is a specific marking scheme mentioned but not provided?
        4. Ambiguous Quotas: Is the word count or formatting missing?
        
        OUTPUT FORMAT (STRICT JSON):
        {
            "is_sufficient": true/false,
            "missing_items": ["Item 1", "Item 2"],
            "suggested_action": "ask_user" | "search_web" | "none",
            "reason": "Brief explanation"
        }
        
        Note: If the item can be found on Kaggle, Google Scholar, or official websites, suggest "search_web". 
        If it requires a personal/university-private file, suggest "ask_user".
        """
        
        user_prompt = f"TOPIC: {topic}\nINSTRUCTIONS: {instructions}\n\nREFERENCE CONTENT PROVIDED:\n{files_content[:5000]}"
        
        try:
            response = await self.generate_content(
                user_prompt, 
                system_instruction=system_prompt,
                timeout=45
            )
            
            # Clean JSON
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            
            result = json.loads(json_str)
            return result
        except Exception as e:
            logger.error(f"Data sufficiency check failed: {str(e)}")
            return {"is_sufficient": True, "missing_items": [], "suggested_action": "none", "reason": "System error during check"}

    async def perform_web_research(self, missing_item: str, context: str = "") -> str:
        """
        Performs live web research using Serper.dev API.
        Falls back to LLM internal knowledge if no API key is configured.
        """
        import aiohttp
        import json

        serper_api_key = getattr(settings, 'SERPER_API_KEY', None)

        # --- Live Search Path (Serper.dev) ---
        if serper_api_key:
            try:
                search_query = f"academic research {missing_item} site:scholar.google.com OR site:researchgate.net OR site:pubmed.ncbi.nlm.nih.gov"
                headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
                payload = {"q": search_query, "num": 5}

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "https://google.serper.dev/search",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=15)
                    ) as resp:
                        data = await resp.json()

                organic = data.get("organic", [])
                if organic:
                    # Format results as a reference block for the AI
                    snippets = []
                    for r in organic[:5]:
                        snippets.append(f"- [{r.get('title', 'Source')}]({r.get('link', '#')})\n  {r.get('snippet', '')}")
                    live_context = "\n".join(snippets)

                    # Use AI to synthesize the live search results into usable academic text
                    synthesis_prompt = f"""
                    You are an Academic Research Synthesizer.
                    Based on these live search results, write a concise, well-cited academic summary
                    that can be referenced inside an assignment.

                    SEARCH QUERY: {missing_item}
                    SEARCH RESULTS:
                    {live_context}

                    Write a 200-400 word synthesized academic paragraph with in-text citations (Author, Year format).
                    Include a References section at the end in APA format.
                    """
                    return await self.generate_content(synthesis_prompt, timeout=90)

            except Exception as e:
                logger.warning(f"Serper search failed, falling back to LLM knowledge: {str(e)}")

        # --- Fallback: LLM Internal Knowledge ---
        system_prompt = f"""
        You are a Research Assistant using your extensive training knowledge.
        Your goal is to find detailed, factual data about: {missing_item}

        CONTEXT: {context}

        Provide a detailed technical/academic summary with statistics, key theories, and key authors.
        Include properly formatted APA references (even if they must be inferred from your knowledge).
        Do NOT hallucinate — if data is truly unavailable, state it clearly.
        """
        try:
            return await self.generate_content(
                f"Research topic: {missing_item}",
                system_instruction=system_prompt,
                timeout=120
            )
        except Exception as e:
            logger.error(f"Web research failed: {str(e)}")
            return f"Could not retrieve research data for: {missing_item}."

    async def chat_response(self, history: list, new_message: str) -> str:
        # Deprecated fallback/legacy
        pass


ai_service = AIService()

def get_ai_service():
    return ai_service
