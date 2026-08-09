"""Constants shared across the app. No I/O at import time."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDS_YAML_PATH = REPO_ROOT / "data" / "feeds.yaml"

SECTIONS = ("tech", "finance", "world_india")
FROZEN_FEED_COUNT = 35

# ARCHITECTURE.md §6 - the one honest User-Agent every outbound fetch uses.
USER_AGENT = (
    "Aakasavani/1.0 (personal news reader; +mailto:deepugudapati123@gmail.com)"
)

# ARCHITECTURE.md §6 - budget caps for the research panel. Enforced in
# app/research/budget.py (step 14), not here - this is just the constant.
MONTHLY_USD_CAP = 25.00
DAILY_USD_CAP = 2.00
SINGLE_CALL_CAP = 0.10

# Extraction failure floor - ARCHITECTURE.md §2.4.
MIN_EXTRACTION_CHARS = 500
