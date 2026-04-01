from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleConnector:
    def __init__(self, credentials: dict):
        creds = Credentials(
            token=credentials["access_token"],
            refresh_token=credentials.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
        )
        self.drive = build("drive", "v3", credentials=creds)
        self.docs = build("docs", "v1", credentials=creds)

    def list_docs(self) -> list[dict]:
        results = self.drive.files().list(
            q="mimeType='application/vnd.google-apps.document' and trashed=false",
            fields="files(id, name, modifiedTime)",
            pageSize=200,
        ).execute()
        return results.get("files", [])

    def get_doc(self, doc_id: str) -> dict:
        return self.docs.documents().get(documentId=doc_id).execute()
