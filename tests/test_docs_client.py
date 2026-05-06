"""Tests for docs_client.DocsClient."""

from unittest.mock import MagicMock

import pytest

from docs_client import DocsClient


class TestCreateDocument:
    def test_create_document_returns_id(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        docs_svc.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc123"
        }
        client = DocsClient(docs_svc, drive_svc)
        doc_id = client.create_document("My Title")
        assert doc_id == "doc123"

    def test_create_document_adds_to_folder(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        docs_svc.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc123"
        }
        drive_svc.files.return_value.update.return_value.execute.return_value = {}

        client = DocsClient(docs_svc, drive_svc)
        doc_id = client.create_document("My Title", folder_id="new_folder")

        assert doc_id == "doc123"
        update_call = drive_svc.files.return_value.update
        update_call.assert_called_once()
        kwargs = update_call.call_args.kwargs
        # Only adds the new parent; does NOT remove any existing parents
        assert kwargs["addParents"] == "new_folder"
        assert "removeParents" not in kwargs

    def test_create_document_no_folder(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        docs_svc.documents.return_value.create.return_value.execute.return_value = {
            "documentId": "doc456"
        }
        client = DocsClient(docs_svc, drive_svc)
        client.create_document("No Folder")
        # Drive.files().update should NOT be called when no folder is given
        drive_svc.files.return_value.update.assert_not_called()


class TestCopyTemplate:
    def test_copy_template_returns_new_id(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        drive_svc.files.return_value.copy.return_value.execute.return_value = {
            "id": "new_doc_id"
        }
        client = DocsClient(docs_svc, drive_svc)
        new_id = client.copy_template("template_id", "Copy Title")
        assert new_id == "new_doc_id"
        copy_kwargs = drive_svc.files.return_value.copy.call_args.kwargs
        assert copy_kwargs["fileId"] == "template_id"
        assert copy_kwargs["body"]["name"] == "Copy Title"

    def test_copy_template_sets_folder(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        drive_svc.files.return_value.copy.return_value.execute.return_value = {
            "id": "new_doc_id"
        }
        client = DocsClient(docs_svc, drive_svc)
        client.copy_template("template_id", "Copy Title", folder_id="folder_id")
        copy_kwargs = drive_svc.files.return_value.copy.call_args.kwargs
        assert copy_kwargs["body"]["parents"] == ["folder_id"]


class TestGetDocument:
    def test_get_document_calls_api(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        docs_svc.documents.return_value.get.return_value.execute.return_value = {
            "documentId": "doc123",
            "title": "My Doc",
        }
        client = DocsClient(docs_svc, drive_svc)
        result = client.get_document("doc123")
        assert result["title"] == "My Doc"


class TestReplaceText:
    def test_replace_text_builds_correct_requests(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        batch_mock = docs_svc.documents.return_value.batchUpdate
        batch_mock.return_value.execute.return_value = {}

        client = DocsClient(docs_svc, drive_svc)
        client.replace_text("doc123", {"{{NAME}}": "Alice", "{{AGE}}": "30"})

        batch_mock.assert_called_once()
        body = batch_mock.call_args.kwargs["body"]
        requests = body["requests"]
        # Two replacements expected
        assert len(requests) == 2
        placeholders = {r["replaceAllText"]["containsText"]["text"] for r in requests}
        assert placeholders == {"{{NAME}}", "{{AGE}}"}

    def test_replace_text_empty_replacements(self):
        docs_svc = MagicMock()
        drive_svc = MagicMock()
        batch_mock = docs_svc.documents.return_value.batchUpdate
        batch_mock.return_value.execute.return_value = {}

        client = DocsClient(docs_svc, drive_svc)
        client.replace_text("doc123", {})

        body = batch_mock.call_args.kwargs["body"]
        assert body["requests"] == []
