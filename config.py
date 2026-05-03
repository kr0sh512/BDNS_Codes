"""
Configuration constants: spreadsheet IDs and sheet names for all tables
used in BDNS (DSIN) student database management.

All spreadsheet IDs and the documents folder ID are loaded from environment
variables (see ``.env.example`` for the full list).  Create a ``.env`` file
in the project root (it is git-ignored) and fill in the real values there.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Spreadsheet IDs — loaded from environment variables
# ---------------------------------------------------------------------------
SPREADSHEET_IDS: dict[str, str] = {
    # Main student database (state-funded and contract students)
    "cmc_database": os.getenv("SPREADSHEET_ID_CMC_DATABASE", ""),
    # Dismissed students archive
    "dismissed_students": os.getenv("SPREADSHEET_ID_DISMISSED_STUDENTS", ""),
    # Table auto-created by the Google Form response (BDNS admission data)
    "response_form": os.getenv("SPREADSHEET_ID_RESPONSE_FORM", ""),
    # Public student status / admission status table
    "student_status": os.getenv("SPREADSHEET_ID_STUDENT_STATUS", ""),
    # OPK student database
    "opk_database": os.getenv("SPREADSHEET_ID_OPK_DATABASE", ""),
}

# ---------------------------------------------------------------------------
# Sheet (tab) names inside the CMC Database spreadsheet
# ---------------------------------------------------------------------------
CMC_SHEETS: dict[str, str] = {
    "state": "Бюджет",      # State-funded students
    "contract": "Контракт", # Contract students
}

# ---------------------------------------------------------------------------
# Google Drive folder ID where generated documents are stored
# ---------------------------------------------------------------------------
DOCS_FOLDER_ID: str = os.getenv("DOCS_FOLDER_ID", "")
