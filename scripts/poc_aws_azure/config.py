import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env.poc from the project root (two levels up from scripts/poc-aws-azure/)
ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env.poc"

REQUIRED_ENV_VARS = {
    "AWS_REGION": "e.g., ca-central-1",
    "AWS_ACCESS_KEY_ID": "your AWS access key",
    "AWS_SECRET_ACCESS_KEY": "your AWS secret key",
    "AWS_S3_BUCKET_POC": "e.g., normient-poc-spike-dev",
    "AZURE_DOC_INTEL_ENDPOINT": "e.g., https://my-resource.cognitiveservices.azure.com/",
    "AZURE_DOC_INTEL_KEY": "your Azure Document Intelligence API key",
    "AZURE_LANGUAGE_ENDPOINT": "e.g., https://my-resource.cognitiveservices.azure.com/",
    "AZURE_LANGUAGE_KEY": "your Azure Language API key",
}

# Paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OCR_CORPUS_DIR = PROJECT_ROOT / "eval" / "ocr-corpus" / "spike-seed"
PII_CORPUS_DIR = PROJECT_ROOT / "eval" / "redaction-corpus"
RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Pricing constants (captured May 2025 — use as-is)
TEXTRACT_COST_PER_PAGE = 0.065      # USD, AnalyzeDocument with TABLES+FORMS
DOC_INTEL_COST_PER_PAGE = 0.065     # USD, prebuilt-layout
COMPREHEND_COST_PER_UNIT = 0.0001   # USD, 1 unit = 100 chars, min 3 units
AZURE_LANG_COST_PER_1K_RECORDS = 1.00  # USD, 1 record = up to 1000 chars

# Content type map for Azure Document Intelligence
CONTENT_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


def load_config():
    """Load and validate all environment variables. Abort if any are missing."""
    if not ENV_FILE.exists():
        print(f"CRITICAL: .env.poc not found at {ENV_FILE}")
        print("Create it per the pre-flight checklist in POC-aws-vs-azure-ocr-pii.md")
        sys.exit(1)

    load_dotenv(ENV_FILE)

    missing = []
    for var, hint in REQUIRED_ENV_VARS.items():
        if not os.environ.get(var):
            missing.append(f"  {var} — {hint}")
    if missing:
        print("CRITICAL: Missing required environment variables in .env.poc:")
        print("\n".join(missing))
        sys.exit(1)


def init_aws_clients():
    """Initialize and return (textract_client, s3_client, comprehend_client)."""
    import boto3
    region = os.environ["AWS_REGION"]
    key_id = os.environ["AWS_ACCESS_KEY_ID"]
    secret = os.environ["AWS_SECRET_ACCESS_KEY"]
    kwargs = dict(region_name=region, aws_access_key_id=key_id, aws_secret_access_key=secret)
    return (
        boto3.client("textract", **kwargs),
        boto3.client("s3", **kwargs),
        boto3.client("comprehend", **kwargs),
    )


def init_azure_clients():
    """Initialize and return (doc_intel_client, text_analytics_client)."""
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.ai.textanalytics import TextAnalyticsClient
    from azure.core.credentials import AzureKeyCredential

    doc_intel = DocumentIntelligenceClient(
        endpoint=os.environ["AZURE_DOC_INTEL_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_DOC_INTEL_KEY"]),
    )
    text_analytics = TextAnalyticsClient(
        endpoint=os.environ["AZURE_LANGUAGE_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_LANGUAGE_KEY"]),
    )
    return doc_intel, text_analytics
