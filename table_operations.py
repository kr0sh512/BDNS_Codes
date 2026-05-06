"""
Higher-level table operations built on top of SheetsClient and DocsClient.

All internal data manipulation is performed with pandas DataFrames.

* Transferring rows between spreadsheets / sheets (with optional column
  renaming and row filtering).
* Building auxiliary tables inside a spreadsheet.
* Generating one Google Doc per row from a template document.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from docs_client import DocsClient
from sheets_client import SheetsClient


def transfer_rows(
    sheets_client: SheetsClient,
    source_id: str,
    source_sheet: str,
    dest_id: str,
    dest_sheet: str,
    column_map: dict[str, str] | None = None,
    row_filter: Callable[[pd.Series], bool] | None = None,
    delete_from_source: bool = False,
) -> pd.DataFrame:
    """Transfer rows from one sheet to another, optionally renaming columns.

    Reads *source_sheet* into a DataFrame, applies the optional *row_filter*,
    renames / selects columns according to *column_map*, and appends the
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
        Optional callable that receives a row (``pd.Series``) and returns
        ``True`` if the row should be transferred.  Applied via
        ``df.apply(row_filter, axis=1)``; for very large sheets a
        vectorized mask (e.g. ``df["col"] == value``) passed as a boolean
        Series is more performant.
    delete_from_source:
        If ``True``, delete transferred rows from the source sheet after
        a successful write.  Row deletion is performed from the bottom to
        preserve correct indices.

    Returns
    -------
    pd.DataFrame
        The rows that were written to the destination (with destination
        column names).  Returns an empty DataFrame when nothing was
        transferred.
    """
    source_rows = sheets_client.read_as_dicts(source_id, source_sheet)
    df = pd.DataFrame(source_rows)

    if df.empty:
        return pd.DataFrame()

    # Apply row filter and remember original (pre-filter) positional indices
    if row_filter is not None:
        mask = df.apply(row_filter, axis=1)
        selected_df = df[mask]
        selected_indices = df.index[mask].tolist()
    else:
        selected_df = df
        selected_indices = df.index.tolist()

    if selected_df.empty:
        return pd.DataFrame()

    # Select and rename columns
    if column_map is not None:
        dest_df = selected_df[list(column_map.keys())].rename(columns=column_map)
    else:
        dest_df = selected_df.copy()

    # Write header row only when destination sheet is currently empty
    existing = sheets_client.read_values(dest_id, dest_sheet)
    if not existing:
        sheets_client.append_rows(dest_id, dest_sheet, [dest_df.columns.tolist()])

    sheets_client.append_rows(dest_id, dest_sheet, dest_df.values.tolist())

    # Optionally delete from source (bottom-up to keep indices valid)
    if delete_from_source:
        sheet_id = sheets_client.get_sheet_id(source_id, source_sheet)
        # +1 because index 0 in source_rows corresponds to row 1 in the sheet
        # (row 0 is the header).
        for row_idx in sorted([idx + 1 for idx in selected_indices], reverse=True):
            sheets_client.delete_rows(source_id, sheet_id, row_idx, row_idx + 1)

    return dest_df.reset_index(drop=True)


def build_auxiliary_table(
    sheets_client: SheetsClient,
    spreadsheet_id: str,
    sheet_name: str,
    source_data: pd.DataFrame,
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
        DataFrame to write.  Pass an empty DataFrame to create an empty sheet.
    column_map:
        Optional mapping ``{source_column: output_column_header}``.  Only
        the columns listed are written.  If *None*, all columns are written
        with their original names.
    """
    existing_sheets = sheets_client.get_sheet_names(spreadsheet_id)

    if sheet_name in existing_sheets:
        sheets_client.clear_range(spreadsheet_id, sheet_name)
    else:
        sheets_client.add_sheet(spreadsheet_id, sheet_name)

    if source_data.empty:
        return

    if column_map is not None:
        df = source_data[list(column_map.keys())].rename(columns=column_map)
    else:
        df = source_data

    sheets_client.write_values(
        spreadsheet_id, sheet_name, [df.columns.tolist()] + df.values.tolist()
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
    row_filter: Callable[[pd.Series], bool] | None = None,
) -> list[str]:
    """Generate one Google Doc per row from a template document.

    For each selected row the template document is copied and then all
    ``{{PLACEHOLDER}}`` strings are replaced with the corresponding cell
    values from the row.

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
        The source column whose value is used as the document title.
    column_map:
        Optional mapping ``{source_column: placeholder_text}``.
        Each source cell value replaces ``{{placeholder_text}}`` in the
        copied document.  If *None*, every source column ``COL`` maps to
        ``{{COL}}``.
    row_filter:
        Optional callable receiving a row (``pd.Series``) and returning
        ``True`` when the row should produce a document.  Applied via
        ``df.apply(row_filter, axis=1)``; for very large sheets a
        vectorized boolean mask is more performant.

    Returns
    -------
    list[str]
        IDs of the newly created documents (one per row).
    """
    source_rows = sheets_client.read_as_dicts(spreadsheet_id, sheet_name)
    df = pd.DataFrame(source_rows)

    if df.empty:
        return []

    if row_filter is not None:
        df = df[df.apply(row_filter, axis=1)].reset_index(drop=True)

    if df.empty:
        return []

    if column_map is None:
        column_map = {col: col for col in df.columns}

    document_ids: list[str] = []
    for row in df.to_dict(orient="records"):
        doc_title = str(row.get(title_column, "Document"))
        new_doc_id = docs_client.copy_template(template_id, doc_title, folder_id)
        replacements = {
            f"{{{{{placeholder}}}}}": str(row.get(src_col, ""))
            for src_col, placeholder in column_map.items()
        }
        docs_client.replace_text(new_doc_id, replacements)
        document_ids.append(new_doc_id)

    return document_ids
