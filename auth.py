"""
Authentication helpers for Google Sheets, Docs, and Drive APIs.

All services use a service account whose key is stored in ``credentials.json``
(never commit that file to version control).
"""

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

DEFAULT_CREDENTIALS_FILE = "credentials.json"

# Scopes required by the application
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]


def get_credentials(credentials_file: str = DEFAULT_CREDENTIALS_FILE) -> Credentials:
    """Load service-account credentials from *credentials_file*.

    Parameters
    ----------
    credentials_file:
        Path to the service-account JSON key file (default: ``credentials.json``).

    Returns
    -------
    google.oauth2.service_account.Credentials
        Scoped credentials ready to be passed to :func:`build_*_service` helpers.
    """
    return Credentials.from_service_account_file(credentials_file, scopes=SCOPES)


def build_sheets_service(credentials_file: str = DEFAULT_CREDENTIALS_FILE):
    """Return an authenticated Google Sheets API service (v4)."""
    creds = get_credentials(credentials_file)
    return build("sheets", "v4", credentials=creds)


def build_docs_service(credentials_file: str = DEFAULT_CREDENTIALS_FILE):
    """Return an authenticated Google Docs API service (v1)."""
    creds = get_credentials(credentials_file)
    return build("docs", "v1", credentials=creds)


def build_drive_service(credentials_file: str = DEFAULT_CREDENTIALS_FILE):
    """Return an authenticated Google Drive API service (v3)."""
    creds = get_credentials(credentials_file)
    return build("drive", "v3", credentials=creds)
