from pydantic import BaseModel, Field
from typing import List, Optional

class TestCaseRequest(BaseModel):
    query: str

class TestCase(BaseModel):
    test_id: str
    feature: str
    test_scenario: str
    expected_result: str
    grounded_in: str

class TestPlan(BaseModel):
    test_viewpoints: List[str] = Field(default_factory=list)
    test_cases: List[TestCase]

class SeleniumScriptRequest(BaseModel):
    test_case: TestCase
    html_content: Optional[str] = None

class SeleniumScriptResponse(BaseModel):
    script_code: str
