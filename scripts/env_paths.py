"""Shared paths & env — no hardcoded usernames."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DECODER_ROOT = Path(
    os.path.expanduser(
        os.environ.get(
            "SOCIAL_ECOM_DECODER",
            "~/.claude/skills/social-ecom-decoder",
        )
    )
)
REPORT_AUTHORS = os.environ.get("REPORT_AUTHORS", "Your Team")
HTML_OUTPUT = PROJECT_ROOT / os.environ.get("REPORT_HTML", "monthly-report.html")
