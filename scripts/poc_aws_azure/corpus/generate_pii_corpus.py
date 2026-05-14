"""PII corpus generator — produces 200 .txt files + answers.json with verified offsets."""

import json
import random
import pathlib
from faker import Faker

from scripts.poc_aws_azure.corpus.sin_utils import generate_valid_sin, validate_sin
from scripts.poc_aws_azure.corpus.name_pools import (
    FRENCH_FIRST_NAMES, FRENCH_LAST_NAMES,
    BANK_NAMES, QUEBEC_CITIES, PROVINCES, CITIES_BY_PROVINCE,
    generate_postal_code, generate_phone, generate_email, generate_account_number,
)

fake = Faker("en_CA")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_entities(doc_text: str, entities: list[dict], filename: str):
    """Assert every entity's offsets match the document text."""
    for e in entities:
        actual = doc_text[e["start_char"]:e["end_char"]]
        assert actual == e["text"], (
            f"Offset mismatch in {filename}: expected {e['text']!r} "
            f"at [{e['start_char']}:{e['end_char']}], got {actual!r}"
        )


def _en_person():
    """Generate an English person name."""
    return fake.first_name(), fake.last_name()


def _fr_person():
    """Generate a French person name from pools."""
    return random.choice(FRENCH_FIRST_NAMES), random.choice(FRENCH_LAST_NAMES)


def _add_entity(entities, doc_text, entity_type, value):
    """Record entity at current end of doc_text, return doc_text + value."""
    start = len(doc_text)
    doc_text += value
    end = len(doc_text)
    entities.append({
        "entity_type": entity_type,
        "text": value,
        "start_char": start,
        "end_char": end,
    })
    return doc_text


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def generate_wire_en(seq: int) -> tuple[str, list[dict]]:
    """Generate one English wire transfer doc + entity list."""
    entities = []
    sender_first, sender_last = _en_person()
    sender_name = f"{sender_first} {sender_last}"
    recip_first, recip_last = _en_person()
    recip_name = f"{recip_first} {recip_last}"
    approver_first, approver_last = _en_person()
    approver_name = f"{approver_first} {approver_last}"

    sender_acct = generate_account_number()
    recip_acct = generate_account_number()
    sin = generate_valid_sin()
    email = generate_email(approver_first, approver_last)
    phone = generate_phone()
    postal = generate_postal_code()
    amount = f"{random.uniform(1000, 500000):,.2f}"
    bank = random.choice(BANK_NAMES)
    province = random.choice(PROVINCES)
    city = random.choice(CITIES_BY_PROVINCE[province])
    date1 = fake.date_between(start_date="-1y", end_date="today").strftime("%Y-%m-%d")
    date2 = fake.date_between(start_date="-1y", end_date="today").strftime("%Y-%m-%d")
    ref = f"WT-{random.randint(100000, 999999)}"
    purpose = random.choice(["Vendor Payment", "Payroll", "Investment Transfer", "Loan Repayment"])

    doc = ""
    doc += "WIRE TRANSFER AUTHORIZATION FORM\n"
    doc += "=================================\n\n"
    doc += f"Date: {date1}\n"
    doc += f"Reference: {ref}\n\n"
    doc += "SENDER INFORMATION\n"
    doc += "Name: "
    doc = _add_entity(entities, doc, "PERSON", sender_name)
    doc += "\nAccount Number: "
    doc = _add_entity(entities, doc, "ACCOUNT", sender_acct)
    doc += f"\nBranch: {city}, {province}\n\n"
    doc += "RECIPIENT INFORMATION\n"
    doc += "Name: "
    doc = _add_entity(entities, doc, "PERSON", recip_name)
    doc += "\nAccount Number: "
    doc = _add_entity(entities, doc, "ACCOUNT", recip_acct)
    doc += f"\nInstitution: {bank}\n\n"
    doc += "TRANSFER DETAILS\n"
    doc += "Amount: $"
    doc = _add_entity(entities, doc, "AMOUNT", amount)
    doc += " CAD\n"
    doc += f"Purpose: {purpose}\n\n"
    doc += "AUTHORIZATION\n"
    doc += "Approved by: "
    doc = _add_entity(entities, doc, "PERSON", approver_name)
    doc += "\nSIN (for verification): "
    doc = _add_entity(entities, doc, "SIN", sin)
    doc += "\nEmail: "
    doc = _add_entity(entities, doc, "EMAIL", email)
    doc += "\nPhone: "
    doc = _add_entity(entities, doc, "PHONE", phone)
    doc += "\nPostal Code: "
    doc = _add_entity(entities, doc, "POSTAL_CODE", postal)
    doc += "\n\nSignature: ____________________\n"
    doc += f"Date: {date2}\n"

    return doc, entities


def generate_screenshot_en(seq: int) -> tuple[str, list[dict]]:
    """Generate one English screenshot transcription doc + entity list."""
    entities = []
    first, last = _en_person()
    name = f"{first} {last}"
    acct = generate_account_number()
    email = generate_email(first, last)
    acct_type = random.choice(["Chequing", "Savings", "Business"])
    balance = random.uniform(5000, 200000)
    last_login = fake.date_time_between(start_date="-30d", end_date="now").strftime("%Y-%m-%d %H:%M:%S")

    doc = ""
    doc += "=== ACCOUNT SUMMARY ===\n"
    doc += "Client Name: "
    doc = _add_entity(entities, doc, "PERSON", name)
    doc += "\nAccount: "
    doc = _add_entity(entities, doc, "ACCOUNT", acct)
    doc += f"\nType: {acct_type}\n"
    doc += f"Balance: ${balance:,.2f} CAD\n"
    doc += f"Last Login: {last_login}\n"
    doc += "Email on file: "
    doc = _add_entity(entities, doc, "EMAIL", email)
    doc += "\n\nRECENT TRANSACTIONS\n"
    doc += "Date        Description              Amount      Balance\n"

    running = balance
    for _ in range(5):
        txn_date = fake.date_between(start_date="-30d", end_date="today").strftime("%Y-%m-%d")
        desc = random.choice([
            "Wire transfer", "Direct deposit", "Bill payment",
            "ATM withdrawal", "POS purchase", "E-transfer",
        ])
        amt = random.uniform(50, 10000)
        if random.random() < 0.5:
            running -= amt
            amt_str = f"-${amt:,.2f}"
        else:
            running += amt
            amt_str = f"${amt:,.2f}"
        doc += f"{txn_date}  {desc:<24} {amt_str:<12} ${running:,.2f}\n"

    return doc, entities


def generate_excel_en(seq: int) -> tuple[str, list[dict]]:
    """Generate one English Excel export transcription doc + entity list."""
    entities = []
    first, last = _en_person()
    holder_name = f"{first} {last}"
    acct = generate_account_number()
    gen_date = fake.date_between(start_date="-30d", end_date="today").strftime("%Y-%m-%d")

    # Pool of 5-8 authorizer names for this doc
    num_authorizers = random.randint(5, 8)
    authorizer_names = [f"{fake.first_name()} {fake.last_name()}" for _ in range(num_authorizers)]

    doc = ""
    doc += f"TRANSACTION EXPORT - Generated {gen_date}\n"
    doc += "Account Holder: "
    doc = _add_entity(entities, doc, "PERSON", holder_name)
    doc += "\nAccount Number: "
    doc = _add_entity(entities, doc, "ACCOUNT", acct)
    doc += "\n\n"
    doc += "Date\tDescription\tAuthorized By\tDebit\tCredit\tBalance\tReference\n"

    running = random.uniform(10000, 100000)
    authorizer_offsets_added = set()

    for i in range(50):
        txn_date = fake.date_between(start_date="-365d", end_date="today").strftime("%Y-%m-%d")
        desc = random.choice([
            "Wire transfer", "Direct deposit", "Bill payment",
            "Vendor payment", "Payroll", "E-transfer", "Service fee",
        ])
        auth = random.choice(authorizer_names)
        ref = f"TXN-{random.randint(100000, 999999)}"

        if random.random() < 0.5:
            debit = random.uniform(100, 50000)
            credit = ""
            running -= debit
            debit_str = f"{debit:,.2f}"
        else:
            debit = ""
            credit = random.uniform(100, 50000)
            running += credit
            debit_str = ""
            credit_str = f"{credit:,.2f}" if credit else ""

        if debit:
            credit_str = ""
        else:
            debit_str = ""
            credit_str = f"{credit:,.2f}"

        doc += f"{txn_date}\t{desc}\t"
        # Track PERSON entities for authorizers
        doc = _add_entity(entities, doc, "PERSON", auth)
        doc += f"\t{debit_str}\t{credit_str}\t{running:,.2f}\t{ref}\n"

    return doc, entities


def generate_procedure_en(seq: int) -> tuple[str, list[dict]]:
    """Generate one negative-control procedure doc (no PII)."""
    entities = []
    procedures = [
        "Wire Transfer Approval", "Account Opening Verification",
        "Anti-Money Laundering Review", "Customer Due Diligence",
        "Transaction Monitoring", "Fraud Detection Protocol",
        "Regulatory Compliance Check", "Internal Audit Process",
        "Risk Assessment Framework", "Data Retention Policy",
    ]
    departments = [
        "Compliance", "Risk Management", "Internal Audit",
        "Operations", "Treasury", "Legal",
    ]
    proc_name = random.choice(procedures)
    dept = random.choice(departments)
    version = f"{random.randint(1, 5)}.{random.randint(0, 9)}"
    eff_date = fake.date_between(start_date="-2y", end_date="today").strftime("%Y-%m-%d")

    doc = ""
    doc += f"PROCEDURE: {proc_name}\n"
    doc += f"Version: {version}\n"
    doc += f"Effective Date: {eff_date}\n"
    doc += f"Department: {dept}\n\n"
    doc += "1. PURPOSE\n"
    doc += f"This procedure establishes the process for {proc_name.lower()} "
    doc += f"within the {dept} department. It defines the roles, responsibilities, "
    doc += "and steps required to ensure compliance with applicable regulations "
    doc += "and internal policies.\n\n"
    doc += "2. SCOPE\n"
    doc += f"This procedure applies to all employees in the {dept} department "
    doc += "and any supporting staff involved in the execution of these processes. "
    doc += "All personnel must be trained on this procedure prior to performing "
    doc += "any related activities.\n\n"
    doc += "3. RESPONSIBILITIES\n"
    doc += "The Compliance Officer is responsible for ensuring that all activities "
    doc += "under this procedure are conducted in accordance with regulatory requirements. "
    doc += "The Branch Manager must ensure that staff are adequately trained and that "
    doc += "all documentation is maintained for the required retention period.\n\n"
    doc += "4. PROCEDURE STEPS\n"
    doc += "4.1 The authorized reviewer shall examine all submitted documentation "
    doc += "for completeness and accuracy before proceeding to the next step.\n"
    doc += "4.2 All exceptions must be documented in the exception log and reported "
    doc += "to the department head within 24 hours of identification.\n"
    doc += "4.3 The reviewer shall verify that all required approvals have been "
    doc += "obtained before finalizing any transaction or process change.\n"
    doc += "4.4 Upon completion of the review, the reviewer shall sign off on "
    doc += "the documentation and forward it to the records management team.\n\n"
    doc += "5. REVIEW AND UPDATES\n"
    doc += "This procedure shall be reviewed annually by the department head "
    doc += "and updated as necessary to reflect changes in regulations, policies, "
    doc += "or operational requirements. All revisions must be approved by the "
    doc += "Chief Compliance Officer before publication.\n\n"
    doc += "6. REFERENCES\n"
    doc += "- Corporate Governance Framework\n"
    doc += "- Regulatory Compliance Manual\n"
    doc += "- Internal Audit Standards\n"
    doc += "- Records Retention Schedule\n"

    return doc, entities


def generate_wire_fr(seq: int) -> tuple[str, list[dict]]:
    """Generate one French wire transfer doc + entity list."""
    entities = []
    sender_first, sender_last = _fr_person()
    sender_name = f"{sender_first} {sender_last}"
    recip_first, recip_last = _fr_person()
    recip_name = f"{recip_first} {recip_last}"
    approver_first, approver_last = _fr_person()
    approver_name = f"{approver_first} {approver_last}"

    sender_acct = generate_account_number()
    recip_acct = generate_account_number()
    sin = generate_valid_sin()
    email = generate_email(approver_first, approver_last)
    phone = generate_phone()
    postal = generate_postal_code()
    amount = f"{random.uniform(1000, 500000):,.2f}"
    bank = random.choice(BANK_NAMES)
    city = random.choice(QUEBEC_CITIES)
    date1 = fake.date_between(start_date="-1y", end_date="today").strftime("%Y-%m-%d")
    date2 = fake.date_between(start_date="-1y", end_date="today").strftime("%Y-%m-%d")
    ref = f"VIR-{random.randint(100000, 999999)}"
    purpose = random.choice(["Paiement fournisseur", "Paie", "Transfert d'investissement"])

    doc = ""
    doc += "FORMULAIRE D'AUTORISATION DE VIREMENT\n"
    doc += "======================================\n\n"
    doc += f"Date : {date1}\n"
    doc += f"Reference : {ref}\n\n"
    doc += "INFORMATIONS DE L'EXPEDITEUR\n"
    doc += "Nom : "
    doc = _add_entity(entities, doc, "PERSON", sender_name)
    doc += "\nNumero de compte : "
    doc = _add_entity(entities, doc, "ACCOUNT", sender_acct)
    doc += f"\nSuccursale : {city}\n\n"
    doc += "INFORMATIONS DU DESTINATAIRE\n"
    doc += "Nom : "
    doc = _add_entity(entities, doc, "PERSON", recip_name)
    doc += "\nNumero de compte : "
    doc = _add_entity(entities, doc, "ACCOUNT", recip_acct)
    doc += f"\nInstitution : {bank}\n\n"
    doc += "DETAILS DU VIREMENT\n"
    doc += "Montant : "
    doc = _add_entity(entities, doc, "AMOUNT", amount)
    doc += " $ CAD\n"
    doc += f"Objet : {purpose}\n\n"
    doc += "AUTORISATION\n"
    doc += "Approuve par : "
    doc = _add_entity(entities, doc, "PERSON", approver_name)
    doc += "\nNAS (pour verification) : "
    doc = _add_entity(entities, doc, "SIN", sin)
    doc += "\nCourriel : "
    doc = _add_entity(entities, doc, "EMAIL", email)
    doc += "\nTelephone : "
    doc = _add_entity(entities, doc, "PHONE", phone)
    doc += "\nCode postal : "
    doc = _add_entity(entities, doc, "POSTAL_CODE", postal)
    doc += "\n\nSignature : ____________________\n"
    doc += f"Date : {date2}\n"

    return doc, entities


def generate_edge_en(seq: int) -> tuple[str, list[dict]]:
    """Generate one edge-case doc. Type based on seq: 1-10=spaces, 11-20=dashes, 21-30=brackets+typo."""
    entities = []
    first, last = _en_person()
    sin = generate_valid_sin()
    acct = generate_account_number()

    if seq <= 10:
        # Type A — SIN with spaces
        name = f"{first} {last}"
        sin_formatted = f"{sin[0:3]} {sin[3:6]} {sin[6:9]}"
        doc = ""
        doc += "Employee Verification Record\n"
        doc += "Name: "
        doc = _add_entity(entities, doc, "PERSON", name)
        doc += "\nSocial Insurance Number: "
        doc = _add_entity(entities, doc, "SIN", sin_formatted)
        doc += "\nAccount: "
        doc = _add_entity(entities, doc, "ACCOUNT", acct)
        doc += "\n"

    elif seq <= 20:
        # Type B — SIN with dashes
        name = f"{first} {last}"
        sin_formatted = f"{sin[0:3]}-{sin[3:6]}-{sin[6:9]}"
        email = generate_email(first, last)
        doc = ""
        doc += "Payroll Authorization\n"
        doc += "Employee: "
        doc = _add_entity(entities, doc, "PERSON", name)
        doc += "\nSIN: "
        doc = _add_entity(entities, doc, "SIN", sin_formatted)
        doc += "\nContact: "
        doc = _add_entity(entities, doc, "EMAIL", email)
        doc += "\n"

    else:
        # Type C — Account in brackets, name with typo
        # Duplicate one letter in first name
        if len(first) >= 2:
            idx = random.randint(0, len(first) - 1)
            typo_first = first[:idx] + first[idx] + first[idx:]
        else:
            typo_first = first + first
        name = f"{typo_first} {last}"
        amount = f"{random.uniform(1000, 100000):,.2f}"
        ref = f"WT-{random.randint(100000, 999999)}"

        doc = ""
        doc += "Transfer Record\n"
        doc += "Client: "
        doc = _add_entity(entities, doc, "PERSON", name)
        doc += "\nAccount: ["
        doc = _add_entity(entities, doc, "ACCOUNT", acct)
        doc += "]\n"
        doc += f"Wire Ref: {ref}\n"
        doc += "Amount: $"
        doc = _add_entity(entities, doc, "AMOUNT", amount)
        doc += "\n"

    return doc, entities


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    random.seed(42)
    Faker.seed(42)

    output_dir = pathlib.Path(__file__).resolve().parent.parent.parent.parent / "eval" / "redaction-corpus"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_docs = []  # (doc_id, language, category, entities)

    generators = [
        ("wire", "en", 50, generate_wire_en),
        ("screenshot", "en", 30, generate_screenshot_en),
        ("excel", "en", 30, generate_excel_en),
        ("procedure", "en", 30, generate_procedure_en),
        ("wire", "fr", 30, generate_wire_fr),
        ("edge", "en", 30, generate_edge_en),
    ]

    for category, language, count, gen_func in generators:
        for seq in range(1, count + 1):
            doc_id = f"{category}_{language}_{seq:03d}"
            filename = f"{doc_id}.txt"

            doc_text, entities = gen_func(seq)

            # Verify offset integrity
            _verify_entities(doc_text, entities, filename)

            # Write document
            (output_dir / filename).write_text(doc_text, encoding="utf-8")

            all_docs.append((doc_id, language, category, entities))

    # Write answers.json
    answers = {}
    for doc_id, language, category, entities in all_docs:
        answers[doc_id] = {
            "language": language,
            "category": category,
            "entities": entities,
        }

    with open(output_dir / "answers.json", "w", encoding="utf-8") as f:
        json.dump(answers, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"Generated {len(all_docs)} documents in {output_dir}")
    entity_counts = {}
    category_counts = {}
    for doc_id, language, category, entities in all_docs:
        cat_key = f"{category}_{language}"
        category_counts[cat_key] = category_counts.get(cat_key, 0) + 1
        for e in entities:
            entity_counts[e["entity_type"]] = entity_counts.get(e["entity_type"], 0) + 1

    print("\nDocuments by category:")
    for cat, count in sorted(category_counts.items()):
        print(f"  {cat}: {count}")

    print("\nEntities by type:")
    total = 0
    for etype, count in sorted(entity_counts.items()):
        print(f"  {etype}: {count}")
        total += count
    print(f"  TOTAL: {total}")


if __name__ == "__main__":
    main()
