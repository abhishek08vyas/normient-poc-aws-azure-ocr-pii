"""OCR corpus generator — produces 10 content files + 10 .gold.txt files."""

import io
import os
import random
import pathlib
from datetime import date, timedelta

from faker import Faker
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Frame, PageTemplate, BaseDocTemplate, NextPageTemplate, PageBreak,
)
from reportlab.lib import colors
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import openpyxl
from openpyxl.styles import Font as XLFont
import fitz  # PyMuPDF

fake = Faker("en_CA")

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "eval" / "ocr-corpus" / "spike-seed"


# ---------------------------------------------------------------------------
# Files 1-2: Clean text PDFs
# ---------------------------------------------------------------------------

def _build_policy_content(variant: int):
    """Return (list of page texts for gold, pdf bytes)."""
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=18, spaceAfter=20)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=14, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=12, leading=16, spaceBefore=4, spaceAfter=8)
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER)

    policy_names = [
        "Internal Control Policy for Wire Transfer Operations",
        "Anti-Money Laundering Compliance Policy",
    ]
    policy_name = policy_names[variant]
    eff_date = date(2025, 1, 15) + timedelta(days=variant * 30)
    version = f"{variant + 1}.0"

    approver_names = [f"{fake.first_name()} {fake.last_name()}" for _ in range(3)]

    sections = [
        ("1. PURPOSE", [
            f"The purpose of this policy is to establish guidelines and procedures for "
            f"{policy_name.lower().replace('policy for ', '').replace('policy', 'operations')} "
            f"within the organization. This policy applies to all departments and business units.",
            "All employees must comply with the requirements set forth in this document. "
            "Failure to adhere to these guidelines may result in disciplinary action in "
            "accordance with the organization's code of conduct.",
            "This policy has been developed in consultation with the Legal, Compliance, "
            "and Risk Management departments to ensure alignment with regulatory requirements "
            "and industry best practices.",
        ]),
        ("2. SCOPE", [
            "This policy applies to all employees, contractors, and third-party service providers "
            "who have access to the organization's financial systems or who are involved in the "
            "processing of financial transactions.",
            "The scope includes all domestic and international wire transfers, electronic funds "
            "transfers, and interbank settlement operations conducted by or on behalf of the "
            "organization.",
            "Exemptions to this policy may only be granted by the Chief Compliance Officer "
            "in writing and must be reviewed quarterly.",
        ]),
        ("3. DEFINITIONS", [
            "Wire Transfer: An electronic transfer of funds between financial institutions "
            "initiated by the sending institution on behalf of the originator.",
            "Dual Authorization: A control mechanism requiring two independent approvals "
            "before a transaction can be executed. Both approvers must be at the manager "
            "level or above.",
            "Threshold Amount: The monetary value above which additional controls and "
            "approvals are required. The current threshold is $10,000 CAD for domestic "
            "transfers and $5,000 CAD for international transfers.",
        ]),
        ("4. ROLES AND RESPONSIBILITIES", [
            "4.1 The Compliance Officer is responsible for monitoring adherence to this policy "
            "and reporting any violations to senior management.",
            "4.2 Branch Managers must ensure that all staff under their supervision are trained "
            "on the requirements of this policy and that training records are maintained.",
            "4.3 The Internal Audit department shall conduct periodic reviews of wire transfer "
            "activities to verify compliance with this policy.",
            "4.4 All employees involved in transaction processing must complete annual "
            "certification confirming their understanding of this policy.",
        ]),
        ("5. PROCEDURES", [
            "5.1 All wire transfer requests must be submitted using the approved request form. "
            "The form must include the originator's name, account number, recipient details, "
            "amount, purpose, and supporting documentation.",
            "5.2 Transfers exceeding the threshold amount require dual authorization. The "
            "first approver reviews the request for completeness and accuracy. The second "
            "approver independently verifies the recipient details and supporting documents.",
            "5.3 All approved transfers must be recorded in the transaction log within one "
            "business day of execution. The log must include the date, time, amount, "
            "participants, and reference number.",
        ]),
        ("6. MONITORING AND REPORTING", [
            "6.1 The Compliance team shall generate daily reports of all wire transfers "
            "exceeding the threshold amount and review them for unusual patterns.",
            "6.2 Monthly summary reports shall be provided to the Risk Committee detailing "
            "total transfer volumes, exception counts, and any identified concerns.",
            "6.3 Any suspicious activity must be reported immediately to the designated "
            "compliance officer and documented in the incident management system.",
        ]),
        ("7. RECORD RETENTION", [
            "All records related to wire transfer operations, including request forms, "
            "approval documentation, and transaction logs, must be retained for a minimum "
            "of seven years in accordance with regulatory requirements.",
            "Electronic records must be stored in the approved document management system "
            "with appropriate access controls. Physical records must be stored in a secure "
            "location with restricted access.",
        ]),
        ("8. POLICY REVIEW", [
            "This policy shall be reviewed annually by the Policy Committee and updated as "
            "necessary to reflect changes in regulatory requirements, organizational structure, "
            "or business processes.",
            "All amendments must be approved by the Chief Compliance Officer and communicated "
            "to all affected personnel within 30 days of approval.",
        ]),
    ]

    # Build gold text page by page
    gold_pages = []

    # Page 1 — title page
    gold_p1 = f"{policy_name}\n\nEffective Date: {eff_date.strftime('%Y-%m-%d')}\nVersion: {version}\n\nCONFIDENTIAL"
    gold_pages.append(gold_p1)

    # Pages 2-9 — body (distribute sections across pages, ~1 section per page)
    for i, (header, paragraphs) in enumerate(sections):
        page_text = header + "\n"
        for p in paragraphs:
            page_text += "\n" + p
        gold_pages.append(page_text)

    # Page 10 — approval
    approval_text = "APPROVAL SIGNATURES\n"
    for i, name in enumerate(approver_names):
        role = ["Chief Compliance Officer", "VP Operations", "Director of Risk Management"][i]
        approval_text += f"\n{role}: {name}\nDate: {eff_date.strftime('%Y-%m-%d')}\nSignature: ____________________\n"
    gold_pages.append(approval_text)

    # Build PDF
    doc = SimpleDocTemplate(buf, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=inch, rightMargin=inch)
    story = []

    # Page 1 — title
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(policy_name, title_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"Effective Date: {eff_date.strftime('%Y-%m-%d')}", body_style))
    story.append(Paragraph(f"Version: {version}", body_style))
    story.append(Spacer(1, inch))
    story.append(Paragraph("CONFIDENTIAL", ParagraphStyle("Conf", parent=body_style, alignment=TA_CENTER, fontSize=14)))
    story.append(PageBreak())

    # Pages 2-9 — body sections
    for header, paragraphs in sections:
        story.append(Paragraph(header, heading_style))
        for p in paragraphs:
            story.append(Paragraph(p, body_style))
        story.append(PageBreak())

    # Page 10 — approval
    story.append(Paragraph("APPROVAL SIGNATURES", heading_style))
    story.append(Spacer(1, 0.3*inch))
    for i, name in enumerate(approver_names):
        role = ["Chief Compliance Officer", "VP Operations", "Director of Risk Management"][i]
        story.append(Paragraph(f"{role}: {name}", body_style))
        story.append(Paragraph(f"Date: {eff_date.strftime('%Y-%m-%d')}", body_style))
        story.append(Paragraph("Signature: ____________________", body_style))
        story.append(Spacer(1, 0.3*inch))

    # Add page numbers via onPage
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Times-Roman", 9)
        canvas.drawCentredString(letter[0]/2, 0.5*inch, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)

    # Add page number to gold text
    for i in range(len(gold_pages)):
        gold_pages[i] += f"\nPage {i + 1}"

    return gold_pages, buf.getvalue()


def generate_clean_policy_pdfs():
    """Files 1-2: 10-page text PDFs."""
    for variant in range(2):
        filename = f"clean_policy_{variant + 1:02d}"
        gold_pages, pdf_bytes = _build_policy_content(variant)

        # Write PDF
        (OUTPUT_DIR / f"{filename}.pdf").write_bytes(pdf_bytes)

        # Write gold text
        gold = ""
        for i, page_text in enumerate(gold_pages):
            if i > 0:
                gold += f"\n--- PAGE {i + 1} ---\n"
            gold += page_text + "\n"
        (OUTPUT_DIR / f"{filename}.gold.txt").write_text(gold, encoding="utf-8", newline="\n")

    print("  Generated clean_policy_01.pdf, clean_policy_02.pdf")


# ---------------------------------------------------------------------------
# Files 3-4: Scanned PDFs
# ---------------------------------------------------------------------------

def _build_scanned_form(variant: int):
    """Return (gold text, clean pdf bytes) for a 2-page wire transfer form."""
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("H", parent=styles["Heading2"], fontSize=14, spaceAfter=12)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=12, leading=16, spaceAfter=4)
    value_style = ParagraphStyle("Value", parent=styles["Normal"], fontSize=12, leading=16, fontName="Courier-Oblique", spaceAfter=8)

    names = [fake.first_name() + " " + fake.last_name() for _ in range(2)]
    acct = f"{random.randint(1000000, 9999999)}"
    amount = f"${random.uniform(5000, 100000):,.2f}"
    form_date = fake.date_between(start_date="-6m", end_date="today").strftime("%Y-%m-%d")
    auth_date = fake.date_between(start_date="-6m", end_date="today").strftime("%Y-%m-%d")

    # Page 1 fields
    p1_fields = [
        ("WIRE TRANSFER APPROVAL FORM", None),
        ("Approver Name:", names[0]),
        ("Date:", form_date),
        ("Account Number:", acct),
        ("Amount:", amount),
    ]
    # Page 2 fields
    p2_fields = [
        ("AUTHORIZATION", None),
        ("Authorization Signature:", names[1]),
        ("Date:", auth_date),
        ("Approved: YES", None),
        ("Remarks:", "Approved for processing."),
    ]

    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=inch, bottomMargin=inch,
                           leftMargin=inch, rightMargin=inch)
    story = []
    for fields in [p1_fields, p2_fields]:
        for label, value in fields:
            if value is None:
                story.append(Paragraph(label, heading))
            else:
                story.append(Paragraph(label, label_style))
                story.append(Paragraph(value, value_style))
            story.append(Spacer(1, 0.15*inch))
        if fields is p1_fields:
            story.append(PageBreak())

    doc.build(story)

    # Gold text
    gold = "WIRE TRANSFER APPROVAL FORM\n"
    gold += f"Approver Name: {names[0]}\n"
    gold += f"Date: {form_date}\n"
    gold += f"Account Number: {acct}\n"
    gold += f"Amount: {amount}\n"
    gold += "\n--- PAGE 2 ---\n"
    gold += "AUTHORIZATION\n"
    gold += f"Authorization Signature: {names[1]}\n"
    gold += f"Date: {auth_date}\n"
    gold += "Approved: YES\n"
    gold += f"Remarks: Approved for processing.\n"

    return gold, buf.getvalue()


def generate_scanned_approval_pdfs():
    """Files 3-4: 2-page scanned forms."""
    for variant in range(2):
        filename = f"scanned_approval_{variant + 3:02d}"
        gold, clean_pdf_bytes = _build_scanned_form(variant)

        # Render clean PDF to images using PyMuPDF
        pdf_doc = fitz.open(stream=clean_pdf_bytes, filetype="pdf")
        noised_images = []
        for page in pdf_doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            # Add noise: slight rotation
            angle = random.uniform(-2, 2)
            img = img.rotate(angle, expand=False, fillcolor=(255, 255, 255))
            # Reduce quality via JPEG round-trip
            jpeg_buf = io.BytesIO()
            img.save(jpeg_buf, format="JPEG", quality=85)
            jpeg_buf.seek(0)
            img = Image.open(jpeg_buf)
            # Slight blur for scan effect
            img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
            # Convert to grayscale
            img = img.convert("L")
            noised_images.append(img)
        pdf_doc.close()

        # Combine images back into PDF using ReportLab
        from reportlab.lib.pagesizes import letter as lt
        out_buf = io.BytesIO()
        from reportlab.pdfgen import canvas as rc
        c = rc.Canvas(out_buf, pagesize=lt)
        for img in noised_images:
            img_buf = io.BytesIO()
            img.save(img_buf, format="PNG")
            img_buf.seek(0)
            from reportlab.lib.utils import ImageReader
            img_reader = ImageReader(img_buf)
            c.drawImage(img_reader, 0, 0, width=lt[0], height=lt[1])
            c.showPage()
        c.save()

        (OUTPUT_DIR / f"{filename}.pdf").write_bytes(out_buf.getvalue())
        (OUTPUT_DIR / f"{filename}.gold.txt").write_text(gold, encoding="utf-8", newline="\n")

    print("  Generated scanned_approval_03.pdf, scanned_approval_04.pdf")


# ---------------------------------------------------------------------------
# Files 5-6: PNG screenshots
# ---------------------------------------------------------------------------

def generate_banking_screenshots():
    """Files 5-6: 1920x1080 PNG banking screenshots."""
    for variant in range(2):
        filename = f"screenshot_banking_{variant + 5:02d}"
        width, height = 1920, 1080

        client_name = f"{fake.first_name()} {fake.last_name()}"
        acct_num = f"{random.randint(1000000, 9999999)}"
        balance = random.uniform(10000, 100000)

        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        # Try to get a monospace font; fall back to default
        try:
            font = ImageFont.truetype("cour.ttf", 14)
            font_header = ImageFont.truetype("cour.ttf", 20)
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_header = font

        # Header bar
        draw.rectangle([0, 0, width, 60], fill="#003366")
        draw.text((20, 18), "Acme Bank - Transaction Dashboard", fill="white", font=font_header)

        # Client info
        y = 80
        info_lines = [
            f"Client: {client_name}",
            f"Account: {acct_num}",
            f"Balance: ${balance:,.2f}",
        ]
        for line in info_lines:
            draw.text((20, y), line, fill="black", font=font)
            y += 25

        y += 20

        # Table headers
        headers = ["Date", "Description", "Debit", "Credit", "Balance", "Reference", "Status", "Approver"]
        col_widths = [120, 180, 100, 100, 120, 120, 100, 160]
        col_x = [20]
        for w in col_widths[:-1]:
            col_x.append(col_x[-1] + w)

        row_height = 30
        num_rows = 10

        # Draw header row
        for i, h in enumerate(headers):
            draw.rectangle([col_x[i], y, col_x[i] + col_widths[i], y + row_height], outline="black")
            draw.text((col_x[i] + 5, y + 7), h, fill="black", font=font)
        y += row_height

        # Generate transaction data
        statuses = ["Approved", "Pending", "Completed"]
        descriptions = ["Wire transfer", "Direct deposit", "Bill payment", "E-transfer",
                        "Payroll", "Service fee", "ATM withdrawal", "POS purchase",
                        "Interest payment", "Account transfer"]
        running = balance
        txn_rows = []
        for r in range(num_rows):
            txn_date = (date(2025, 1, 1) + timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d")
            desc = random.choice(descriptions)
            approver = f"{fake.first_name()} {fake.last_name()}"
            status = random.choice(statuses)
            ref = f"TXN-{random.randint(100000, 999999)}"

            if random.random() < 0.5:
                debit = random.uniform(100, 10000)
                credit = ""
                running -= debit
                debit_str = f"{debit:,.2f}"
                credit_str = ""
            else:
                credit = random.uniform(100, 10000)
                debit = ""
                running += credit
                debit_str = ""
                credit_str = f"{credit:,.2f}"

            row_data = [txn_date, desc, debit_str, credit_str, f"{running:,.2f}", ref, status, approver]
            txn_rows.append(row_data)

            for i, val in enumerate(row_data):
                draw.rectangle([col_x[i], y, col_x[i] + col_widths[i], y + row_height], outline="black")
                draw.text((col_x[i] + 5, y + 7), str(val), fill="black", font=font)
            y += row_height

        img.save(OUTPUT_DIR / f"{filename}.png")

        # Gold text
        gold = "Acme Bank - Transaction Dashboard\n"
        gold += f"Client: {client_name}\n"
        gold += f"Account: {acct_num}\n"
        gold += f"Balance: ${balance:,.2f}\n\n"
        gold += "\t".join(headers) + "\n"
        for row in txn_rows:
            gold += "\t".join(row) + "\n"

        (OUTPUT_DIR / f"{filename}.gold.txt").write_text(gold, encoding="utf-8", newline="\n")

    print("  Generated screenshot_banking_05.png, screenshot_banking_06.png")


# ---------------------------------------------------------------------------
# Files 7-8: Excel exports
# ---------------------------------------------------------------------------

def generate_transaction_excels():
    """Files 7-8: 50-row Excel workbooks."""
    for variant in range(2):
        filename = f"transactions_{variant + 7:02d}"

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Transactions"

        headers = ["Date", "Description", "Account Number", "Debit", "Credit",
                    "Running Balance", "Reference", "Authorized By"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = XLFont(bold=True)
        for col in range(1, len(headers) + 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 15

        running = random.uniform(20000, 100000)
        descriptions = ["Wire transfer", "Direct deposit", "Bill payment", "Vendor payment",
                         "Payroll", "E-transfer", "Service fee", "Interest payment"]
        gold_rows = []

        for row_idx in range(1, 51):
            txn_date = (date(2025, 1, 1) + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d")
            desc = random.choice(descriptions)
            acct_num = f"{random.randint(1000000, 9999999)}"
            auth_by = f"{fake.first_name()} {fake.last_name()}"
            ref = f"TXN-{random.randint(100000, 999999)}"

            if random.random() < 0.5:
                debit = round(random.uniform(100, 50000), 2)
                credit = ""
                running -= debit
                debit_str = f"{debit:.2f}"
                credit_str = ""
            else:
                credit = round(random.uniform(100, 50000), 2)
                debit = ""
                running += credit
                debit_str = ""
                credit_str = f"{credit:.2f}"

            balance_str = f"{running:.2f}"
            row_data = [txn_date, desc, acct_num, debit_str, credit_str, balance_str, ref, auth_by]
            gold_rows.append(row_data)

            ws.cell(row=row_idx + 1, column=1, value=txn_date)
            ws.cell(row=row_idx + 1, column=2, value=desc)
            ws.cell(row=row_idx + 1, column=3, value=acct_num)
            ws.cell(row=row_idx + 1, column=4, value=debit_str if debit_str else "")
            ws.cell(row=row_idx + 1, column=5, value=credit_str if credit_str else "")
            ws.cell(row=row_idx + 1, column=6, value=balance_str)
            ws.cell(row=row_idx + 1, column=7, value=ref)
            ws.cell(row=row_idx + 1, column=8, value=auth_by)

        wb.save(OUTPUT_DIR / f"{filename}.xlsx")

        # Gold text — TSV
        gold = "\t".join(headers) + "\n"
        for row in gold_rows:
            gold += "\t".join(row) + "\n"

        (OUTPUT_DIR / f"{filename}.gold.txt").write_text(gold, encoding="utf-8", newline="\n")

    print("  Generated transactions_07.xlsx, transactions_08.xlsx")


# ---------------------------------------------------------------------------
# Files 9-10: Multi-column PDFs
# ---------------------------------------------------------------------------

def generate_multicolumn_pdfs():
    """Files 9-10: 5-page two-column PDFs with embedded table."""
    from reportlab.platypus import FrameBreak

    for variant in range(2):
        filename = f"multicolumn_control_{variant + 9:02d}"

        page_w, page_h = letter
        margin = 0.75 * inch
        gutter = 0.3 * inch
        col_w = (page_w - 2 * margin - gutter) / 2

        styles = getSampleStyleSheet()
        heading_style = ParagraphStyle("MCH", parent=styles["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=6)
        body_style = ParagraphStyle("MCB", parent=styles["Normal"], fontSize=10, leading=14, spaceBefore=3, spaceAfter=6)
        small_style = ParagraphStyle("MCS", parent=styles["Normal"], fontSize=9, leading=12, spaceBefore=2, spaceAfter=4)

        # 10 control sections to fill 5 pages (2 sections per page across 2 columns)
        control_sections = [
            ("Control Objective 1: Wire Transfer Authorization",
             "Ensure all wire transfers above $10,000 require dual authorization from "
             "two independent approvers. The first approver verifies the request details "
             "and supporting documentation. The second approver independently confirms "
             "the recipient information and transaction purpose. Both approvers must be "
             "at the manager level or above and cannot be the same individual. "
             "All wire transfer requests must be submitted through the approved electronic "
             "system and include complete originator and beneficiary information. Manual "
             "or verbal wire transfer instructions are prohibited.",
             "Testing approach: Select a random sample of 25 wire transfers above the "
             "threshold from the past quarter. For each transfer, verify that two distinct "
             "approver signatures are present on the authorization form and that both "
             "approvers hold the required management level. Document any exceptions found."),
            ("Control Objective 2: Account Opening Verification",
             "All new account openings must include verification of customer identity "
             "using two forms of government-issued identification. The verification must "
             "be documented in the customer file and reviewed by a supervisor within "
             "24 hours of account creation. Enhanced due diligence must be performed for "
             "high-risk customers, politically exposed persons, and non-resident accounts. "
             "The customer risk rating must be assigned at account opening and reviewed "
             "annually thereafter.",
             "Testing approach: Select 20 recently opened accounts. Verify that the "
             "customer file contains copies of two forms of identification and that "
             "the supervisor review sign-off is dated within one business day. Check that "
             "risk ratings are assigned and appropriate for the customer profile."),
            ("Control Objective 3: Transaction Monitoring",
             "The automated transaction monitoring system must flag all transactions "
             "exceeding $50,000 for manual review. Flagged transactions must be reviewed "
             "and dispositioned within 48 hours. All reviews must be documented in the "
             "case management system with a clear rationale for the disposition decision. "
             "Suspicious activity reports must be filed within five business days of "
             "determination. The monitoring thresholds must be reviewed and calibrated "
             "quarterly to ensure effectiveness.",
             "Testing approach: Review system configuration to confirm the $50,000 "
             "threshold is active. Select 30 flagged transactions and verify timely "
             "review and proper documentation in the case management system. Verify that "
             "all suspicious activity reports were filed within the required timeframe."),
            ("Control Objective 4: Segregation of Duties",
             "No single individual may both initiate and approve a financial transaction. "
             "The system must enforce this separation through role-based access controls. "
             "Any attempts to circumvent this control must be logged and reported to the "
             "compliance team within 24 hours. Access roles must be reviewed quarterly "
             "to ensure continued appropriateness. Temporary role assignments for coverage "
             "purposes must be pre-approved and time-limited.",
             "Testing approach: Review user access profiles for all transaction processors. "
             "Verify that no user has both initiator and approver roles. Test the system "
             "by attempting same-user initiation and approval. Review the exception log for "
             "any circumvention attempts during the review period."),
            ("Control Objective 5: Data Backup and Recovery",
             "All critical financial data must be backed up daily with encrypted backups "
             "stored in a geographically separate facility. Recovery testing must be "
             "performed quarterly to verify data integrity and recovery procedures. "
             "Backup completion must be verified by automated monitoring with alerts "
             "for any failures. The recovery point objective is 24 hours and the "
             "recovery time objective is 4 hours for critical systems.",
             "Testing approach: Review backup logs for the past 90 days. Verify daily "
             "backup completion and encryption status. Review the most recent quarterly "
             "recovery test results and confirm successful data restoration within the "
             "defined recovery time objective."),
            ("Control Objective 6: Access Review",
             "User access to financial systems must be reviewed quarterly by department "
             "managers. Any access that is no longer required must be revoked within "
             "five business days of the review. All reviews must be documented and "
             "retained for audit purposes. Privileged access accounts must be reviewed "
             "monthly by the IT Security team. Service accounts must be inventoried "
             "and their access justified semi-annually.",
             "Testing approach: Obtain the most recent quarterly access review report. "
             "Verify that all users were reviewed and that identified revocations were "
             "processed within the required timeframe. Check privileged account reviews."),
            ("Control Objective 7: Vendor Risk Management",
             "All third-party vendors with access to customer data or financial systems "
             "must undergo a risk assessment prior to onboarding and annually thereafter. "
             "Vendor contracts must include data protection clauses, right-to-audit "
             "provisions, and incident notification requirements. High-risk vendors must "
             "provide SOC 2 Type II reports or equivalent assurance documentation. "
             "Vendor performance must be monitored against defined service levels.",
             "Testing approach: Select 15 active vendors with data access. Verify that "
             "initial and annual risk assessments are on file. Review contracts for "
             "required clauses. For high-risk vendors, confirm receipt and review of "
             "SOC 2 reports or equivalent documentation."),
            ("Control Objective 8: Incident Response",
             "All security incidents must be reported to the IT Security team within "
             "one hour of detection. The incident response plan must be activated for "
             "all confirmed incidents. Post-incident reviews must be conducted within "
             "five business days and lessons learned must be documented and communicated "
             "to relevant stakeholders. The incident response plan must be tested "
             "annually through tabletop exercises or simulations.",
             "Testing approach: Review the incident log for the past six months. Verify "
             "that all incidents were reported within the required timeframe. Select five "
             "resolved incidents and verify that post-incident reviews were completed "
             "and lessons learned were documented and distributed."),
            ("Control Objective 9: Change Management",
             "All changes to production financial systems must follow the change management "
             "process including impact assessment, testing, approval, and documentation. "
             "Emergency changes must be retrospectively approved within 48 hours. "
             "All changes must be tracked in the change management system with a complete "
             "audit trail. Rollback procedures must be documented for all changes.",
             "Testing approach: Select 20 recent production changes. Verify that each "
             "change followed the required process including appropriate approvals and "
             "testing documentation. Review emergency changes for retrospective approval. "
             "Verify rollback procedures are documented."),
            ("Control Objective 10: Regulatory Compliance Monitoring",
             "The compliance team must maintain a regulatory inventory covering all "
             "applicable federal and provincial regulations. Regulatory changes must be "
             "assessed for impact within 30 days of publication. Required policy and "
             "procedure updates must be implemented within 90 days. Compliance training "
             "must be completed by all staff annually.",
             "Testing approach: Review the regulatory inventory for completeness. Select "
             "five recent regulatory changes and verify timely impact assessment and "
             "implementation of required updates. Review training completion records "
             "to confirm all staff have completed annual compliance training."),
        ]

        # Table data for page 3
        table_headers = ["Control ID", "Description", "Frequency", "Owner", "Last Tested"]
        owners = ["Risk Manager", "Compliance Lead", "Audit Director", "Operations VP",
                   "IT Security", "Branch Manager", "Treasury Head", "CFO"]
        table_rows = []
        for i in range(8):
            ctrl_id = f"CTL-{variant * 100 + i + 1:03d}"
            desc = f"Control test procedure {i + 1}"
            freq = random.choice(["Monthly", "Quarterly", "Annually", "Semi-annually"])
            owner = owners[i]
            last_tested = (date(2025, 1, 1) + timedelta(days=random.randint(0, 180))).strftime("%Y-%m-%d")
            table_rows.append([ctrl_id, desc, freq, owner, last_tested])

        # Summary text for page 5
        summary_text = (
            "SUMMARY OF FINDINGS: Based on the testing procedures performed, all ten control "
            "objectives were found to be operating effectively during the review period. "
            "No material exceptions were identified. Two minor observations were noted "
            "regarding documentation timeliness and have been communicated to the responsible "
            "department heads for remediation. The overall control environment is assessed "
            "as satisfactory with a low residual risk rating. The next scheduled review "
            "will be conducted in the following quarter. Management has agreed to address "
            "the minor observations within 30 days and will provide evidence of remediation "
            "to the internal audit team for verification."
        )

        # Build story with explicit PageBreaks to ensure 5 pages
        story = []
        gold_pages = []

        # Page 1: Control objectives 1-2 (left column + right column)
        page_gold = ""
        for idx in [0, 1]:
            title, body, testing = control_sections[idx]
            story.append(Paragraph(title, heading_style))
            story.append(Paragraph(body, body_style))
            story.append(Paragraph(testing, small_style))
            if idx == 0:
                story.append(FrameBreak())
                page_gold += f"{title}\n{body}\n{testing}\n"
            else:
                page_gold += f"{title}\n{body}\n{testing}"
        gold_pages.append(page_gold)
        story.append(PageBreak())

        # Page 2: Control objectives 3-4
        page_gold = ""
        for idx in [2, 3]:
            title, body, testing = control_sections[idx]
            story.append(Paragraph(title, heading_style))
            story.append(Paragraph(body, body_style))
            story.append(Paragraph(testing, small_style))
            if idx == 2:
                story.append(FrameBreak())
                page_gold += f"{title}\n{body}\n{testing}\n"
            else:
                page_gold += f"{title}\n{body}\n{testing}"
        gold_pages.append(page_gold)
        story.append(PageBreak())

        # Page 3: Control objectives 5-6 + table (spanning both columns via single-col template)
        story.append(NextPageTemplate("singlecol"))
        story.append(PageBreak())
        page3_gold = ""
        for idx in [4, 5]:
            title, body, testing = control_sections[idx]
            story.append(Paragraph(title, heading_style))
            story.append(Paragraph(body, body_style))
            story.append(Paragraph(testing, small_style))
            page3_gold += f"{title}\n{body}\n{testing}\n"

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Control Testing Summary", heading_style))
        tbl_data = [table_headers] + table_rows
        tbl = Table(tbl_data, colWidths=[80, 180, 90, 110, 90])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(tbl)

        page3_gold += "\nControl Testing Summary\n"
        page3_gold += "\t".join(table_headers) + "\n"
        for row in table_rows:
            page3_gold += "\t".join(row) + "\n"
        gold_pages.append(page3_gold)

        # Page 4: Control objectives 7-10 (back to two-column)
        story.append(NextPageTemplate("twocol"))
        story.append(PageBreak())
        page_gold = ""
        for idx in [6, 7]:
            title, body, testing = control_sections[idx]
            story.append(Paragraph(title, heading_style))
            story.append(Paragraph(body, body_style))
            story.append(Paragraph(testing, small_style))
            if idx == 6:
                story.append(FrameBreak())
                page_gold += f"{title}\n{body}\n{testing}\n"
            else:
                page_gold += f"{title}\n{body}\n{testing}"
        gold_pages.append(page_gold)

        # Page 5: objectives 9-10 + summary (single-column)
        story.append(NextPageTemplate("singlecol"))
        story.append(PageBreak())
        page5_gold = ""
        for idx in [8, 9]:
            title, body, testing = control_sections[idx]
            story.append(Paragraph(title, heading_style))
            story.append(Paragraph(body, body_style))
            story.append(Paragraph(testing, small_style))
            page5_gold += f"{title}\n{body}\n{testing}\n"

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("SUMMARY OF FINDINGS", heading_style))
        story.append(Paragraph(summary_text, body_style))
        page5_gold += f"\nSUMMARY OF FINDINGS\n{summary_text}"
        gold_pages.append(page5_gold)

        # Build PDF
        out_buf = io.BytesIO()

        class TwoColDocTemplate(BaseDocTemplate):
            pass

        left_frame = Frame(margin, margin, col_w, page_h - 2*margin, id="left")
        right_frame = Frame(margin + col_w + gutter, margin, col_w, page_h - 2*margin, id="right")
        two_col_template = PageTemplate(id="twocol", frames=[left_frame, right_frame])
        single_frame = Frame(margin, margin, page_w - 2*margin, page_h - 2*margin, id="single")
        single_col_template = PageTemplate(id="singlecol", frames=[single_frame])

        doc = TwoColDocTemplate(out_buf, pagesize=letter,
                                topMargin=margin, bottomMargin=margin,
                                leftMargin=margin, rightMargin=margin)
        doc.addPageTemplates([two_col_template, single_col_template])
        doc.build(story)

        (OUTPUT_DIR / f"{filename}.pdf").write_bytes(out_buf.getvalue())

        # Write gold text
        gold = gold_pages[0] + "\n"
        for i in range(1, len(gold_pages)):
            gold += f"\n--- PAGE {i + 1} ---\n"
            gold += gold_pages[i] + "\n"
        (OUTPUT_DIR / f"{filename}.gold.txt").write_text(gold, encoding="utf-8", newline="\n")

    print("  Generated multicolumn_control_09.pdf, multicolumn_control_10.pdf")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    random.seed(42)
    Faker.seed(42)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating OCR corpus...")
    generate_clean_policy_pdfs()
    generate_scanned_approval_pdfs()
    generate_banking_screenshots()
    generate_transaction_excels()
    generate_multicolumn_pdfs()

    # Summary
    content_files = [f for f in OUTPUT_DIR.iterdir() if not f.name.endswith(".gold.txt")]
    gold_files = [f for f in OUTPUT_DIR.iterdir() if f.name.endswith(".gold.txt")]
    print(f"\nGenerated {len(content_files)} content files and {len(gold_files)} gold files in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
