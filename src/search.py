import os
import requests
import logging
from typing import List, Optional
from src.models import SearchResult

logger = logging.getLogger(__name__)

class WebSearchAgent:
    """
    Search agent that queries the live web using Tavily or Serper API.
    Provides fallback simulation if API keys are missing or requests fail.
    """
    def __init__(self, tavily_api_key: Optional[str] = None, serper_api_key: Optional[str] = None):
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.serper_api_key = serper_api_key or os.getenv("SERPER_API_KEY")

        if not self.tavily_api_key and not self.serper_api_key:
            logger.warning(
                "Neither TAVILY_API_KEY nor SERPER_API_KEY was found. "
                "WebSearchAgent will run in SIMULATION mode returning mock search results."
            )

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Executes web search for the query. Prefers Tavily, falls back to Serper,
        and finally falls back to simulation mode if keys are unavailable.
        """
        if self.tavily_api_key:
            try:
                return self._search_tavily(query, max_results)
            except Exception as e:
                logger.error(f"Tavily search failed: {e}. Trying Serper or fallback...")

        if self.serper_api_key:
            try:
                return self._search_serper(query, max_results)
            except Exception as e:
                logger.error(f"Serper search failed: {e}. Falling back to simulation...")

        return self._search_simulation(query)

    def _search_tavily(self, query: str, max_results: int) -> List[SearchResult]:
        """
        Calls the Tavily Search API.
        """
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False
        }
        
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("results", []):
            results.append(SearchResult(
                url=item.get("url", ""),
                title=item.get("title", "No Title"),
                snippet=item.get("content", ""),
                score=float(item.get("score", 0.0))
            ))
        return results

    def _search_serper(self, query: str, max_results: int) -> List[SearchResult]:
        """
        Calls the Serper.dev Google Search API.
        """
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.serper_api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "q": query,
            "num": max_results
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        results = []
        # Parse organic results
        for idx, item in enumerate(data.get("organic", [])):
            # Calculate mock score based on position (first result is higher)
            score = max(0.95 - (idx * 0.1), 0.1)
            results.append(SearchResult(
                url=item.get("link", ""),
                title=item.get("title", "No Title"),
                snippet=item.get("snippet", ""),
                score=score
            ))
        return results

    def _search_simulation(self, query: str) -> List[SearchResult]:
        """
        Generates simulated search results when API keys are not provided.
        Helps test UI and flow without incurring API costs.
        """
        logger.info(f"Simulating web search for: '{query}'")
        
        # Simple simulated database based on keywords in the query to make it dynamic
        q_lower = query.lower()
        
        if "apple" in q_lower or "revenue" in q_lower or "financial" in q_lower:
            return [
                SearchResult(
                    url="https://www.sec.gov/edgar/searchedgar/companysearch",
                    title="Apple Inc. Form 10-K SEC Filing 2024",
                    snippet="Apple Inc. reported annual revenue of $391.04 billion and net income of $93.74 billion for the fiscal year ended September 28, 2024, compared to revenue of $383.29 billion in 2023.",
                    score=0.98
                ),
                SearchResult(
                    url="https://finance.yahoo.com/quote/AAPL",
                    title="Apple Inc. (AAPL) Financials & News - Yahoo Finance",
                    snippet="AAPL closed at $180.25 with quarterly revenue growth of 4.90% year-over-year. Balance sheet shows cash and equivalents of $29.9 billion as of Q1 2024.",
                    score=0.88
                )
            ]
        elif "gdp" in q_lower or "economic" in q_lower:
            return [
                SearchResult(
                    url="https://www.bea.gov/news/glance",
                    title="US Bureau of Economic Analysis (BEA) - GDP at a Glance",
                    snippet="Real gross domestic product (GDP) increased at an annual rate of 1.6 percent in the first quarter of 2024, down from 3.4 percent in the fourth quarter of 2023.",
                    score=0.96
                ),
                SearchResult(
                    url="https://data.worldbank.org/indicator/NY.GDP.MKTP.CD",
                    title="GDP (current US$) - World Bank Data",
                    snippet="Global GDP reached approximately $105.4 trillion in 2023, with the United States leading at $27.36 trillion, followed by China at $17.79 trillion.",
                    score=0.91
                )
            ]
        elif "population" in q_lower or "census" in q_lower:
            return [
                SearchResult(
                    url="https://www.census.gov/popclock/",
                    title="U.S. and World Population Clock - U.S. Census Bureau",
                    snippet="The current U.S. population is estimated to be approximately 336 million as of mid-2024, and the world population stands at 8.05 billion.",
                    score=0.97
                )
            ]
        
        # General generic fallback search result
        return [
            SearchResult(
                url="https://www.wikipedia.org/wiki/Special:Search",
                title=f"Wikipedia search results for: {query}",
                snippet=f"Factual reference article discussing topics related to: {query}. Historical records and news articles indicate typical details regarding these figures.",
                score=0.5
            )
        ]
