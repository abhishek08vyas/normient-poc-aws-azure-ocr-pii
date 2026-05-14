import json
from dataclasses import asdict
from datetime import datetime, date


def to_serializable(obj):
    """Recursively convert SDK response objects to JSON-serializable dicts."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return "<bytes>"
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_serializable(item) for item in obj]
    # Azure SDK objects have __dict__ or as_dict()
    if hasattr(obj, "as_dict"):
        return to_serializable(obj.as_dict())
    if hasattr(obj, "__dict__"):
        return to_serializable(vars(obj))
    return str(obj)


def sanitize_response(response_dict: dict) -> dict:
    """Remove any keys that may contain credentials or secrets."""
    SENSITIVE_KEYS = {"authorization", "key", "token", "secret", "credential",
                      "x-amz-security-token", "ocp-apim-subscription-key",
                      "aws_access_key_id", "aws_secret_access_key"}
    if not isinstance(response_dict, dict):
        return response_dict
    result = {}
    for k, v in response_dict.items():
        if k.lower() in SENSITIVE_KEYS or any(s in k.lower() for s in SENSITIVE_KEYS):
            result[k] = "<REDACTED>"
        elif isinstance(v, dict):
            result[k] = sanitize_response(v)
        elif isinstance(v, list):
            result[k] = [sanitize_response(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def save_result(result_dataclass, filepath: str):
    """Serialize a dataclass result to JSON file."""
    d = asdict(result_dataclass)
    d["raw_response"] = sanitize_response(d.get("raw_response", {}))
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False, default=str)
