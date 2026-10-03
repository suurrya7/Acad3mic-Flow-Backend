import logging
import json
import asyncio
from uuid import UUID
from typing import Dict, List, Any, Optional
from app.services.ai_service import get_ai_service
from app.models.grading import GradingRequest, GradingReport, GradingCriterionResult, GradingRubric, RubricCriterion
from app.config import get_settings, TierAllocation

logger = logging.getLogger("grading_service")
settings = get_settings()

class GradingService:
    def __init__(self):
        self.ai_service = get_ai_service()

    async def extract_or_generate_rubric(self, brief_text: str, country: str) -> GradingRubric:
        """
        Layer 2: Rubric Intelligence Engine
        """
        system_prompt = f"""
        You are an Academic Quality Assurance Expert. 
        Your task is to analyze an assignment brief and extract or generate a professional marking rubric.
        
        COUNTRY CONTEXT: {country}
        
        IF A RUBRIC IS DETAILED IN THE BRIEF:
        - Extract all criteria and their specific weightings.
        - If weights aren't clear, distribute them logically based on importance.
        
        IF NO RUBRIC IS PROVIDED:
        - Generate a standard academic rubric appropriate for {country} university standards.
        - Common criteria include: Critical Analysis, Research/Referencing, Structure/Presentation, Understanding of Topic.
        
        OUTPUT FORMAT (STRICT JSON):
        {{
            "criteria": [
                {{
                    "name": "Criterion Name",
                    "weight": 25.0,
                    "description": "What is being assessed...",
                    "descriptors": {{
                        "High Score": "Descriptors for top marks...",
                        "Pass": "Descriptors for minimum pass..."
                    }}
                }}
            ],
            "total_weight": 100.0
        }}
        """
        
        try:
            response = await self.ai_service.generate_content(
                f"Assignment Brief:\n{brief_text[:10000]}", 
                system_instruction=system_prompt
            )
            
            # Extract JSON from response (clean any markdown if present)
            json_str = self.ai_service.extract_json_from_text(response)
            data = json.loads(json_str)
            return GradingRubric(**data)
        except Exception as e:
            logger.error(f"Rubric intelligence failed: {str(e)}")
            # Fallback rubric
            return GradingRubric(criteria=[
                RubricCriterion(name="Knowledge & Understanding", weight=30.0),
                RubricCriterion(name="Critical Analysis", weight=30.0),
                RubricCriterion(name="Structure & Coherence", weight=20.0),
                RubricCriterion(name="Referencing & Citations", weight=20.0)
            ])

    async def evaluate_criterion(self, criterion: RubricCriterion, assignment_text: str, strictness: str) -> GradingCriterionResult:
        """
        Evaluate a single criterion using LLM.
        """
        strictness_guide = {
            "Lenient": "Be encouraging. If they meet the requirement partially, lean towards higher marks. Focus on potential.",
            "Standard": "Be balanced and fair. Use standard university benchmarks.",
            "Very Strict": "Be extremely rigorous. Deduct for any minor flaws. Expect high-level criticality and flawless formatting."
        }
        
        system_prompt = f"""
        You are a Senior University Examiner using a {strictness} marking style.
        
        STRICTNESS GUIDE: {strictness_guide.get(strictness, strictness_guide['Standard'])}
        
        CRITERION TO EVALUATE:
        - Name: {criterion.name}
        - Weight: {criterion.weight}
        - Context: {criterion.description}
        - Descriptors: {json.dumps(criterion.descriptors) if criterion.descriptors else "Standard university levels"}
        
        YOUR JOB:
        1. Read the assignment text.
        2. Assign a score out of {criterion.weight}.
        3. Provide specific, professional feedback.
        4. List 2-3 specific strengths and 2-3 specific weaknesses for this criterion.
        
        OUTPUT FORMAT (STRICT JSON):
        {{
            "score": 0.0,
            "feedback": "Detailed examiner feedback...",
            "strengths": ["Strength 1", "Strength 2"],
            "weaknesses": ["Weakness 1", "Weakness 2"]
        }}
        """
        
        try:
            response = await self.ai_service.generate_content(
                f"Assignment Content:\n{assignment_text[:20000]}", 
                system_instruction=system_prompt
            )
            
            json_str = self.ai_service.extract_json_from_text(response)
            data = json.loads(json_str)
            return GradingCriterionResult(
                criterion_name=criterion.name,
                score=data['score'],
                max_score=criterion.weight,
                feedback=data['feedback'],
                strengths=data['strengths'],
                weaknesses=data['weaknesses']
            )
        except Exception as e:
            logger.error(f"Criterion evaluation failed for {criterion.name}: {str(e)}")
            return GradingCriterionResult(
                criterion_name=criterion.name,
                score=criterion.weight * 0.5,
                max_score=criterion.weight,
                feedback="Evaluation failed due to technical error.",
                strengths=[],
                weaknesses=[]
            )

    def calculate_grade_classification(self, score: float, country: str) -> str:
        """
        Maps score to classification based on country.
        """
        classifications = TierAllocation.MARKING_CLASSIFICATIONS.get(country, TierAllocation.MARKING_CLASSIFICATIONS["UK"])
        for label, (low, high) in classifications.items():
            if low <= score <= high:
                return label
        return "Fail"

    async def generate_full_report(self, request: GradingRequest) -> GradingReport:
        """
        Main entry point for the grading algorithm.
        """
        # 1. Rubric Extraction
        rubric = await self.extract_or_generate_rubric(request.brief_text, request.country)
        
        # 2. Parallel Evaluation of Criteria
        tasks = [self.evaluate_criterion(c, request.assignment_text, request.strictness) for c in rubric.criteria]
        criterion_results = await asyncio.gather(*tasks)
        
        # 3. Rule-Based Validation Layer (Citation Quality & Density)
        import re
        word_count = len(request.assignment_text.split())
        
        # Regex for Harvard/APA in-text: (Smith, 2021) or (Smith et al., 2023)
        author_year_citations = re.findall(r'\(([A-Z][a-zA-Z\s\.,&]+(?:,\s*|\s+)(\d{4}[a-z]?))\)', request.assignment_text)
        # Regex for IEEE style: [1], [2-4]
        ieee_citations = re.findall(r'\[(\d+)\]', request.assignment_text)
        
        detected_citations = len(author_year_citations) + len(ieee_citations)
        citation_count = max(detected_citations, request.assignment_text.count("(") + request.assignment_text.count("["))
        
        # Citation recency and density metrics
        current_year = 2026
        years = [int(m[1][:4]) for m in author_year_citations if m[1][:4].isdigit()]
        recent_years = [y for y in years if y >= (current_year - 5)]
        recency_ratio = round(len(recent_years) / len(years), 2) if years else 0.5
        density_per_1000 = round((citation_count / max(1, word_count)) * 1000, 1)
        citation_health = "Excellent" if density_per_1000 >= 10 and recency_ratio >= 0.5 else ("Good" if density_per_1000 >= 5 else "Needs Improvement")
        
        citation_quality_metrics = {
            "total_citations": citation_count,
            "density_per_1000_words": density_per_1000,
            "recent_sources_ratio": recency_ratio,
            "citation_health": citation_health
        }

        # 3b. Structured Markdown Rubric Table
        rubric_table_rows = ["| Criterion | Weight | Score | Assessment |", "| :--- | :--- | :--- | :--- |"]
        for cr in criterion_results:
            pct = round((cr.score / cr.max_score) * 100, 1) if cr.max_score > 0 else 0
            rubric_table_rows.append(f"| {cr.criterion_name} | {cr.max_score}% | {cr.score:.1f}/{cr.max_score:.1f} | {pct}% |")
        rubric_table_markdown = "\n".join(rubric_table_rows)
        
        # 4. Strictness Bias Logic (Layer 3)
        raw_total_score = sum(r.score for r in criterion_results)
        
        bias = 0
        if request.strictness == "Lenient":
            bias = 5.0 # +5% bias
        elif request.strictness == "Very Strict":
            bias = -5.0 # -5% tolerance
            
        final_score = max(0, min(100, raw_total_score + bias))
        
        # 5. Grade Classification
        classification = self.calculate_grade_classification(final_score, request.country)
        
        # 6. Generate Overall Comments, Improvements & Grade Gap Analysis
        summary_prompt = f"""
        You are the Head Academic Examiner evaluating an assignment according to {request.country} university standards.
        
        STATS:
        - Score: {final_score:.1f}/100
        - Classification: {classification}
        - Word Count: {word_count}
        - Citation Health: {citation_health} (Density: {density_per_1000}/1k words, Recent Ratio: {int(recency_ratio*100)}%)
        
        CRITERIA SCORES:
        {json.dumps([r.dict() for r in criterion_results])}

        TASK:
        1. Write professional examiner comments explaining why this grade was awarded.
        2. Provide 3-5 high-impact, actionable improvement suggestions.
        3. Provide a 'Grade Gap Analysis': For each criterion where marks were dropped, explain what precise changes are required to elevate the work to the next higher grade classification band.
        
        OUTPUT FORMAT (STRICT JSON):
        {{
            "examiner_comments": "A paragraph of professionally formatted summary comments...",
            "improvement_suggestions": ["Actionable step 1", "Actionable step 2", "Actionable step 3"],
            "grade_gap_analysis": ["To reach the next grade band in [Criterion]: [Specific edit required]"]
        }}
        """
        
        try:
            summary_res = await self.ai_service.generate_content(summary_prompt)
            
            json_str = self.ai_service.extract_json_from_text(summary_res)
            summary_data = json.loads(json_str)
            
            return GradingReport(
                title=f"Evaluation: {request.brief_text[:50]}...",
                overall_score=round(final_score, 1),
                grade_classification=classification,
                criterion_results=criterion_results,
                examiner_comments=summary_data.get('examiner_comments', 'No comments provided.'),
                improvement_suggestions=summary_data.get('improvement_suggestions', []),
                grade_gap_analysis=summary_data.get('grade_gap_analysis', []),
                rubric_table_markdown=rubric_table_markdown,
                word_count=word_count,
                referencing_style_detected="Detected from content",
                citation_count=citation_count,
                citation_quality_metrics=citation_quality_metrics,
                assignment_id=request.assignment_id,
                country=request.country,
                strictness=request.strictness,
                brief_text=request.brief_text,
                assignment_text=request.assignment_text,
                rubric_json=rubric.dict(),
                brief_document_ids=request.brief_document_ids,
                assignment_document_ids=request.assignment_document_ids
            )
        except Exception as e:
            logger.error(f"Final summary generation failed: {str(e)}\nRaw AI Response: {summary_res if 'summary_res' in locals() else 'None'}")
            return GradingReport(
                title="Evaluation Report",
                overall_score=round(final_score, 1),
                grade_classification=classification,
                criterion_results=criterion_results,
                examiner_comments="Manual review recommended. Technical error in summary generation.",
                improvement_suggestions=[],
                grade_gap_analysis=[],
                rubric_table_markdown=rubric_table_markdown,
                word_count=word_count,
                referencing_style_detected="N/A",
                citation_count=citation_count,
                citation_quality_metrics=citation_quality_metrics,
                assignment_id=request.assignment_id,
                country=request.country,
                strictness=request.strictness,
                brief_text=request.brief_text,
                assignment_text=request.assignment_text,
                rubric_json=rubric.dict() if 'rubric' in locals() else None,
                brief_document_ids=request.brief_document_ids,
                assignment_document_ids=request.assignment_document_ids
            )

grading_service = GradingService()

def get_grading_service():
    return grading_service
