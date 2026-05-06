"""Tests for table_operations module."""

from unittest.mock import MagicMock, call

import pandas as pd
import pytest

from docs_client import DocsClient
from sheets_client import SheetsClient
import table_operations as to


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_SOURCE_ROWS = [
    {"Имя": "Alice", "Возраст": "20", "Группа": "101"},
    {"Имя": "Bob", "Возраст": "21", "Группа": "102"},
    {"Имя": "Carol", "Возраст": "22", "Группа": "101"},
]

SAMPLE_DF = pd.DataFrame(SAMPLE_SOURCE_ROWS)


def _make_sheets_client(source_rows=None, sheet_names=None, existing_dest=None):
    """Build a SheetsClient whose methods return controllable data."""
    client = MagicMock(spec=SheetsClient)
    client.read_as_dicts.return_value = source_rows or []
    client.get_sheet_names.return_value = sheet_names or []
    # By default, destination sheet is empty
    client.read_values.return_value = existing_dest if existing_dest is not None else []
    client.get_sheet_id.return_value = 0
    client.append_rows.return_value = {}
    client.write_values.return_value = {}
    client.clear_range.return_value = {}
    client.add_sheet.return_value = {}
    client.delete_rows.return_value = {}
    return client


def _make_docs_client():
    client = MagicMock(spec=DocsClient)
    client.copy_template.side_effect = lambda tid, title, folder_id=None: f"new_{title}"
    client.replace_text.return_value = {}
    return client


# ---------------------------------------------------------------------------
# transfer_rows
# ---------------------------------------------------------------------------

class TestTransferRows:
    def test_transfer_all_rows_no_map(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS)
        transferred = to.transfer_rows(
            sc, "src_id", "SrcSheet", "dst_id", "DstSheet"
        )
        assert isinstance(transferred, pd.DataFrame)
        assert len(transferred) == 3
        # Header should have been appended first (dest was empty)
        first_append = sc.append_rows.call_args_list[0]
        assert first_append == call(
            "dst_id", "DstSheet", [["Имя", "Возраст", "Группа"]]
        )

    def test_transfer_with_column_map(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS)
        col_map = {"Имя": "Name", "Группа": "Group"}
        transferred = to.transfer_rows(
            sc, "src_id", "SrcSheet", "dst_id", "DstSheet",
            column_map=col_map,
        )
        assert isinstance(transferred, pd.DataFrame)
        assert list(transferred.columns) == ["Name", "Group"]
        assert len(transferred) == 3
        # Check header written to dest
        first_append = sc.append_rows.call_args_list[0]
        assert first_append == call("dst_id", "DstSheet", [["Name", "Group"]])
        # Check data rows (only mapped columns)
        second_append = sc.append_rows.call_args_list[1]
        assert second_append == call(
            "dst_id", "DstSheet",
            [["Alice", "101"], ["Bob", "102"], ["Carol", "101"]],
        )

    def test_transfer_with_filter(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS)
        transferred = to.transfer_rows(
            sc, "src_id", "SrcSheet", "dst_id", "DstSheet",
            row_filter=lambda r: r["Группа"] == "101",
        )
        assert isinstance(transferred, pd.DataFrame)
        assert len(transferred) == 2
        assert transferred["Имя"].tolist() == ["Alice", "Carol"]

    def test_no_rows_transferred_when_filter_excludes_all(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS)
        transferred = to.transfer_rows(
            sc, "src_id", "SrcSheet", "dst_id", "DstSheet",
            row_filter=lambda r: False,
        )
        assert isinstance(transferred, pd.DataFrame)
        assert transferred.empty
        sc.append_rows.assert_not_called()

    def test_no_header_appended_when_dest_has_data(self):
        sc = _make_sheets_client(
            source_rows=SAMPLE_SOURCE_ROWS,
            existing_dest=[["Имя", "Возраст", "Группа"], ["X", "1", "A"]],
        )
        to.transfer_rows(sc, "src_id", "SrcSheet", "dst_id", "DstSheet")
        # Only one append call (the data rows), no header append
        assert sc.append_rows.call_count == 1
        data_append = sc.append_rows.call_args_list[0]
        assert data_append.args[2][0] == ["Alice", "20", "101"]

    def test_delete_from_source(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS)
        to.transfer_rows(
            sc, "src_id", "SrcSheet", "dst_id", "DstSheet",
            delete_from_source=True,
        )
        # Three rows → three delete_rows calls
        assert sc.delete_rows.call_count == 3

    def test_empty_source_returns_empty_dataframe(self):
        sc = _make_sheets_client(source_rows=[])
        result = to.transfer_rows(sc, "s", "S", "d", "D")
        assert isinstance(result, pd.DataFrame)
        assert result.empty


# ---------------------------------------------------------------------------
# build_auxiliary_table
# ---------------------------------------------------------------------------

class TestBuildAuxiliaryTable:
    def test_clears_existing_sheet(self):
        sc = _make_sheets_client(sheet_names=["Existing"])
        to.build_auxiliary_table(sc, "sid", "Existing", SAMPLE_DF)
        sc.clear_range.assert_called_once_with("sid", "Existing")
        sc.add_sheet.assert_not_called()

    def test_creates_new_sheet(self):
        sc = _make_sheets_client(sheet_names=["Other"])
        to.build_auxiliary_table(sc, "sid", "New", SAMPLE_DF)
        sc.add_sheet.assert_called_once_with("sid", "New")
        sc.clear_range.assert_not_called()

    def test_writes_header_and_data(self):
        sc = _make_sheets_client(sheet_names=[])
        to.build_auxiliary_table(sc, "sid", "Sheet", SAMPLE_DF.iloc[:2])
        sc.write_values.assert_called_once()
        written = sc.write_values.call_args.args[2]
        assert written[0] == ["Имя", "Возраст", "Группа"]  # header
        assert written[1] == ["Alice", "20", "101"]
        assert written[2] == ["Bob", "21", "102"]

    def test_writes_with_column_map(self):
        sc = _make_sheets_client(sheet_names=[])
        to.build_auxiliary_table(
            sc, "sid", "Sheet", SAMPLE_DF.iloc[:1],
            column_map={"Имя": "Name", "Группа": "Group"},
        )
        written = sc.write_values.call_args.args[2]
        assert written[0] == ["Name", "Group"]
        assert written[1] == ["Alice", "101"]

    def test_empty_source_data_does_not_write(self):
        sc = _make_sheets_client(sheet_names=[])
        to.build_auxiliary_table(sc, "sid", "Sheet", pd.DataFrame())
        sc.write_values.assert_not_called()


# ---------------------------------------------------------------------------
# generate_documents_from_table
# ---------------------------------------------------------------------------

class TestGenerateDocumentsFromTable:
    def test_generates_one_doc_per_row(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS)
        dc = _make_docs_client()
        ids = to.generate_documents_from_table(
            sc, dc, "sid", "Sheet", "tmpl_id", "folder_id",
            title_column="Имя",
        )
        assert len(ids) == 3
        assert dc.copy_template.call_count == 3
        assert dc.replace_text.call_count == 3

    def test_uses_title_column_for_doc_name(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS[:1])
        dc = _make_docs_client()
        to.generate_documents_from_table(
            sc, dc, "sid", "Sheet", "tmpl_id", "folder_id",
            title_column="Имя",
        )
        dc.copy_template.assert_called_once_with("tmpl_id", "Alice", "folder_id")

    def test_placeholder_substitution(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS[:1])
        dc = _make_docs_client()
        to.generate_documents_from_table(
            sc, dc, "sid", "Sheet", "tmpl_id", "folder_id",
            title_column="Имя",
            column_map={"Имя": "NAME", "Группа": "GROUP"},
        )
        replacements = dc.replace_text.call_args.args[1]
        assert replacements["{{NAME}}"] == "Alice"
        assert replacements["{{GROUP}}"] == "101"

    def test_row_filter_applied(self):
        sc = _make_sheets_client(source_rows=SAMPLE_SOURCE_ROWS)
        dc = _make_docs_client()
        to.generate_documents_from_table(
            sc, dc, "sid", "Sheet", "tmpl_id", "folder_id",
            title_column="Имя",
            row_filter=lambda r: r["Группа"] == "102",
        )
        assert dc.copy_template.call_count == 1
        dc.copy_template.assert_called_once_with("tmpl_id", "Bob", "folder_id")

    def test_empty_sheet_returns_empty(self):
        sc = _make_sheets_client(source_rows=[])
        dc = _make_docs_client()
        result = to.generate_documents_from_table(
            sc, dc, "sid", "Sheet", "tmpl_id", "folder_id",
            title_column="Имя",
        )
        assert result == []
