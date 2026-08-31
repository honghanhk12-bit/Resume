"""Central configuration for the job hunt orchestration system.

Fill in the API keys below (or, preferably, set them as environment
variables of the same name and leave the defaults here empty) before
running main.py.
"""

import os

# --- API credentials -------------------------------------------------------
# Prefer environment variables in real deployments; the os.getenv fallback
# lets you drop a key here directly for local/one-off use.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")  # get a free key at serper.dev

# --- Target role config -----------------------------------------------------
TARGET_ROLE = "Head of Data"
TARGET_LOCATION = "London"
TARGET_INDUSTRY = "Real Estate"

# --- File paths --------------------------------------------------------------
RESUME_PATH = "data/resume.pdf"
DATA_DIR = "data"
OUTPUTS_DIR = "outputs"

# --- Model / pipeline settings ------------------------------------------------
MODEL = "claude-3-5-sonnet-20241022"
MAX_LISTINGS_TO_FETCH = 5
MIN_ATS_SCORE = 80
MAX_SURGEON_RETRIES = 2

# --- Retry / backoff settings for API calls -----------------------------------
MAX_API_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2.0
BACKOFF_MULTIPLIER = 2.0

# --- Misc ----------------------------------------------------------------------
MAX_TOKENS = 4096
REQUEST_TIMEOUT_SECONDS = 120
