from app.services.grading_service import get_grading_service
from app.models.grading import GradingRequest
import json

async def test_summary():
    service = get_grading_service()
    
    request = GradingRequest(
        brief_text="Write a 100 word essay about dogs.",
        assignment_text="Dogs are great pets. They are loyal and fun to play with. I love my dog very much.",
        country="UK",
        strictness="Standard"
    )
    
    print("Generating report...")
    report = await service.generate_full_report(request)
    
    print("\n--- REPORT RESULTS ---")
    print(f"Overall Score: {report.overall_score}")
    print(f"Examiner Comments: {report.examiner_comments}")
    print(f"Improvement Suggestions: {report.improvement_suggestions}")
    
    if "Manual review recommended" in report.examiner_comments:
        print("\n❌ Summary generation still failing!")
    else:
        print("\n✅ Summary generation successful!")

if __name__ == "__main__":
    asyncio.run(test_summary())
