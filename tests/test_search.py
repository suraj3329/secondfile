import pytest
from unittest.mock import patch, MagicMock
from src.search import WebSearchAgent

@patch('requests.post')
def test_search_tavily_api_flow(mock_post):
    """
    Verify search routing queries Tavily first and parses results successfully.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Tavily Reference Webpage",
                "url": "https://evidence.org/doc",
                "content": "Factual evidence corroborating the statement.",
                "score": 0.92
            }
        ]
    }
    mock_post.return_value = mock_response
    
    agent = WebSearchAgent(tavily_api_key="tvly-fake-key")
    results = agent.search("query statement", max_results=1)
    
    assert len(results) == 1
    assert results[0].title == "Tavily Reference Webpage"
    assert results[0].url == "https://evidence.org/doc"
    assert results[0].snippet == "Factual evidence corroborating the statement."
    assert results[0].score == 0.92
    
    # Assert post request targets Tavily endpoint
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://api.tavily.com/search"

@patch('requests.post')
def test_search_serper_fallback(mock_post):
    """
    Verify search falls back to Serper if Tavily fails or key is missing.
    """
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [
            {
                "title": "Serper Source Result",
                "link": "https://google-serper.net/article",
                "snippet": "Paragraph explaining factual statistics."
            }
        ]
    }
    mock_post.return_value = mock_response
    
    # Init with only Serper API key
    agent = WebSearchAgent(serper_api_key="serper-fake-key")
    results = agent.search("economic statistics")
    
    assert len(results) == 1
    assert results[0].title == "Serper Source Result"
    assert results[0].url == "https://google-serper.net/article"
    assert results[0].snippet == "Paragraph explaining factual statistics."
    assert results[0].score > 0.0 # Serper gets mock score calculation
    
    # Assert call goes to Serper endpoint
    args, kwargs = mock_post.call_args
    assert args[0] == "https://google.serper.dev/search"

def test_search_simulation_mode():
    """
    Verify agent runs in simulation mode and extracts dynamic results when keys are absent.
    """
    agent = WebSearchAgent()
    results = agent.search("Apple annual revenue and net income 2024")
    
    assert len(results) > 0
    # Should select apple simulation
    assert "apple" in results[0].title.lower() or "sec" in results[0].title.lower()
    assert results[0].score == 0.98
