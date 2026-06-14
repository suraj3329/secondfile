import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv

from src.extractor import PDFClaimExtractor
from src.search import WebSearchAgent
from src.verifier import FactVerifier
from src.reporter import generate_csv, generate_pdf
from src.models import VerificationReport, VerificationVerdict, ClaimType

# Load local environment variables (if any)
load_dotenv()

# Set Streamlit page configuration
st.set_page_config(
    page_title="Fact-Check Agent • Truth Layer for PDFs",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium CSS injection
st.markdown("""
<style>
    /* Styling headers and title */
    .title-container {
        padding: 1.5rem 0rem;
        text-align: center;
        background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
        border-radius: 12px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    }
    .title-text {
        font-family: 'Outfit', 'Inter', sans-serif;
        color: #f8fafc !important;
        font-weight: 800;
        font-size: 2.8rem;
        margin: 0;
    }
    .subtitle-text {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-top: 0.5rem;
    }

    /* Metric cards styling */
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.5rem;
    }

    /* Status badge colors */
    .badge-verified {
        background-color: #dcfce7;
        color: #15803d;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-inaccurate {
        background-color: #fef3c7;
        color: #b45309;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-false {
        background-color: #fee2e2;
        color: #b91c1c;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
    }

    /* Custom layout boxes */
    .claim-box {
        border-left: 4px solid #64748b;
        background-color: #f8fafc;
        padding: 1rem 1.5rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
    }
    .claim-box-verified { border-left-color: #22c55e; }
    .claim-box-inaccurate { border-left-color: #f59e0b; }
    .claim-box-false { border-left-color: #ef4444; }

    /* Button alignment and layout overrides */
    .stButton>button {
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# App Title Header
st.markdown("""
<div class="title-container">
    <h1 class="title-text">🛡️ Fact-Check Agent</h1>
    <div class="subtitle-text">The Truth Layer for PDFs — Extracting and Verifying Claims in Real-Time</div>
</div>
""", unsafe_allow_html=True)

# ----------------- SIDEBAR SETUP -----------------
st.sidebar.image("https://img.icons8.com/color/96/shield.png", width=70)
st.sidebar.title("Configuration")

# API Keys Configuration
st.sidebar.subheader("API Keys Setup")

# Try loading default values from environment
env_gemini_key = os.getenv("GEMINI_API_KEY", "")
env_tavily_key = os.getenv("TAVILY_API_KEY", "")
env_serper_key = os.getenv("SERPER_API_KEY", "")

gemini_key = st.sidebar.text_input(
    "Google Gemini API Key", 
    type="password", 
    value=env_gemini_key,
    help="Required. Used for Claim Extraction (Gemini 2.5 Flash) and Verification reasoning."
)

tavily_key = st.sidebar.text_input(
    "Tavily Search API Key", 
    type="password", 
    value=env_tavily_key,
    help="Optional. Highly optimized search for LLMs. If empty, Serper or Simulation will be used."
)

serper_key = st.sidebar.text_input(
    "Serper Search API Key", 
    type="password", 
    value=env_serper_key,
    help="Optional. Standard Google Search API. Used as secondary option or fallback."
)

# Simulation option if no keys are provided
simulation_mode = False
if not gemini_key:
    st.sidebar.warning("⚠️ Enter a Google Gemini API Key to run claim extraction.")
if not tavily_key and not serper_key:
    simulation_mode = st.sidebar.checkbox(
        "Run in Search Simulation Mode", 
        value=True,
        help="Simulates Google Searches for common queries (Apple revenue, GDP, Census/Population, etc.) if API keys are missing."
    )

st.sidebar.divider()

# Advanced Parameters
st.sidebar.subheader("Advanced Parameters")
confidence_threshold = st.sidebar.slider(
    "Confidence Threshold (%)",
    min_value=0,
    max_value=100,
    value=30,
    help="Hide verified claims below this confidence score from the dashboard views."
)

st.sidebar.markdown("""
### How it works:
1. **Upload** any PDF document (reports, papers, statistics pages).
2. **Claim Agent** parses text (PyMuPDF) and isolates factual assertions.
3. **Search Agent** crawls government sites, financial databases, and trusted sources.
4. **Verifier Agent** audits claims and scores credibility before rendering reports.
""")

# ----------------- MAIN FLOW -----------------

# Initialize session state for verification report
if "report" not in st.session_state:
    st.session_state.report = None
if "claims" not in st.session_state:
    st.session_state.claims = None
if "file_name" not in st.session_state:
    st.session_state.file_name = ""

# File Upload Section
st.subheader("1. Upload Document for Auditing")
uploaded_file = st.file_uploader(
    "Drag & drop or browse your PDF file", 
    type=["pdf"], 
    accept_multiple_files=False,
    help="Limit 200MB. Only PDF documents are currently supported."
)

# Trigger button for fact-checking
can_submit = uploaded_file is not None and len(gemini_key) > 0
if uploaded_file:
    # Clear session state if file changed
    if uploaded_file.name != st.session_state.file_name:
        st.session_state.report = None
        st.session_state.claims = None
        st.session_state.file_name = uploaded_file.name

submit_btn = st.button(
    "Verify Claims", 
    disabled=not can_submit, 
    type="primary", 
    help="Requires Gemini Key to extract claims. Searches will use Tavily/Serper or simulation fallback."
)

if not can_submit and uploaded_file is not None:
    st.info("💡 Please provide a Google Gemini API Key in the sidebar to start verification.")

# Process the PDF
if submit_btn and uploaded_file:
    pdf_bytes = uploaded_file.read()
    
    # Init tools
    try:
        # Create search agent
        if simulation_mode:
            # Explicitly force empty keys to trigger simulation
            search_agent = WebSearchAgent(tavily_api_key="", serper_api_key="")
        else:
            search_agent = WebSearchAgent(tavily_api_key=tavily_key, serper_api_key=serper_key)

        extractor = PDFClaimExtractor(api_key=gemini_key)
        verifier = FactVerifier(api_key=gemini_key, search_agent=search_agent)
        
        # Step 1: Extract Text
        with st.status("Reading and preparing PDF content...", expanded=True) as status:
            status.update(label="Parsing PDF document text (PyMuPDF)...")
            pages_data = extractor.extract_text_from_pdf(pdf_bytes)
            
            # Step 2: Extract Claims
            status.update(label="Extracting testable factual claims using Gemini 2.5 Flash...")
            claims = extractor.extract_claims(pages_data)
            st.session_state.claims = claims
            
            if not claims:
                status.update(label="No testable claims found in PDF", state="complete")
                st.warning("We could not extract any specific testable claims (statistics, dates, financial figures) from this PDF. Please try another file.")
            else:
                st.write(f"✓ Found {len(claims)} candidate claims for verification.")
                
                # Step 3: Fact Verification
                status.update(label="Conducting real-time web verification audits...")
                
                # Setup Streamlit progress bar inside status block
                prog_bar = st.progress(0.0)
                def progress_cb(current, total):
                    prog_bar.progress(float(current / total))
                
                report = verifier.verify_claims(claims, progress_callback=progress_cb)
                st.session_state.report = report
                
                status.update(label="Fact-Check verification audit completed!", state="complete")
                st.success("Verification complete! See results below.")
                
    except Exception as e:
        st.error(f"An error occurred during verification: {str(e)}")
        st.exception(e)

# ----------------- DISPLAY RESULTS -----------------
if st.session_state.report is not None:
    report: VerificationReport = st.session_state.report
    
    st.divider()
    st.subheader("2. Audit Results Dashboard")
    
    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #0f172a;">{report.total_claims}</div>
            <div class="metric-label">Claims Analyzed</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #16a34a;">{report.verified_count}</div>
            <div class="metric-label">✅ Verified</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #d97706;">{report.inaccurate_count}</div>
            <div class="metric-label">⚠️ Inaccurate</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #dc2626;">{report.false_count}</div>
            <div class="metric-label">❌ False</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Export Options
    col_dl1, col_dl2, _ = st.columns([1.5, 1.5, 7])
    with col_dl1:
        csv_data = generate_csv(report)
        st.download_button(
            label="Download CSV Audit Trail",
            data=csv_data,
            file_name=f"factcheck_report_{uploaded_file.name.replace('.pdf', '')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_dl2:
        with st.spinner("Compiling PDF report..."):
            pdf_data = generate_pdf(report)
        st.download_button(
            label="Export Styled PDF Report",
            data=pdf_data,
            file_name=f"factcheck_report_{uploaded_file.name.replace('.pdf', '')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Filtering Dashboard Table
    st.subheader("3. Verification Logs Breakdown")
    
    # Filter controls
    f_col1, f_col2 = st.columns([3, 7])
    with f_col1:
        verdict_filter = st.selectbox(
            "Filter by Verdict",
            options=["All", "Verified (✅)", "Inaccurate (⚠️)", "False (❌)"]
        )
    with f_col2:
        search_filter = st.text_input("Search claims...", value="", help="Search text within factual claims or explanations.")

    # Filter data based on widgets
    filtered_verifications = []
    for v in report.verifications:
        # Filter confidence threshold
        if v.confidence_score < confidence_threshold:
            continue
            
        # Filter Verdict
        if verdict_filter == "Verified (✅)" and v.verdict != VerificationVerdict.VERIFIED:
            continue
        elif verdict_filter == "Inaccurate (⚠️)" and v.verdict != VerificationVerdict.INACCURATE:
            continue
        elif verdict_filter == "False (❌)" and v.verdict != VerificationVerdict.FALSE:
            continue
            
        # Filter search text
        if search_filter:
            text_pool = (v.claim.text + " " + v.explanation).lower()
            if search_filter.lower() not in text_pool:
                continue
                
        filtered_verifications.append(v)

    if not filtered_verifications:
        st.info("No claims matched your current filter criteria.")
    else:
        # Loop through and display claims as styled containers
        for idx, v in enumerate(filtered_verifications):
            verdict_badge = ""
            box_class = "claim-box"
            if v.verdict == VerificationVerdict.VERIFIED:
                verdict_badge = '<span class="badge-verified">✅ Verified</span>'
                box_class += " claim-box-verified"
            elif v.verdict == VerificationVerdict.INACCURATE:
                verdict_badge = '<span class="badge-inaccurate">⚠️ Inaccurate</span>'
                box_class += " claim-box-inaccurate"
            else:
                verdict_badge = '<span class="badge-false">❌ False</span>'
                box_class += " claim-box-false"

            expander_title = f"{v.claim.type.value} Claim on Page {v.claim.page_number} : \"{v.claim.text[:90]}{'...' if len(v.claim.text)>90 else ''}\""
            
            with st.expander(expander_title):
                st.markdown(f"""
                <div class="{box_class}">
                    <p style="font-size: 1.1rem; font-style: italic; margin-bottom: 0.5rem; color: #1e293b;">
                        "{v.claim.text}"
                    </p>
                    <div style="display: flex; gap: 15px; align-items: center; margin-bottom: 0.5rem;">
                        {verdict_badge}
                        <span style="font-size: 0.9rem; color: #64748b;">Confidence: <b>{v.confidence_score}%</b></span>
                        <span style="font-size: 0.9rem; color: #64748b;">Source Credibility: <b>{v.credibility_score}%</b></span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Context in document
                st.markdown(f"**Original Document Context:** *\"{v.claim.context}\"*")
                
                # Findings Explanation
                st.info(f"**Audit Findings:** {v.explanation}")
                
                # Supporting quotes or contradictions
                if v.supporting_excerpts:
                    st.markdown("**Supporting Excerpts & Evidence Quotes:**")
                    for excerpt in v.supporting_excerpts:
                        st.markdown(f"- *\"{excerpt}\"*")
                
                # Sources/Citations Table
                if v.sources:
                    st.markdown("**Search Sources & Citations:**")
                    source_rows = []
                    for s in v.sources:
                        source_rows.append({
                            "Title": s.title,
                            "URL": s.url,
                            "Search Relevance": f"{int(s.score * 100)}%" if s.score else "N/A"
                        })
                    st.dataframe(
                        pd.DataFrame(source_rows),
                        column_config={
                            "URL": st.column_config.LinkColumn("Source URL")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
