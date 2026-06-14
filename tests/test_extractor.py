import pytest
from unittest.mock import MagicMock, patch
from src.extractor import PDFClaimExtractor
from src.models import ClaimType

@patch('google.generativeai.GenerativeModel')
@patch('google.generativeai.configure')
def test_extractor_initialization(mock_configure, mock_model_class):
    """
    Test that the extractor initializes correctly and configures Google GenAI.
    """
    extractor = PDFClaimExtractor(api_key="fake-api-key")
    mock_configure.assert_called_once_with(api_key="fake-api-key")
    mock_model_class.assert_called_once()
    assert extractor.model_name == "gemini-2.5-flash"

@patch('google.generativeai.GenerativeModel')
@patch('google.generativeai.configure')
def test_extractor_claims_parsing(mock_configure, mock_model_class):
    """
    Test that Gemini response is parsed correctly into Claim objects.
    """
    mock_model = MagicMock()
    mock_model_class.return_value = mock_model
    
    # Mock response from Gemini
    mock_response = MagicMock()
    mock_response.text = """
    {
        "claims": [
            {
                "text": "GDP grew by 2.5% in Q3 2023",
                "type": "Percentages",
                "context": "According to the national registry, GDP grew by 2.5% in Q3 2023.",
                "page_number": 2
            },
            {
                "text": "The company was founded on June 12, 1998",
                "type": "Dates",
                "context": "The company was founded on June 12, 1998, in a garage.",
                "page_number": 5
            }
        ]
    }
    """
    mock_model.generate_content.return_value = mock_response
    
    extractor = PDFClaimExtractor(api_key="fake-key")
    pages_data = [
        {"page_number": 2, "text": "GDP grew by 2.5% in Q3 2023."},
        {"page_number": 5, "text": "The company was founded on June 12, 1998."}
    ]
    
    claims = extractor.extract_claims(pages_data)
    
    assert len(claims) == 2
    assert claims[0].text == "GDP grew by 2.5% in Q3 2023"
    assert claims[0].type == ClaimType.PERCENTAGES
    assert claims[0].page_number == 2
    assert claims[1].text == "The company was founded on June 12, 1998"
    assert claims[1].type == ClaimType.DATES
    assert claims[1].page_number == 5

@patch('fitz.open')
def test_extract_text_from_pdf(mock_fitz_open):
    """
    Test PyMuPDF parser extracts text page by page.
    """
    mock_doc = MagicMock()
    mock_fitz_open.return_value = mock_doc
    
    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = "Page 1 Content"
    mock_page2 = MagicMock()
    mock_page2.get_text.return_value = "Page 2 Content"
    
    mock_doc.__len__.return_value = 2
    mock_doc.load_page.side_effect = [mock_page1, mock_page2]
    
    extractor = PDFClaimExtractor(api_key="fake-key")
    result = extractor.extract_text_from_pdf(b"fake pdf bytes")
    
    assert len(result) == 2
    assert result[0] == {"page_number": 1, "text": "Page 1 Content"}
    assert result[1] == {"page_number": 2, "text": "Page 2 Content"}
    mock_doc.close.assert_called_once()
