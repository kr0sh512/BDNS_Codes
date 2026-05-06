"""
Universal Google Sheets client.

``SheetsClient`` wraps the raw Google Sheets API service and provides
high-level helpers for reading, writing, and manipulating spreadsheet data.
"""

from __future__ import annotations

from typing import Any


class SheetsClient:
    """High-level wrapper around the Google Sheets API v4 service.

    Parameters
    ----------
    service:
        An authenticated ``googleapiclient`` resource object for the Sheets API,
        typically obtained via :func:`auth.build_sheets_service`.
    """

    def __init__(self, service) -> None:
        self._service = service

    # ------------------------------------------------------------------
    # Spreadsheet / sheet metadata
    # ------------------------------------------------------------------

    def get_spreadsheet(self, spreadsheet_id: str) -> dict:
        """Return full spreadsheet metadata (title, sheets, etc.)."""
        return (
            self._service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id)
            .execute()
        )

    def get_sheet_names(self, spreadsheet_id: str) -> list[str]:
        """Return a list of sheet (tab) names in the given spreadsheet."""
        meta = self.get_spreadsheet(spreadsheet_id)
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    def get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> int:
        """Return the numeric *sheetId* for the sheet named *sheet_name*.

        Raises
        ------
        ValueError
            If no sheet with that name exists.
        """
        meta = self.get_spreadsheet(spreadsheet_id)
        for sheet in meta.get("sheets", []):
            props = sheet["properties"]
            if props["title"] == sheet_name:
                return props["sheetId"]
        raise ValueError(
            f"Sheet '{sheet_name}' not found in spreadsheet '{spreadsheet_id}'."
        )

    # ------------------------------------------------------------------
    # Reading data
    # ------------------------------------------------------------------

    def read_values(
        self, spreadsheet_id: str, range_name: str
    ) -> list[list[Any]]:
        """Read raw cell values from *range_name*.

        Returns a list of rows, where each row is a list of cell values.
        Trailing empty cells in a row are omitted by the API.

        Parameters
        ----------
        spreadsheet_id:
            The ID of the spreadsheet.
        range_name:
            A1-notation range, e.g. ``"Sheet1"`` or ``"Sheet1!A1:D10"``.
        """
        result = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [])

    def read_as_dicts(
        self, spreadsheet_id: str, sheet_name: str
    ) -> list[dict[str, Any]]:
        """Read a sheet and return its rows as a list of dicts.

        The first row of the sheet is treated as the header and used as
        dictionary keys.  Empty trailing cells within a row are filled
        with ``""`` to keep all dicts the same width as the header.

        Parameters
        ----------
        spreadsheet_id:
            The ID of the spreadsheet.
        sheet_name:
            The name of the sheet (tab) to read.
        """
        rows = self.read_values(spreadsheet_id, sheet_name)
        if not rows:
            return []
        header = rows[0]
        result: list[dict[str, Any]] = []
        for row in rows[1:]:
            # Pad row to header length so every key is present
            padded = row + [""] * (len(header) - len(row))
            result.append(dict(zip(header, padded)))
        return result

    # ------------------------------------------------------------------
    # Writing data
    # ------------------------------------------------------------------

    def write_values(
        self,
        spreadsheet_id: str,
        range_name: str,
        values: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Write *values* to *range_name*, overwriting existing content.

        Parameters
        ----------
        spreadsheet_id:
            The ID of the spreadsheet.
        range_name:
            A1-notation range where writing starts.
        values:
            List of rows (each row is a list of cell values).
        value_input_option:
            ``"RAW"`` (literal strings) or ``"USER_ENTERED"`` (parsed as
            if typed by a user, default).
        """
        body = {"values": values}
        return (
            self._service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body,
            )
            .execute()
        )

    def append_rows(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        rows: list[list[Any]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict:
        """Append *rows* after the last row with data in *sheet_name*.

        Parameters
        ----------
        spreadsheet_id:
            The ID of the spreadsheet.
        sheet_name:
            The name of the destination sheet.
        rows:
            List of rows to append.
        value_input_option:
            ``"RAW"`` or ``"USER_ENTERED"`` (default).
        """
        body = {"values": rows}
        return (
            self._service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=sheet_name,
                valueInputOption=value_input_option,
                insertDataOption="INSERT_ROWS",
                body=body,
            )
            .execute()
        )

    def clear_range(self, spreadsheet_id: str, range_name: str) -> dict:
        """Clear all values in *range_name* (formatting is preserved).

        Parameters
        ----------
        spreadsheet_id:
            The ID of the spreadsheet.
        range_name:
            A1-notation range to clear.
        """
        return (
            self._service.spreadsheets()
            .values()
            .clear(spreadsheetId=spreadsheet_id, range=range_name, body={})
            .execute()
        )

    def delete_rows(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        start_index: int,
        end_index: int,
    ) -> dict:
        """Delete rows [*start_index*, *end_index*) from the given sheet.

        Row indices are **0-based** (the header row is index 0).

        Parameters
        ----------
        spreadsheet_id:
            The ID of the spreadsheet.
        sheet_id:
            The numeric sheet ID (not the name).  Use
            :meth:`get_sheet_id` to look this up.
        start_index:
            First row to delete (inclusive, 0-based).
        end_index:
            Row after the last row to delete (exclusive, 0-based).
        """
        body = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": start_index,
                            "endIndex": end_index,
                        }
                    }
                }
            ]
        }
        return (
            self._service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            .execute()
        )

    # ------------------------------------------------------------------
    # Sheet management
    # ------------------------------------------------------------------

    def add_sheet(
        self, spreadsheet_id: str, sheet_name: str
    ) -> dict:
        """Add a new sheet (tab) named *sheet_name* to the spreadsheet.

        Returns the ``addSheet`` reply from the API which contains the
        new sheet's properties.

        Raises
        ------
        googleapiclient.errors.HttpError
            If a sheet with that name already exists.
        """
        body = {
            "requests": [
                {
                    "addSheet": {
                        "properties": {"title": sheet_name}
                    }
                }
            ]
        }
        response = (
            self._service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            .execute()
        )
        return response["replies"][0]["addSheet"]
