import json
import hashlib
from pathlib import Path
from datetime import datetime


def save_user_template(
    headers: list[str],
    column_mapping: dict[int, str],
) -> str:
    user_dir = Path(__file__).parents[3] / "config" / "bank_templates" / "user_learned"
    user_dir.mkdir(parents=True, exist_ok=True)

    header_concat = "|".join(headers)
    template_id = "user_" + hashlib.md5(header_concat.encode()).hexdigest()[:12]

    template = {
        "template_id": template_id,
        "description": f"User-learned template from {datetime.now().strftime('%Y-%m-%d')}",
        "match_headers": headers,
        "match_threshold": 0.85,
        "column_map": {headers[idx]: field for idx, field in column_mapping.items() if idx < len(headers)},
        "date_format": "%d/%m/%y",
        "decimal_style": "comma_thousands",
        "is_fallback": False,
        "created": datetime.now().isoformat(),
    }

    path = user_dir / f"{template_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(template, f, indent=2)

    return template_id
