import pytest
from unittest.mock import patch, MagicMock
from src.verifier import FactVerifier
from src.models import Claim, ClaimType, VerificationVerdict, SearchResult

def test_domain_credibility_calculation():
    """
    Test static credibility scores assigned to different domains.
    """
    # Create mock search agent
    mock_search = MagicMock()
    verifier = FactVerifier(api_key="fake-key", search_agent=mock_search)
    
    # Test Government
    gov = verifier.get_domain_credibility("https://www.sec.gov/edgar/search")
    assert gov.category == "Government"
    assert gov.score == 95
    
    # Test Academic
    edu = verifier.get_domain_credibility("https://research.harvard.edu/paper.pdf")
    assert edu.category == "Academic"
    assert edu.score == 90
    
    # Test Trusted News
    news = verifier.get_domain_credibility("https://reuters.com/business/finance")
    assert news.category == "Trusted News"
    assert news.score == 85
    
    # Test Blog
    blog = verifier.get_domain_credibility("https://medium.com/@anonymous/my-opinion")
    assert blog.category == "Social Media/Blog"
    assert blog.score == 30

@patch('google.generativeai.GenerativeModel')
@patch('google.generativeai.configure')
def test_verify_single_claim_flow(mock_configure, mock_model_class):
    """
    Verify claim flows to LLM verifier and formats adjusted confidence values.
    """
    mock_model = MagicMock()
    mock_model_class.return_value = mock_model
    
    # Mock LLM verification response text
    mock_response = MagicMock()
    mock_response.text = """
    {
        "verdict": "Verified",
        "explanation": "The claim is fully backed by SEC filings.",
        "supporting_excerpts": ["Apple reported revenue of $391.04 billion in 2024."],
        "confidence_score": 90,
        "credibility_reasoning": "Primary SEC sources are reliable."
    }
    """
    mock_model.generate_content.return_value = mock_response
    
    # Mock search agent returning governmental results
    mock_search = MagicMock()
    mock_search.search.return_value = [
        SearchResult(
            url="https://sec.gov/aapl-10k.htm",
            title="Apple SEC 10K Filings",
            snippet="Apple reported revenue of $391.04 billion in 2024.",
            score=0.99
        )
    ]
    
    verifier = FactVerifier(api_key="fake-key", search_agent=mock_search)
    claim = Claim(
        text="Apple revenue was $391.04 billion in 2024",
        type=ClaimType.FINANCIAL,
        context="For the year 2024, Apple revenue was $391.04 billion.",
        page_number=1
    )
    
    verification = verifier.verify_single_claim(claim)
    
    assert verification.verdict == VerificationVerdict.VERIFIED
    assert verification.explanation == "The claim is fully backed by SEC filings."
    assert verification.confidence_score > 80  # Blend of LLM 90% and Government domain 95%
    assert verification.credibility_score == 95  # Government domain score is 95
    assert len(verification.sources) == 1
    assert verification.sources[0].url == "https://sec.gov/aapl-10k.htm"
