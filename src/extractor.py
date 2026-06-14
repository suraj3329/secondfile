import fitz  # PyMuPDF
import json
import logging
from typing import List, Dict, Any
import google.generativeai as genai
from pydantic import BaseModel
from src.models import Claim, ClaimType

logger = logging.getLogger(__name__)

class ClaimList(BaseModel):
    claims: List[Claim]

class PDFClaimExtractor:
    """
    Extracts plain text from PDF pages and uses Gemini to identify and structure testable factual claims.
    """
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        if not api_key:
            raise ValueError("API key must be provided to initialize PDFClaimExtractor.")
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=(
                "You are an expert Fact-Checking Claim Extractor. Your role is to read the text content of a document "
                "along with page references, and extract specific, testable, factual claims. "
                "Focus on extracting: \n"
                "- Statistics (e.g., population growth, scientific measurements)\n"
                "- Dates (e.g., historical events, launch dates, deadline dates)\n"
                "- Percentages (e.g., market share, conversion rates, statistical percentages)\n"
                "- Financial figures (e.g., revenue, net income, valuation, growth rates)\n"
                "- Technical claims (e.g., performance speeds, memory capabilities, software versions)\n\n"
                "Do NOT extract opinions, general advice, vague descriptions, predictions, or non-verifiable statements. "
                "Each claim must be precise and specify the page number it was extracted from."
            )
        )

    def extract_text_from_pdf(self, pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extract text page-by-page from PDF bytes using PyMuPDF (fitz).
        Returns a list of dictionaries with 'page_number' and 'text'.
        """
        pages_data = []
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                pages_data.append({
                    "page_number": page_num + 1,
                    "text": text.strip()
                })
            doc.close()
        except Exception as e:
            logger.error(f"Error reading PDF bytes: {e}")
            raise RuntimeError(f"Failed to parse PDF document: {str(e)}")
        
        return pages_data

    def extract_claims(self, pages_data: List[Dict[str, Any]]) -> List[Claim]:
        """
        Sends the page-by-page text to Gemini and retrieves a structured list of claims.
        """
        if not pages_data:
            return []

        # Prepare payload showing page boundaries to help the model maintain references
        document_payload = []
        total_length = 0
        for page in pages_data:
            document_payload.append(f"--- PAGE {page['page_number']} ---\n{page['text']}\n")
            total_length += len(page['text'])

        full_text_input = "\n".join(document_payload)
        
        # Define instruction and prompt
        prompt = (
            f"Please extract all factual claims from the document below. "
            f"Here is the text including page indicators:\n\n{full_text_input}"
        )

        try:
            # Using Gemini structured schema output
            generation_config = genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=ClaimList,
                temperature=0.1,  # Low temperature for deterministic factual extraction
            )
            
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if not response.text:
                logger.warning("Gemini returned an empty response.")
                return []
                
            # Parse the JSON response structured as ClaimList
            parsed_data = ClaimList.model_validate_json(response.text)
            return parsed_data.claims
            
        except Exception as e:
            logger.error(f"Error during claim extraction LLM call: {e}")
            # Fallback simple parsing/cleanup if needed, or raise
            raise RuntimeError(f"Failed to extract claims from document text: {str(e)}")
