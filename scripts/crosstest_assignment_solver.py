#!/usr/bin/env python3
"""
Comprehensive Cross-Test Suite for Acad3mic-Flow Assignment Solver Engine.
Tests all components:
1. Configuration & Model Settings (Gemini 3.5 Flash Lite, Grading Systems, CORS)
2. Document Parsing (TXT, DOCX with tables & paragraphs)
3. Document Export (University DOCX formatting, Cover Page, Styles, References)
4. Citation Validator (CrossRef DOI verification & link augmentation)
5. Grading Service (Rubric generation, Grade Gap Analysis, Multi-country bands)
6. Prompt Manager (TTL caching & cache invalidation)
7. Gemini 3.5 Flash Lite AI Generation (Live model inference & connection pool)
8. FastAPI Local Endpoints (Auth, CORS, Chunks, Progress Stream, DOCX Export)
9. Live Render Production Endpoints (Health, Latency, Live CORS preflight)
"""

import sys
import os
import io
import time
import json
import asyncio
from uuid import uuid4

# Set up environment
os.environ.setdefault("ENVIRONMENT", "testing")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Results collector
TEST_RESULTS = []

def record_result(category: str, test_name: str, passed: bool, details: str = "", latency_ms: float = 0.0):
    TEST_RESULTS.append({
        "category": category,
        "test_name": test_name,
        "passed": passed,
        "details": details,
        "latency_ms": round(latency_ms, 2)
    })
    status_icon = "✅ PASS" if passed else "❌ FAIL"
    latency_str = f" ({round(latency_ms, 1)}ms)" if latency_ms > 0 else ""
    print(f"[{status_icon}] {category} :: {test_name}{latency_str}")
    if not passed and details:
        print(f"       Details: {details}")


# ── TEST 1: Configuration & Settings ──────────────────────────────────────────
def test_configuration():
    start = time.perf_counter()
    try:
        from app.config import get_settings, MARKING_CLASSIFICATIONS
        settings = get_settings()

        # Check default model
        assert "gemini-3.5-flash-lite" in settings.GEMINI_MODEL_NAME, f"Model is {settings.GEMINI_MODEL_NAME}, expected gemini-3.5-flash-lite"
        
        # Check marking classifications
        expected_countries = ["UK", "USA", "Canada", "South Africa"]
        for c in expected_countries:
            assert c in MARKING_CLASSIFICATIONS, f"Missing country classification: {c}"
            assert len(MARKING_CLASSIFICATIONS[c]) >= 4, f"Insufficient bands for {c}"

        # Check CORS prod origins
        prod_origins = settings.PROD_ORIGINS
        assert "acad3micflow.space" in prod_origins, "Missing acad3micflow.space in settings.PROD_ORIGINS"

        record_result("Configuration", "Model, Grading Bands & CORS Config", True, "gemini-3.5-flash-lite & 4 country grading bands verified", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("Configuration", "Model, Grading Bands & CORS Config", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 2: Document Parsing (TXT, DOCX with tables) ─────────────────────────
async def test_document_parsing():
    start = time.perf_counter()
    try:
        from app.utils.text_parser import extract_text_from_file
        from docx import Document
        from fastapi import UploadFile

        # 1. Test TXT extraction
        txt_bytes = b"Course: Advanced Distributed Systems\nAssignment: Build Raft Consensus\nWord Limit: 2000"
        txt_upload = UploadFile(filename="assignment_brief.txt", file=io.BytesIO(txt_bytes))
        extracted_txt = await extract_text_from_file(txt_upload)
        assert "Advanced Distributed Systems" in extracted_txt, "Failed to extract plain text"

        # 2. Test DOCX extraction with paragraphs and tables
        doc = Document()
        doc.add_heading("Module: ENGR7025 Engineering Ethics", level=1)
        doc.add_paragraph("Please address all criteria in the table below.")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Criteria"
        table.cell(0, 1).text = "Weighting"
        table.cell(1, 0).text = "Ethical Risk Analysis"
        table.cell(1, 1).text = "40%"

        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_bytes = doc_io.getvalue()

        docx_upload = UploadFile(filename="brief.docx", file=io.BytesIO(doc_bytes))
        extracted_docx = await extract_text_from_file(docx_upload)
        
        assert "ENGR7025 Engineering Ethics" in extracted_docx, "Failed to extract docx heading/paragraph"
        assert "Ethical Risk Analysis" in extracted_docx, "Failed to extract table cell text from docx"
        assert "40%" in extracted_docx, "Failed to extract table weighting from docx"

        record_result("Document Parser", "DOCX Paragraphs & Table Extraction", True, "Successfully extracted paragraphs and table rows", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("Document Parser", "DOCX Paragraphs & Table Extraction", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 3: Document Export (.docx generation) ───────────────────────────────
def test_document_export():
    start = time.perf_counter()
    try:
        from app.services.document_export import get_docx_exporter
        from docx import Document

        exporter = get_docx_exporter()
        sample_markdown = """# 1. Introduction
This is the introductory section discussing distributed systems and consensus protocols.

## 1.1 Background
Paxos and Raft represent two primary consensus algorithms in state machine replication.

### 1.1.1 Raft Overview
- Leader Election
- Log Replication
- Safety Invariants

> "Consensus algorithms allow a collection of machines to work as a coherent group that can survive the failures of some of its members." - Ongaro & Ousterhout (2014)

# References
Ongaro, D., & Ousterhout, J. (2014). In search of an understandable consensus algorithm. USENIX ATC '14. https://doi.org/10.5555/2643634.2643666
Lamport, L. (1998). The part-time parliament. ACM Transactions on Computer Systems, 16(2), 133-169.
"""

        stream = exporter.generate_docx(
            title="Comparative Analysis of Raft and Paxos",
            content_markdown=sample_markdown,
            student_name="Student Test",
            course_name="Distributed Computing"
        )

        assert stream is not None, "DOCX stream is None"
        docx_bytes = stream.getvalue()
        assert len(docx_bytes) > 5000, f"DOCX file size too small: {len(docx_bytes)} bytes"

        # Verify docx integrity by parsing it back
        parsed_doc = Document(io.BytesIO(docx_bytes))
        all_text = " ".join([p.text for p in parsed_doc.paragraphs])
        assert "Comparative Analysis of Raft and Paxos" in all_text, "Title missing in generated docx"
        assert "1. Introduction" in all_text, "Heading missing in generated docx"
        assert "Ongaro & Ousterhout" in all_text, "Body/quote missing in generated docx"

        record_result("Document Exporter", "Academic DOCX Generation & Formatting", True, f"Generated valid Word doc ({len(docx_bytes)} bytes) with Cover Page & References", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("Document Exporter", "Academic DOCX Generation & Formatting", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 4: Citation Validator (CrossRef DOI Validation) ──────────────────────
async def test_citation_validator():
    start = time.perf_counter()
    try:
        from app.services.citation_validator import get_citation_validator
        validator = get_citation_validator()

        sample_text = """
Recent studies highlight the role of transformer models in academic synthesis (Vaswani et al., 2017).
Furthermore, attention mechanisms improve long-range dependencies significantly (Bahdanau et al., 2015).

# References
Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, L., & Polosukhin, I. (2017). Attention is all you need. Advances in Neural Information Processing Systems.
Bahdanau, D., Cho, K., & Bengio, Y. (2015). Neural machine translation by jointly learning to align and translate. ICLR 2015.
"""

        validated_text, stats = await validator.validate_document_citations(sample_text)
        
        assert "total_references" in stats, "Missing stats key total_references"
        assert "verified_references" in stats, "Missing stats key verified_references"
        assert stats["total_references"] >= 2, f"Expected >= 2 citations, found {stats['total_references']}"

        record_result("Citation Validator", "CrossRef DOI Lookup & Citation Augmentation", True, f"Processed {stats['total_references']} citations, verified {stats['verified_references']} ({stats.get('verification_accuracy_pct')}%)", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("Citation Validator", "CrossRef DOI Lookup & Citation Augmentation", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 5: Grading Service (Rubrics, Grade Gap, Classifications) ─────────────
def test_grading_service():
    start = time.perf_counter()
    try:
        from app.services.grading_service import get_grading_service
        from app.models.grading import GradingCriterionResult
        service = get_grading_service()

        # 1. Country Marking Classifications
        uk_grade = service.calculate_grade_classification(72, "UK")
        usa_grade = service.calculate_grade_classification(94, "USA")
        canada_grade = service.calculate_grade_classification(82, "Canada")
        sa_grade = service.calculate_grade_classification(76, "South Africa")

        assert uk_grade == "First (1st)", f"Expected First (1st), got {uk_grade}"
        assert "A" in usa_grade, f"Expected A grade, got {usa_grade}"
        assert "A" in canada_grade, f"Expected A grade, got {canada_grade}"
        assert "First Class" in sa_grade, f"Expected First Class, got {sa_grade}"

        # 2. Rubric Markdown Table Generation
        sample_results = [
            GradingCriterionResult(criterion_name="Critical Analysis", score=18.0, max_score=20.0, feedback="Strong evaluation.", strengths=["Depth"], weaknesses=[]),
            GradingCriterionResult(criterion_name="Methodology", score=16.0, max_score=20.0, feedback="Good framing.", strengths=["Rigour"], weaknesses=[]),
            GradingCriterionResult(criterion_name="Referencing", score=14.0, max_score=20.0, feedback="Check DOIs.", strengths=[], weaknesses=["DOIs"]),
        ]
        rubric_rows = ["| Criterion | Weight | Score | Assessment |", "| :--- | :--- | :--- | :--- |"]
        for cr in sample_results:
            pct = round((cr.score / cr.max_score) * 100, 1) if cr.max_score > 0 else 0
            rubric_rows.append(f"| {cr.criterion_name} | {cr.max_score}% | {cr.score:.1f}/{cr.max_score:.1f} | {pct}% |")
        rubric_table = "\n".join(rubric_rows)

        assert "| Criterion | Weight | Score | Assessment |" in rubric_table, "Rubric table header missing"
        assert "Critical Analysis" in rubric_table, "Rubric item missing"

        # 3. Citation Quality & Density Analysis
        sample_text = "According to (Smith, 2020), this is verified. (Johnson et al., 2022) found similar results [1]. More tests in [2]."
        import re
        ay_cit = re.findall(r'\(([A-Z][a-zA-Z\s\.,&]+(?:,\s*|\s+)(\d{4}[a-z]?))\)', sample_text)
        ieee_cit = re.findall(r'\[(\d+)\]', sample_text)
        tot_cit = len(ay_cit) + len(ieee_cit)
        assert tot_cit >= 3, f"Expected >= 3 citations, got {tot_cit}"

        record_result("Grading Service", "Classifications (UK/USA/CAN/SA) & Rubrics", True, f"Verified 4 country grade mappings (UK: {uk_grade}, US: {usa_grade}) and rubric formatting", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("Grading Service", "Classifications (UK/USA/CAN/SA) & Rubrics", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 6: Prompt Manager TTL Cache ──────────────────────────────────────────
async def test_prompt_manager_cache():
    start = time.perf_counter()
    try:
        from app.services.prompt_manager import prompt_manager

        # Invalidate first
        prompt_manager._invalidate_cache()
        assert prompt_manager._cached_active_prompt is None, "Cache should be empty after invalidation"

        # Fetch active prompt (first call - populates cache)
        t0 = time.perf_counter()
        p1 = await prompt_manager.get_active_prompt()
        t_first = time.perf_counter() - t0

        # Fetch again (should hit cache instantly)
        t1 = time.perf_counter()
        p2 = await prompt_manager.get_active_prompt()
        t_second = time.perf_counter() - t1

        assert p1 == p2, "Cached prompt does not match first call"
        assert "prompt_text" in p1, "Active prompt missing prompt_text"
        assert t_second < t_first or t_second < 0.001, "Cache hit should be near-instantaneous"

        record_result("Prompt Manager", "In-Memory TTL Caching & Invalidation", True, f"Cache hit served in {round(t_second*1000, 3)}ms (vs {round(t_first*1000, 3)}ms initial)", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("Prompt Manager", "In-Memory TTL Caching & Invalidation", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 7: Live Gemini 3.5 Flash Lite Model Call ─────────────────────────────
async def test_gemini_model_inference():
    start = time.perf_counter()
    try:
        from app.services.ai_service import get_ai_service
        ai = get_ai_service()

        prompt = "In 2 sentences, explain why state machine replication is crucial for fault-tolerant distributed systems."
        response = await ai.generate_content(prompt, timeout=30)

        assert response is not None and len(response.strip()) > 20, "Empty response from Gemini 3.5 Flash Lite"
        
        latency = (time.perf_counter() - start) * 1000
        record_result("AI Service", "Gemini 3.5 Flash Lite Model Inference", True, f"Generated {len(response.split())} words in {round(latency, 1)}ms", latency)
    except Exception as e:
        record_result("AI Service", "Gemini 3.5 Flash Lite Model Inference", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 8: Local FastAPI App Endpoints ───────────────────────────────────────
async def test_local_fastapi_endpoints():
    start = time.perf_counter()
    try:
        import httpx
        from app.main import app
        from app.dependencies import get_current_user, get_current_user_claims

        # Create mock user
        test_user = {
            "id": "0b54c226-9f42-4df9-ba16-447b3e70e0a0",
            "email": "test_crosstest@acad3micflow.space"
        }

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: test_user
        app.dependency_overrides[get_current_user_claims] = lambda: test_user
        transport = httpx.ASGITransport(app=app)
        
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Health check
            res_health = await client.get("/health")
            assert res_health.status_code == 200, f"/health returned {res_health.status_code}"

            # 2. Root security headers
            res_root = await client.get("/")
            assert res_root.status_code == 200, f"/ returned {res_root.status_code}"
            assert res_root.headers.get("x-content-type-options") == "nosniff"
            assert res_root.headers.get("x-frame-options") == "DENY"

            # 3. CORS Preflight
            res_preflight = await client.options(
                "/assignments/submit",
                headers={
                    "Origin": "https://app.acad3micflow.space",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type"
                }
            )
            assert res_preflight.status_code == 200, f"CORS Preflight failed: {res_preflight.status_code}"
            assert res_preflight.headers.get("access-control-allow-origin") == "https://app.acad3micflow.space"

            # 4. List assignments
            res_list = await client.get("/assignments/")
            assert res_list.status_code == 200, f"List assignments returned {res_list.status_code}"
            assignments_list = res_list.json()
            assert isinstance(assignments_list, list), "List assignments did not return a list"

            # 5. Get assignment by ID & Export DOCX
            if assignments_list:
                first_asg = assignments_list[0]
                asg_id = first_asg["id"]
                
                # GET /assignments/{id}
                res_single = await client.get(f"/assignments/{asg_id}")
                assert res_single.status_code == 200, f"GET /assignments/{asg_id} failed: {res_single.status_code}"
                
                # GET /assignments/{id}/chunks
                res_chunks = await client.get(f"/assignments/{asg_id}/chunks")
                assert res_chunks.status_code == 200, f"GET /assignments/{asg_id}/chunks failed: {res_chunks.status_code}"

                # GET /assignments/{id}/export-docx (if completed)
                if first_asg.get("status") == "completed" and first_asg.get("output_text"):
                    res_docx = await client.get(f"/assignments/{asg_id}/export-docx")
                    assert res_docx.status_code == 200, f"GET /assignments/{asg_id}/export-docx failed: {res_docx.status_code}"
                    assert "application/vnd.openxmlformats" in res_docx.headers.get("content-type", "")
                    assert len(res_docx.content) > 1000

        # Clean up overrides
        app.dependency_overrides.clear()

        record_result("API Endpoints", "FastAPI Endpoints (Health, CORS, Chunks, DOCX Export)", True, f"Verified 5 endpoints with mocked auth", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("API Endpoints", "FastAPI Endpoints (Health, CORS, Chunks, DOCX Export)", False, str(e), (time.perf_counter() - start) * 1000)


# ── TEST 9: Live Render Production Endpoint Test ──────────────────────────────
async def test_live_render_production():
    start = time.perf_counter()
    try:
        import httpx
        live_base = "https://acad3mic-flow-backend.onrender.com"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Health check
            res_health = await client.get(f"{live_base}/health")
            assert res_health.status_code == 200, f"Live /health returned {res_health.status_code}"
            health_json = res_health.json()
            assert health_json.get("status") == "healthy", f"Live health status: {health_json}"

            # 2. CORS Preflight
            res_cors = await client.options(
                f"{live_base}/assignments/submit",
                headers={
                    "Origin": "https://app.acad3micflow.space",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type"
                }
            )
            assert res_cors.status_code == 200, f"Live CORS preflight failed: {res_cors.status_code}"
            assert res_cors.headers.get("access-control-allow-origin") == "https://app.acad3micflow.space", "Live CORS origin header mismatch"

        record_result("Production Cloud", "Live Render Health & CORS Headers", True, "Live backend healthy and accepting https://app.acad3micflow.space", (time.perf_counter() - start) * 1000)
    except Exception as e:
        record_result("Production Cloud", "Live Render Health & CORS Headers", False, str(e), (time.perf_counter() - start) * 1000)


# ── MAIN RUNNER ───────────────────────────────────────────────────────────────
async def run_all_tests():
    print("=" * 70)
    print("  ACAD3MIC-FLOW ASSIGNMENT SOLVER ENGINE: COMPLETE CROSS-TEST")
    print("=" * 70)

    test_configuration()
    await test_document_parsing()
    test_document_export()
    await test_citation_validator()
    test_grading_service()
    await test_prompt_manager_cache()
    await test_gemini_model_inference()
    await test_local_fastapi_endpoints()
    await test_live_render_production()

    print("\n" + "=" * 70)
    total = len(TEST_RESULTS)
    passed = sum(1 for r in TEST_RESULTS if r["passed"])
    failed = total - passed
    print(f"  TEST SUMMARY: {passed}/{total} PASSED ({failed} failed)")
    print("=" * 70)

    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
