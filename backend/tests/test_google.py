import pytest
from unittest.mock import MagicMock, patch
from connectors.google import GoogleConnector


@pytest.fixture
def mock_creds():
    return {
        "access_token": "test-token",
        "refresh_token": "refresh",
        "client_id": "client-id",
        "client_secret": "client-secret",
    }


def test_list_docs(mock_creds):
    with patch("connectors.google.build") as mock_build:
        mock_drive = MagicMock()
        mock_drive.files().list().execute.return_value = {
            "files": [
                {"id": "doc1", "name": "Meeting Notes", "modifiedTime": "2024-01-01T00:00:00Z"},
            ]
        }
        mock_build.return_value = mock_drive

        connector = GoogleConnector(mock_creds)
        connector.drive = mock_drive
        docs = connector.list_docs()
        assert len(docs) == 1
        assert docs[0]["name"] == "Meeting Notes"


def test_get_doc(mock_creds):
    with patch("connectors.google.build"):
        connector = GoogleConnector(mock_creds)
        mock_docs = MagicMock()
        mock_docs.documents().get().execute.return_value = {
            "documentId": "doc1",
            "title": "Meeting Notes",
            "body": {"content": []},
        }
        connector.docs = mock_docs
        doc = connector.get_doc("doc1")
        assert doc["title"] == "Meeting Notes"
