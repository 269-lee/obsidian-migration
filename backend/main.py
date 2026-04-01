import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from connectors.notion import NotionConnector
from connectors.slack import SlackConnector
from connectors.google import GoogleConnector
from converter.markdown import notion_blocks_to_markdown, slack_messages_to_markdown, google_doc_to_markdown
from ai.analyzer import KnowledgeAnalyzer
from ai.classifier import NoteClassifier

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SourceSelection(BaseModel):
    claude_api_key: str
    notion_token: str | None = None
    notion_page_ids: list[str] = []
    slack_token: str | None = None
    slack_channel_ids: list[str] = []
    google_credentials: dict | None = None
    google_doc_ids: list[str] = []
    folder_structure: list[str] = ["Projects", "Areas", "Resources", "Inbox"]


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/sources/notion/pages")
def list_notion_pages(body: dict):
    connector = NotionConnector(token=body["token"])
    pages = connector.list_pages()
    return [
        {
            "id": p["id"],
            "title": "".join(
                t["plain_text"]
                for t in p.get("properties", {}).get("title", {}).get("title", [])
            ) or "Untitled"
        }
        for p in pages
    ]


@app.post("/api/sources/slack/channels")
def list_slack_channels(body: dict):
    connector = SlackConnector(token=body["token"])
    channels = connector.list_channels()
    return [{"id": c["id"], "name": c["name"]} for c in channels]


@app.post("/api/sources/google/docs")
def list_google_docs(body: dict):
    connector = GoogleConnector(credentials=body["credentials"])
    docs = connector.list_docs()
    return [{"id": d["id"], "name": d["name"]} for d in docs]


@app.post("/api/migrate")
def migrate(selection: SourceSelection):
    api_key = selection.claude_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail="Claude API 키를 입력해주세요")

    def generate():
        documents = []

        if selection.notion_token and selection.notion_page_ids:
            connector = NotionConnector(token=selection.notion_token)
            for i, page_id in enumerate(selection.notion_page_ids):
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Notion 페이지 수집 중... ({i+1}/{len(selection.notion_page_ids)})', 'percent': 5})}\n\n"
                content = connector.get_page_content(page_id)
                markdown = notion_blocks_to_markdown(content["blocks"])
                documents.append({
                    "title": content["title"],
                    "content": markdown,
                    "source": "notion",
                    "date": content.get("created_time", "")[:10],
                })

        if selection.slack_token and selection.slack_channel_ids:
            connector = SlackConnector(token=selection.slack_token)
            for i, channel_id in enumerate(selection.slack_channel_ids):
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Slack 채널 수집 중... ({i+1}/{len(selection.slack_channel_ids)})', 'percent': 15})}\n\n"
                messages = connector.get_messages(channel_id)
                markdown = slack_messages_to_markdown(messages, channel_name=channel_id)
                documents.append({
                    "title": f"Slack - {channel_id}",
                    "content": markdown,
                    "source": "slack",
                    "date": "",
                })

        if selection.google_credentials and selection.google_doc_ids:
            connector = GoogleConnector(credentials=selection.google_credentials)
            for i, doc_id in enumerate(selection.google_doc_ids):
                yield f"data: {json.dumps({'type': 'progress', 'message': f'Google Docs 수집 중... ({i+1}/{len(selection.google_doc_ids)})', 'percent': 25})}\n\n"
                doc = connector.get_doc(doc_id)
                markdown = google_doc_to_markdown(doc)
                documents.append({
                    "title": doc.get("title", "Untitled"),
                    "content": markdown,
                    "source": "google",
                    "date": "",
                })

        if not documents:
            yield f"data: {json.dumps({'type': 'error', 'message': '수집된 문서가 없습니다'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'progress', 'message': 'Claude가 전체 문서를 분석 중...', 'percent': 35})}\n\n"
        analyzer = KnowledgeAnalyzer(api_key=api_key)
        schema = analyzer.analyze(documents, selection.folder_structure)

        classifier = NoteClassifier(api_key=api_key)
        all_titles = [d["title"] for d in documents]

        for i, doc in enumerate(documents):
            percent = 40 + int((i / len(documents)) * 55)
            doc_title = doc["title"]
            yield f"data: {json.dumps({'type': 'progress', 'message': f'{doc_title} 변환 중...', 'percent': percent})}\n\n"

            classified = classifier.classify(doc, schema, all_titles, selection.folder_structure)
            file_content = classifier.to_markdown(classified)
            file_path = f"{classified['folder']}/{doc['title']}.md"

            yield f"data: {json.dumps({'type': 'file', 'path': file_path, 'content': file_content})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'message': '마이그레이션 완료!', 'percent': 100, 'total': len(documents)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
