"""
Configuration constants: spreadsheet IDs and sheet names for all tables
used in BDNS (DSIN) student database management.

Fill in the actual spreadsheet IDs before running any scripts.
"""

# ---------------------------------------------------------------------------
# Spreadsheet IDs
# Set each value to the ID found in the corresponding Google Sheets URL:
#   https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
# ---------------------------------------------------------------------------
SPREADSHEET_IDS: dict[str, str] = {
    # Main student database (state-funded and contract students)
    "cmc_database": "",
    # Dismissed students archive
    "dismissed_students": "",
    # Table auto-created by the Google Form response (BDNS admission data)
    "response_form": "",
    # Public student status / admission status table
    "student_status": "",
    # OPK student database
    "opk_database": "",
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
DOCS_FOLDER_ID: str = ""
