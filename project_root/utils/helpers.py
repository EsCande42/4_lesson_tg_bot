import json
from typing import Dict, Any

def export_settings(settings: Dict[str, Any]) -> str:
    """Export settings to JSON string"""
    return json.dumps(settings, indent=2)

def import_settings(settings_json: str) -> Dict[str, Any]:
    """Import settings from JSON string"""
    try:
        return json.loads(settings_json)
    except json.JSONDecodeError:
        raise ValueError("Invalid settings JSON format")

def validate_url(url: str) -> bool:
    """Validate URL format"""
    from urllib.parse import urlparse
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def validate_model_name(model: str) -> bool:
    """Validate model name format"""
    return bool(model and isinstance(model, str) and len(model.strip()) > 0)

def validate_temperature(temp: float) -> bool:
    """Validate temperature value"""
    return isinstance(temp, (int, float)) and 0 <= temp <= 1

def validate_max_tokens(tokens: int) -> bool:
    """Validate max tokens value"""
    return isinstance(tokens, int) and tokens >= 150 