"""
Higher-level table operations built on top of SheetsClient and DocsClient.

These helpers implement the workflows described in the problem statement:

* Transferring rows between spreadsheets / sheets (with optional column
  renaming and row filtering).
* Building auxiliary tables inside a spreadsheet.
* Generating one Google Doc per row from a template document.
"""

from __future__ import annotations

from typing import Any, Callable

from docs_client import DocsClient
from sheets_client import SheetsClient


def transfer_rows(
    sheets_client: SheetsClient,
    source_id: str,
    source_sheet: str,
    dest_id: str,
    dest_sheet: str,
    column_map: dict[str, str] | None = None,
    row_filter: Callable[[dict[str, Any]], bool] | None = None,
    delete_from_source: bool = False,
) -> list[dict[str, Any]]:
    """Transfer rows from one sheet to another, optionally renaming columns.

    The function reads *source_sheet* from *source_id*, applies the optional
    *row_filter*, renames columns according to *column_map*, and appends the
    resulting rows to *dest_sheet* in *dest_id*.

    Parameters
    ----------
    sheets_client:
        Initialized :class:`~sheets_client.SheetsClient`.
    source_id:
        Spreadsheet ID of the source table.
    source_sheet:
        Sheet name in the source spreadsheet.
    dest_id:
        Spreadsheet ID of the destination table.
    dest_sheet:
        Sheet name in the destination spreadsheet.
    column_map:
        Optional mapping ``{source_column_name: dest_column_name}``.
        Only the columns listed as keys are transferred; if *None*, all
        columns are transferred unchanged.
    row_filter:
        Optional callable that receives a row dict and returns ``True`` if
        the row should be transferred.
    delete_from_source:
        If ``True``, delete transferred rows from the source sheet after
        a successful write.  Row deletion is performed from the bottom to
        preserve correct indices.

    Returns
    -------
    list[dict[str, Any]]
        The list of row dicts that were written to the destination.
    """
    source_rows = sheets_client.read_as_dicts(source_id, source_sheet)

    # Apply row filter
    if row_filter is not None:
        selected = [
            (idx, row)
            for idx, row in enumerate(source_rows)
            if row_filter(row)
        ]
    else:
        selected = list(enumerate(source_rows))

    if not selected:
        return []

    # Build destination rows according to column_map
    if column_map is not None:
        dest_header = list(column_map.values())
        dest_rows_values: list[list[Any]] = [
            [row.get(src_col, "") for src_col in column_map]
            for _, row in selected
        ]
    else:
        # Use source headers unchanged; read them from the first source row
        dest_header = list(source_rows[0].keys()) if source_rows else []
        dest_rows_values = [
            [row.get(col, "") for col in dest_header]
            for _, row in selected
        ]

    # Check whether destination sheet is empty (needs header row)
    existing = sheets_client.read_values(dest_id, dest_sheet)
    if not existing:
        sheets_client.append_rows(dest_id, dest_sheet, [dest_header])

    sheets_client.append_rows(dest_id, dest_sheet, dest_rows_values)

    transferred = [row for _, row in selected]

    # Optionally delete from source (delete bottom-up to keep indices valid)
    if delete_from_source and selected:
        sheet_id = sheets_client.get_sheet_id(source_id, source_sheet)
        # selected indices are data-row indices (0-based within source_rows);
        # add 1 to account for the header row in the sheet.
        source_indices = sorted([idx + 1 for idx, _ in selected], reverse=True)
        for row_idx in source_indices:
            sheets_client.delete_rows(
                source_id, sheet_id, row_idx, row_idx + 1
            )

    return transferred


def build_auxiliary_table(
    sheets_client: SheetsClient,
    spreadsheet_id: str,
    sheet_name: str,
    source_data: list[dict[str, Any]],
    column_map: dict[str, str] | None = None,
) -> None:
    """Create (or overwrite) an auxiliary table inside an existing spreadsheet.

    If *sheet_name* already exists its contents are cleared; otherwise a
    new sheet tab is created.

    Parameters
    ----------
    sheets_client:
        Initialized :class:`~sheets_client.SheetsClient`.
    spreadsheet_id:
        The ID of the spreadsheet where the table will be written.
    sheet_name:
        Name of the sheet (tab) to create / overwrite.
    source_data:
        List of row dicts to write.
    column_map:
        Optional mapping ``{source_key: column_header}``.  Only the keys
        listed are written.  If *None*, all keys from the first row are
        used, with their original names as headers.
    """
    existing_sheets = sheets_client.get_sheet_names(spreadsheet_id)

    if sheet_name in existing_sheets:
        sheets_client.clear_range(spreadsheet_id, sheet_name)
    else:
        sheets_client.add_sheet(spreadsheet_id, sheet_name)

    if not source_data:
        return

    if column_map is not None:
        header = list(column_map.values())
        rows: list[list[Any]] = [
            [row.get(src_key, "") for src_key in column_map]
            for row in source_data
        ]
    else:
        header = list(source_data[0].keys())
        rows = [[row.get(col, "") for col in header] for row in source_data]

    sheets_client.write_values(
        spreadsheet_id, sheet_name, [header] + rows
    )


def generate_documents_from_table(
    sheets_client: SheetsClient,
    docs_client: DocsClient,
    spreadsheet_id: str,
    sheet_name: str,
    template_id: str,
    folder_id: str,
    title_column: str,
    column_map: dict[str, str] | None = None,
    row_filter: Callable[[dict[str, Any]], bool] | None = None,
) -> list[str]:
    """Generate one Google Doc per row from a template document.

    For each selected row the template document is copied and then all
    ``{{PLACEHOLDER}}`` strings (matching the destination column names from
    *column_map*, e.g. ``{{ФИО}}``) are replaced with the corresponding
    cell values.

    Parameters
    ----------
    sheets_client:
        Initialized :class:`~sheets_client.SheetsClient`.
    docs_client:
        Initialized :class:`~docs_client.DocsClient`.
    spreadsheet_id:
        The spreadsheet containing the data rows.
    sheet_name:
        Sheet (tab) name to read rows from.
    template_id:
        Drive file ID of the template Google Doc.
    folder_id:
        Drive folder ID where generated documents are saved.
    title_column:
        The column whose value is used as the document title.  This is
        the *source* column name (before any column mapping).
    column_map:
        Optional mapping ``{source_column: placeholder_text}``.
        Each source cell value replaces ``{{placeholder_text}}`` in the
        copied document.  If *None*, every source column ``COL`` is
        mapped to the placeholder ``{{COL}}``.
    row_filter:
        Optional callable that receives a row dict and returns ``True``
        when the row should produce a document.

    Returns
    -------
    list[str]
        IDs of the newly created documents (one per transferred row).
    """
    rows = sheets_client.read_as_dicts(spreadsheet_id, sheet_name)

    if row_filter is not None:
        rows = [row for row in rows if row_filter(row)]

    if not rows:
        return []

    if column_map is None:
        column_map = {col: col for col in rows[0]}

    document_ids: list[str] = []
    for row in rows:
        doc_title = row.get(title_column, "Document")
        new_doc_id = docs_client.copy_template(template_id, doc_title, folder_id)

        replacements = {
            f"{{{{{placeholder}}}}}": str(row.get(src_col, ""))
            for src_col, placeholder in column_map.items()
        }
        docs_client.replace_text(new_doc_id, replacements)
        document_ids.append(new_doc_id)

    return document_ids
