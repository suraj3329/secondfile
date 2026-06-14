from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ClaimType(str, Enum):
    STATISTICS = "Statistics"
    DATES = "Dates"
    PERCENTAGES = "Percentages"
    FINANCIAL = "Financial"
    TECHNICAL = "Technical"

class Claim(BaseModel):
    text: str = Field(..., description="The exact statement of the factual claim extracted from the document.")
    type: ClaimType = Field(..., description="The category of the claim (Statistics, Dates, Percentages, Financial, Technical).")
    context: str = Field(..., description="The surrounding context or sentence to help verify the claim.")
    page_number: int = Field(..., description="The 1-based page number where the claim was found in the PDF.")

class SearchResult(BaseModel):
    url: str = Field(..., description="The source URL of the search result.")
    title: str = Field(..., description="The title of the webpage.")
    snippet: str = Field(..., description="A snippet or excerpt of the webpage content relevant to the search query.")
    score: Optional[float] = Field(0.0, description="The search engine's relevance score for the result.")

class SourceCredibility(BaseModel):
    domain: str = Field(..., description="The domain name of the source (e.g., wikipedia.org, sec.gov).")
    category: str = Field(..., description="Category of source (e.g., Government, Academic, News, Corporate, Blog, Social Media).")
    score: int = Field(..., description="Credibility score from 0 to 100.")
    reasoning: str = Field(..., description="Reasoning for the credibility score.")

class VerificationVerdict(str, Enum):
    VERIFIED = "Verified"
    INACCURATE = "Inaccurate"
    FALSE = "False"

class ClaimVerification(BaseModel):
    claim: Claim = Field(..., description="The claim being verified.")
    verdict: VerificationVerdict = Field(..., description="The outcome of the verification (Verified, Inaccurate, False).")
    explanation: str = Field(..., description="A detailed explanation of the verification decision and findings.")
    supporting_excerpts: List[str] = Field(default_factory=list, description="Direct quotes or sentences from the search results that support/refute the claim.")
    sources: List[SearchResult] = Field(default_factory=list, description="List of search sources used to verify the claim.")
    confidence_score: int = Field(..., description="Confidence score from 0 to 100 based on matches and source quality.")
    credibility_score: int = Field(..., description="Credibility score from 0 to 100 of the sources used.")

class VerificationReport(BaseModel):
    total_claims: int = Field(..., description="Total number of claims analyzed.")
    verified_count: int = Field(..., description="Number of claims verified as true.")
    inaccurate_count: int = Field(..., description="Number of claims found to be inaccurate.")
    false_count: int = Field(..., description="Number of claims found to be false.")
    verifications: List[ClaimVerification] = Field(default_factory=list, description="Detailed list of verified claims.")
