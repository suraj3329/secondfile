import logging
import re
from urllib.parse import urlparse
from typing import List, Dict, Any, Tuple
import google.generativeai as genai
from pydantic import BaseModel, Field

from src.models import (
    Claim, 
    ClaimVerification, 
    SearchResult, 
    VerificationVerdict, 
    SourceCredibility,
    VerificationReport
)
from src.search import WebSearchAgent

logger = logging.getLogger(__name__)

# Pydantic model for structured output from Gemini
class LLMVerificationResult(BaseModel):
    verdict: VerificationVerdict = Field(..., description="The outcome of the verification (Verified, Inaccurate, False).")
    explanation: str = Field(..., description="A detailed explanation of why this verdict was chosen based on the evidence.")
    supporting_excerpts: List[str] = Field(..., description="Exact quotes or sentences from the provided evidence that prove/disprove the claim.")
    confidence_score: int = Field(..., description="Confidence score from 0 to 100 based on evidence strength.")
    credibility_reasoning: str = Field(..., description="Reasoning regarding the credibility of the sources in the evidence.")

class FactVerifier:
    """
    Orchestrates the verification of factual claims.
    Coordinates search queries, source credibility scoring, and LLM-based verification.
    """
    def __init__(self, api_key: str, search_agent: WebSearchAgent, model_name: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("Gemini API key must be provided to initialize FactVerifier.")
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.search_agent = search_agent
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=(
                "You are an elite Fact-Checking Agent. Your role is to determine if claims are Verified, Inaccurate, "
                "or False based strictly on the provided web search evidence.\n"
                "Strict Rules:\n"
                "1. If a claim contains statistics/dates/numbers that are different from the evidence, mark it 'Inaccurate' or 'False'.\n"
                "2. Outdated claims (e.g. saying 2020 revenue is the current revenue) must be flagged as 'Inaccurate' or 'False'.\n"
                "3. Do not assume or extrapolate. If the evidence directly contradicts the claim, it is 'False'. If the evidence does not mention the claim and no trusted sources support it, mark it 'False'.\n"
                "4. Be objective and provide clear explanation and direct excerpts."
            )
        )

    def get_domain_credibility(self, url: str) -> SourceCredibility:
        """
        Statically assesses domain credibility based on URL patterns.
        """
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            # Remove www. if present
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            return SourceCredibility(
                domain="unknown",
                category="Unknown",
                score=30,
                reasoning="Invalid or unparseable URL."
            )

        # Basic domain credibility rules
        if any(domain.endswith(ext) for ext in [".gov", ".mil", ".gov.uk", ".gov.sg", ".gov.au"]):
            return SourceCredibility(
                domain=domain,
                category="Government",
                score=95,
                reasoning="Official government domain, representing a highly trusted primary source."
            )
        elif any(domain.endswith(ext) for ext in [".edu", ".ac.uk", ".edu.sg"]):
            return SourceCredibility(
                domain=domain,
                category="Academic",
                score=90,
                reasoning="Academic institution, typically subject to peer review and academic standards."
            )
        elif domain in ["wikipedia.org", "en.wikipedia.org"]:
            return SourceCredibility(
                domain=domain,
                category="Reference",
                score=80,
                reasoning="Publicly edited encyclopedia with citation requirements; generally reliable but check primary links."
            )
        elif any(tld in domain for tld in ["reuters.com", "bloomberg.com", "apnews.com", "nytimes.com", "wsj.com", "ft.com", "bbc.co.uk", "bbc.com"]):
            return SourceCredibility(
                domain=domain,
                category="Trusted News",
                score=85,
                reasoning="Reputable global news organization with rigorous journalism standards."
            )
        elif any(tld in domain for tld in ["github.com", "w3.org", "ietf.org"]):
            return SourceCredibility(
                domain=domain,
                category="Technical Reference",
                score=85,
                reasoning="Established technical platform or standards body."
            )
        elif domain.endswith(".org"):
            return SourceCredibility(
                domain=domain,
                category="Organization",
                score=75,
                reasoning="Non-profit or non-governmental organization. Usually credible, but can have advocacy bias."
            )
        elif any(bad_dom in domain for bad_dom in ["medium.com", "blogspot.com", "wordpress.com", "reddit.com", "twitter.com", "x.com", "facebook.com", "youtube.com"]):
            return SourceCredibility(
                domain=domain,
                category="Social Media/Blog",
                score=30,
                reasoning="User-generated content platforms, lacking editorial oversight and review."
            )
        else:
            # General corporate or news domain
            return SourceCredibility(
                domain=domain,
                category="General Web",
                score=60,
                reasoning="Standard commercial website. Verify with primary sources."
            )

    def generate_search_query(self, claim: Claim) -> str:
        """
        Creates a optimized search query for verifying the claim.
        Focuses on dates, key entities, and figures to avoid generic queries.
        """
        # Clean claim text of redundant symbols
        clean_text = re.sub(r'[^\w\s\-\.\%\$]', '', claim.text)
        # Combine claim text with type or specific entities if needed
        # We can pass the clean text itself, limiting length
        words = clean_text.split()
        if len(words) > 15:
            # Truncate if too long to make search engines happy
            query = " ".join(words[:12])
        else:
            query = clean_text
            
        return query

    def verify_single_claim(self, claim: Claim) -> ClaimVerification:
        """
        Verifies a single claim: runs search, assesses sources, sends to LLM, and formats results.
        """
        # 1. Generate search query
        query = self.generate_search_query(claim)
        
        # 2. Get search results
        search_results = self.search_agent.search(query)
        
        if not search_results:
            # Handle empty search results gracefully
            return ClaimVerification(
                claim=claim,
                verdict=VerificationVerdict.FALSE,
                explanation="No search results were found to corroborate this claim. It is treated as unsubstantiated.",
                supporting_excerpts=["No search evidence available."],
                sources=[],
                confidence_score=10,
                credibility_score=0
            )

        # 3. Assess credibility of all sources statically
        credibility_scores = []
        evidence_lines = []
        for idx, result in enumerate(search_results):
            cred = self.get_domain_credibility(result.url)
            credibility_scores.append(cred.score)
            evidence_lines.append(
                f"[Source {idx+1}]: {result.title}\n"
                f"URL: {result.url}\n"
                f"Source Credibility Category: {cred.category} (Score: {cred.score}/100)\n"
                f"Content: {result.snippet}\n"
            )

        average_credibility = int(sum(credibility_scores) / len(credibility_scores)) if credibility_scores else 50
        evidence_text = "\n".join(evidence_lines)

        # 4. Construct prompt for LLM verification
        prompt = (
            f"Please verify the following claim:\n"
            f"Claim: \"{claim.text}\"\n"
            f"Category of claim: {claim.type.value}\n"
            f"Context in document: \"{claim.context}\"\n"
            f"Document Page Number: {claim.page_number}\n\n"
            f"Here is the web evidence collected:\n"
            f"{evidence_text}\n\n"
            f"Compare the claim details (numbers, dates, entities, facts) with the evidence. "
            f"Determine if the claim is Verified, Inaccurate, or False. "
            f"Fill out the response JSON structure."
        )

        try:
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=LLMVerificationResult,
                temperature=0.1,  # Lower temperature for strict factual accuracy
            )

            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )

            if not response.text:
                raise ValueError("Verification model returned empty text.")

            llm_result = LLMVerificationResult.model_validate_json(response.text)

            # Let's adjust confidence score to combine LLM-rated confidence and source credibility
            # A claim verified using low-credibility blogs should have a lower confidence score
            adjusted_confidence = int((llm_result.confidence_score * 0.6) + (average_credibility * 0.4))
            # Clip between 0 and 100
            adjusted_confidence = max(0, min(100, adjusted_confidence))

            return ClaimVerification(
                claim=claim,
                verdict=llm_result.verdict,
                explanation=llm_result.explanation,
                supporting_excerpts=llm_result.supporting_excerpts,
                sources=search_results,
                confidence_score=adjusted_confidence,
                credibility_score=average_credibility
            )

        except Exception as e:
            logger.error(f"Error during claim verification LLM call: {e}")
            # Fallback verification in case of error
            return ClaimVerification(
                claim=claim,
                verdict=VerificationVerdict.INACCURATE,
                explanation=f"Error running verification model: {str(e)}. Sources were collected but verification failed.",
                supporting_excerpts=[],
                sources=search_results,
                confidence_score=20,
                credibility_score=average_credibility
            )

    def verify_claims(self, claims: List[Claim], progress_callback=None) -> VerificationReport:
        """
        Orchestrates verification across a list of claims.
        Updates progress_callback with (current_index, total_claims) if provided.
        """
        verifications = []
        total = len(claims)
        
        verified_count = 0
        inaccurate_count = 0
        false_count = 0

        for idx, claim in enumerate(claims):
            if progress_callback:
                progress_callback(idx, total)
                
            verification = self.verify_single_claim(claim)
            verifications.append(verification)

            if verification.verdict == VerificationVerdict.VERIFIED:
                verified_count += 1
            elif verification.verdict == VerificationVerdict.INACCURATE:
                inaccurate_count += 1
            elif verification.verdict == VerificationVerdict.FALSE:
                false_count += 1

        if progress_callback:
            progress_callback(total, total)

        return VerificationReport(
            total_claims=total,
            verified_count=verified_count,
            inaccurate_count=inaccurate_count,
            false_count=false_count,
            verifications=verifications
        )
