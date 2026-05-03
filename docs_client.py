"""
Google Docs / Drive client for creating and populating documents.

``DocsClient`` wraps both the Docs API (v1) and the Drive API (v3) to
support the document-generation workflow described in the problem statement.
"""

from __future__ import annotations


class DocsClient:
    """High-level wrapper for Google Docs and Drive operations.

    Parameters
    ----------
    docs_service:
        An authenticated ``googleapiclient`` resource object for the Docs API (v1),
        typically obtained via :func:`auth.build_docs_service`.
    drive_service:
        An authenticated ``googleapiclient`` resource object for the Drive API (v3),
        typically obtained via :func:`auth.build_drive_service`.
    """

    def __init__(self, docs_service, drive_service) -> None:
        self._docs = docs_service
        self._drive = drive_service

    # ------------------------------------------------------------------
    # Document creation
    # ------------------------------------------------------------------

    def create_document(
        self, title: str, folder_id: str | None = None
    ) -> str:
        """Create a new, empty Google Docs document and return its ID.

        Parameters
        ----------
        title:
            Title of the new document.
        folder_id:
            Optional Google Drive folder ID.  If provided, the document is
            moved to that folder immediately after creation.
        """
        doc = self._docs.documents().create(body={"title": title}).execute()
        document_id = doc["documentId"]

        if folder_id:
            self._move_to_folder(document_id, folder_id)

        return document_id

    def copy_template(
        self, template_id: str, title: str, folder_id: str | None = None
    ) -> str:
        """Copy an existing document as a template and return the new document ID.

        Parameters
        ----------
        template_id:
            Drive file ID of the template document.
        title:
            Title for the new copy.
        folder_id:
            Optional Drive folder ID where the copy will be placed.
        """
        copy_meta = {"name": title}
        if folder_id:
            copy_meta["parents"] = [folder_id]

        copied = (
            self._drive.files()
            .copy(fileId=template_id, body=copy_meta)
            .execute()
        )
        return copied["id"]

    # ------------------------------------------------------------------
    # Document reading
    # ------------------------------------------------------------------

    def get_document(self, document_id: str) -> dict:
        """Return the full document resource for *document_id*."""
        return self._docs.documents().get(documentId=document_id).execute()

    # ------------------------------------------------------------------
    # Document editing
    # ------------------------------------------------------------------

    def replace_text(
        self, document_id: str, replacements: dict[str, str]
    ) -> dict:
        """Replace placeholder strings in a document.

        Each key in *replacements* is searched for literally and replaced
        with its corresponding value throughout the entire document.

        Parameters
        ----------
        document_id:
            ID of the document to edit.
        replacements:
            Mapping of ``{placeholder: replacement_text}``.
            Placeholders are typically written as ``{{FIELD_NAME}}`` in the
            template to avoid accidental matches.

        Returns
        -------
        dict
            The ``batchUpdate`` API response.
        """
        requests = [
            {
                "replaceAllText": {
                    "containsText": {
                        "text": placeholder,
                        "matchCase": True,
                    },
                    "replaceText": replacement,
                }
            }
            for placeholder, replacement in replacements.items()
        ]
        return (
            self._docs.documents()
            .batchUpdate(documentId=document_id, body={"requests": requests})
            .execute()
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _move_to_folder(self, file_id: str, folder_id: str) -> None:
        """Move *file_id* into *folder_id* using the Drive API."""
        # Retrieve current parents so we can remove them
        file_meta = (
            self._drive.files()
            .get(fileId=file_id, fields="parents")
            .execute()
        )
        previous_parents = ",".join(file_meta.get("parents", []))
        self._drive.files().update(
            fileId=file_id,
            addParents=folder_id,
            removeParents=previous_parents,
            fields="id, parents",
        ).execute()
