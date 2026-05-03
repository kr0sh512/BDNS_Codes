"""Tests for sheets_client.SheetsClient."""

from unittest.mock import MagicMock, call

import pytest

from sheets_client import SheetsClient


# ---------------------------------------------------------------------------
# Helpers to build mock service chains
# ---------------------------------------------------------------------------

def _make_service(return_value):
    """Return a mock service whose deepest .execute() returns *return_value*."""
    service = MagicMock()
    # Every intermediate call returns a new mock that ultimately returns
    # a mock whose .execute() returns our value.
    execute_mock = MagicMock(return_value=return_value)
    terminal = MagicMock()
    terminal.execute = execute_mock
    # Make every chained attribute / call return `terminal`
    service.spreadsheets.return_value = MagicMock()
    return service, terminal


# ---------------------------------------------------------------------------
# get_spreadsheet / get_sheet_names / get_sheet_id
# ---------------------------------------------------------------------------

class TestMetadata:
    def _service_with_spreadsheet_meta(self, sheets_meta):
        svc = MagicMock()
        svc.spreadsheets.return_value.get.return_value.execute.return_value = {
            "sheets": sheets_meta
        }
        return svc

    def test_get_sheet_names(self):
        meta = [
            {"properties": {"title": "Бюджет", "sheetId": 0}},
            {"properties": {"title": "Контракт", "sheetId": 1}},
        ]
        svc = self._service_with_spreadsheet_meta(meta)
        client = SheetsClient(svc)
        assert client.get_sheet_names("fake_id") == ["Бюджет", "Контракт"]

    def test_get_sheet_id_found(self):
        meta = [
            {"properties": {"title": "Бюджет", "sheetId": 42}},
        ]
        svc = self._service_with_spreadsheet_meta(meta)
        client = SheetsClient(svc)
        assert client.get_sheet_id("fake_id", "Бюджет") == 42

    def test_get_sheet_id_not_found(self):
        meta = [{"properties": {"title": "Бюджет", "sheetId": 0}}]
        svc = self._service_with_spreadsheet_meta(meta)
        client = SheetsClient(svc)
        with pytest.raises(ValueError, match="Sheet 'Missing' not found"):
            client.get_sheet_id("fake_id", "Missing")


# ---------------------------------------------------------------------------
# read_values / read_as_dicts
# ---------------------------------------------------------------------------

class TestReading:
    def _service_with_values(self, values):
        svc = MagicMock()
        svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = (
            {"values": values} if values else {}
        )
        return svc

    def test_read_values_returns_list(self):
        data = [["A", "B"], ["1", "2"]]
        svc = self._service_with_values(data)
        client = SheetsClient(svc)
        assert client.read_values("sid", "Sheet1") == data

    def test_read_values_empty_sheet(self):
        svc = self._service_with_values(None)
        client = SheetsClient(svc)
        assert client.read_values("sid", "Sheet1") == []

    def test_read_as_dicts_basic(self):
        data = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
        svc = self._service_with_values(data)
        client = SheetsClient(svc)
        result = client.read_as_dicts("sid", "Sheet1")
        assert result == [
            {"Name": "Alice", "Age": "30"},
            {"Name": "Bob", "Age": "25"},
        ]

    def test_read_as_dicts_pads_short_rows(self):
        data = [["Name", "Age", "City"], ["Alice"]]
        svc = self._service_with_values(data)
        client = SheetsClient(svc)
        result = client.read_as_dicts("sid", "Sheet1")
        assert result == [{"Name": "Alice", "Age": "", "City": ""}]

    def test_read_as_dicts_empty_sheet(self):
        svc = self._service_with_values(None)
        client = SheetsClient(svc)
        assert client.read_as_dicts("sid", "Sheet1") == []

    def test_read_as_dicts_header_only(self):
        data = [["Name", "Age"]]
        svc = self._service_with_values(data)
        client = SheetsClient(svc)
        assert client.read_as_dicts("sid", "Sheet1") == []


# ---------------------------------------------------------------------------
# write_values / append_rows / clear_range / delete_rows
# ---------------------------------------------------------------------------

class TestWriting:
    def test_write_values_calls_api(self):
        svc = MagicMock()
        update_mock = svc.spreadsheets.return_value.values.return_value.update
        update_mock.return_value.execute.return_value = {}
        client = SheetsClient(svc)
        client.write_values("sid", "Sheet1", [["H1", "H2"], ["a", "b"]])
        update_mock.assert_called_once()
        kwargs = update_mock.call_args.kwargs
        assert kwargs["spreadsheetId"] == "sid"
        assert kwargs["range"] == "Sheet1"
        assert kwargs["body"] == {"values": [["H1", "H2"], ["a", "b"]]}

    def test_append_rows_calls_api(self):
        svc = MagicMock()
        append_mock = svc.spreadsheets.return_value.values.return_value.append
        append_mock.return_value.execute.return_value = {}
        client = SheetsClient(svc)
        client.append_rows("sid", "Sheet1", [["x", "y"]])
        append_mock.assert_called_once()
        kwargs = append_mock.call_args.kwargs
        assert kwargs["spreadsheetId"] == "sid"
        assert kwargs["body"] == {"values": [["x", "y"]]}

    def test_clear_range_calls_api(self):
        svc = MagicMock()
        clear_mock = svc.spreadsheets.return_value.values.return_value.clear
        clear_mock.return_value.execute.return_value = {}
        client = SheetsClient(svc)
        client.clear_range("sid", "Sheet1!A1:Z100")
        clear_mock.assert_called_once()

    def test_delete_rows_calls_api(self):
        svc = MagicMock()
        batch_mock = svc.spreadsheets.return_value.batchUpdate
        batch_mock.return_value.execute.return_value = {}
        client = SheetsClient(svc)
        client.delete_rows("sid", sheet_id=0, start_index=2, end_index=3)
        batch_mock.assert_called_once()
        body = batch_mock.call_args.kwargs["body"]
        dim_range = body["requests"][0]["deleteDimension"]["range"]
        assert dim_range["sheetId"] == 0
        assert dim_range["startIndex"] == 2
        assert dim_range["endIndex"] == 3


# ---------------------------------------------------------------------------
# add_sheet
# ---------------------------------------------------------------------------

class TestAddSheet:
    def test_add_sheet_calls_api(self):
        svc = MagicMock()
        batch_mock = svc.spreadsheets.return_value.batchUpdate
        batch_mock.return_value.execute.return_value = {
            "replies": [{"addSheet": {"properties": {"title": "New", "sheetId": 99}}}]
        }
        client = SheetsClient(svc)
        reply = client.add_sheet("sid", "New")
        assert reply["properties"]["title"] == "New"
        body = batch_mock.call_args.kwargs["body"]
        assert body["requests"][0]["addSheet"]["properties"]["title"] == "New"
