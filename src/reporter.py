import io
import csv
from io import BytesIO
from typing import List

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from src.models import VerificationReport, VerificationVerdict

def generate_csv(report: VerificationReport) -> str:
    """
    Generates a CSV summary of the fact-check verification report.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    # Write header
    writer.writerow([
        "Page", 
        "Category", 
        "Factual Claim", 
        "Verdict", 
        "Confidence Score (%)", 
        "Credibility Score (%)", 
        "Explanation", 
        "Sources"
    ])
    
    for v in report.verifications:
        sources_str = "; ".join([s.url for s in v.sources])
        writer.writerow([
            v.claim.page_number,
            v.claim.type.value,
            v.claim.text,
            v.verdict.value,
            v.confidence_score,
            v.credibility_score,
            v.explanation,
            sources_str
        ])
        
    return output.getvalue()

def generate_pdf(report: VerificationReport) -> bytes:
    """
    Generates a beautifully formatted PDF report of the verification outcomes.
    Uses reportlab flowables and custom corporate/clean styles.
    """
    buffer = BytesIO()
    # Margins: 0.5 inches (36pt) to maximize space
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=36, 
        leftMargin=36,
        topMargin=36, 
        bottomMargin=36
    )
    
    story = []
    styles = getSampleStyleSheet()

    # Define clean, modern styling palettes (Hex Colors)
    c_primary = colors.HexColor('#0F172A')   # Slate 900
    c_secondary = colors.HexColor('#475569') # Slate 600
    c_border = colors.HexColor('#E2E8F0')    # Slate 200
    c_green = colors.HexColor('#15803D')     # Green 700
    c_orange = colors.HexColor('#C2410C')    # Orange 700
    c_red = colors.HexColor('#B91C1C')       # Red 700

    # Custom styles
    title_style = ParagraphStyle(
        name='DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=c_primary,
        spaceAfter=8,
        alignment=TA_CENTER
    )
    
    subtitle_style = ParagraphStyle(
        name='DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=c_secondary,
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    h2_style = ParagraphStyle(
        name='DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=8
    )
    
    body_style = ParagraphStyle(
        name='DocBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#334155'), # Slate 700
        spaceAfter=5,
        leading=12
    )
    
    bold_body_style = ParagraphStyle(
        name='DocBoldBody',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    italic_body_style = ParagraphStyle(
        name='DocItalicBody',
        parent=body_style,
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        textColor=colors.HexColor('#1E293B')
    )
    
    badge_style = ParagraphStyle(
        name='DocBadge',
        parent=body_style,
        fontName='Helvetica-Bold',
        fontSize=9.5
    )

    # 1. Document Title
    story.append(Paragraph("Fact-Check Agent: Factual Verification Report", title_style))
    story.append(Paragraph("Truth Layer Audit Report • Generated via AI Fact-Check Agent Pipeline", subtitle_style))
    story.append(Spacer(1, 5))
    
    # 2. Executive Summary Metrics Table
    summary_data = [
        [
            Paragraph("<b>Total Claims Audited</b>", body_style),
            Paragraph("<b>Verified Claims</b>", body_style),
            Paragraph("<b>Inaccurate Claims</b>", body_style),
            Paragraph("<b>False Claims</b>", body_style)
        ],
        [
            Paragraph(f"<font size=14 color='#0F172A'><b>{report.total_claims}</b></font>", body_style),
            Paragraph(f"<font size=14 color='#15803D'><b>{report.verified_count}</b></font>", body_style),
            Paragraph(f"<font size=14 color='#C2410C'><b>{report.inaccurate_count}</b></font>", body_style),
            Paragraph(f"<font size=14 color='#B91C1C'><b>{report.false_count}</b></font>", body_style)
        ]
    ]
    
    t_summary = Table(summary_data, colWidths=[135, 135, 135, 135])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (0,1), (-1,1), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    
    story.append(t_summary)
    story.append(Spacer(1, 15))
    
    # 3. Claims Summary Table
    story.append(Paragraph("Fact-Check Summary Audit Trail", h2_style))
    
    table_content = [[
        Paragraph("<b>Page</b>", bold_body_style),
        Paragraph("<b>Category</b>", bold_body_style),
        Paragraph("<b>Factual Statement Extracted</b>", bold_body_style),
        Paragraph("<b>Verdict</b>", bold_body_style),
        Paragraph("<b>Confidence</b>", bold_body_style)
    ]]
    
    for idx, v in enumerate(report.verifications):
        if v.verdict == VerificationVerdict.VERIFIED:
            verdict_html = f"<font color='#15803D'><b>{v.verdict.value}</b></font>"
        elif v.verdict == VerificationVerdict.INACCURATE:
            verdict_html = f"<font color='#C2410C'><b>{v.verdict.value}</b></font>"
        else:
            verdict_html = f"<font color='#B91C1C'><b>{v.verdict.value}</b></font>"
        
        # Clip statement in summary table if too long to prevent row height explosion
        claim_text = v.claim.text
        if len(claim_text) > 85:
            claim_text = claim_text[:82] + "..."
            
        table_content.append([
            Paragraph(str(v.claim.page_number), body_style),
            Paragraph(v.claim.type.value, body_style),
            Paragraph(claim_text, body_style),
            Paragraph(verdict_html, body_style),
            Paragraph(f"{v.confidence_score}%", body_style)
        ])
        
    t_claims = Table(table_content, colWidths=[35, 75, 290, 80, 60])
    t_claims.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    
    story.append(t_claims)
    story.append(Spacer(1, 15))
    
    # 4. Detailed Audit Logs (Start on new page)
    story.append(PageBreak())
    story.append(Paragraph("Detailed Verification Evidence & Log", h2_style))
    story.append(Spacer(1, 10))
    
    for idx, v in enumerate(report.verifications):
        # Determine color badge
        if v.verdict == VerificationVerdict.VERIFIED:
            color_hex = '#15803D'
            badge_icon = "✅"
        elif v.verdict == VerificationVerdict.INACCURATE:
            color_hex = '#C2410C'
            badge_icon = "⚠️"
        else:
            color_hex = '#B91C1C'
            badge_icon = "❌"
            
        story.append(Paragraph(
            f"<b>Claim #{idx+1} [Page {v.claim.page_number}] • Category: {v.claim.type.value}</b>", 
            bold_body_style
        ))
        story.append(Paragraph(f"\"{v.claim.text}\"", italic_body_style))
        
        # Verdict Sub-header
        story.append(Paragraph(
            f"Verdict: <font color='{color_hex}'><b>{badge_icon} {v.verdict.value}</b></font> | "
            f"Verification Confidence: <b>{v.confidence_score}%</b> | "
            f"Source Credibility Score: <b>{v.credibility_score}%</b>", 
            badge_style
        ))
        
        story.append(Paragraph(f"<b>Audit Findings & Reasoning:</b> {v.explanation}", body_style))
        
        # Supporting excerpts
        if v.supporting_excerpts:
            story.append(Paragraph("<b>Supporting Excerpts from Search:</b>", bold_body_style))
            for excerpt in v.supporting_excerpts:
                # Basic cleaning of newlines in excerpts
                clean_exc = excerpt.replace('\n', ' ').strip()
                story.append(Paragraph(f"• <i>\"{clean_exc}\"</i>", body_style))
                
        # Core Citations
        if v.sources:
            story.append(Paragraph("<b>Verified Sources & Citations:</b>", bold_body_style))
            for s in v.sources[:3]: # limit to top 3 sources to keep report clean
                story.append(Paragraph(
                    f"• <a href='{s.url}' color='#1D4ED8'><u>{s.title or s.url}</u></a>", 
                    body_style
                ))
                
        story.append(Spacer(1, 10))
        # Divider line
        story.append(HRFlowable(
            width="100%", 
            thickness=0.5, 
            color=c_border, 
            spaceBefore=5, 
            spaceAfter=10
        ))
        
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
