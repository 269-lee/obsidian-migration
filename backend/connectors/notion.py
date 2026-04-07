import httpx


class NotionConnector:
    BASE_URL = "https://api.notion.com/v1"

    def __init__(self, token: str):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def list_pages(self) -> list[dict]:
        """전체 페이지 수집 (커서 페이지네이션)"""
        pages = []
        start_cursor = None
        with httpx.Client(timeout=30) as client:
            while True:
                body = {"filter": {"value": "page", "property": "object"}, "page_size": 100}
                if start_cursor:
                    body["start_cursor"] = start_cursor
                response = client.post(
                    f"{self.BASE_URL}/search",
                    headers=self.headers,
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
                pages.extend(data.get("results", []))
                if not data.get("has_more"):
                    break
                start_cursor = data.get("next_cursor")
                if not start_cursor:
                    break
        return pages

    def get_page_content(self, page_id: str) -> dict:
        with httpx.Client(timeout=30) as client:
            page_resp = client.get(
                f"{self.BASE_URL}/pages/{page_id}", headers=self.headers
            )
            page_resp.raise_for_status()
            page = page_resp.json()

            blocks_resp = client.get(
                f"{self.BASE_URL}/blocks/{page_id}/children", headers=self.headers
            )
            blocks_resp.raise_for_status()

            properties = page.get("properties", {})

            title_prop = properties.get("title", {})
            title_parts = title_prop.get("title", [])
            title = "".join(t["plain_text"] for t in title_parts) or "Untitled"

            # project property 추출 (relation / select / rich_text 모두 지원)
            project_hint = None
            for key, prop in properties.items():
                if key.lower() in ("project", "프로젝트"):
                    ptype = prop.get("type")
                    if ptype == "relation":
                        rel = prop.get("relation", [])
                        if rel:
                            project_hint = rel[0].get("id")
                    elif ptype == "select":
                        sel = prop.get("select")
                        if sel:
                            project_hint = sel.get("name")
                    elif ptype == "rich_text":
                        parts = prop.get("rich_text", [])
                        project_hint = "".join(p["plain_text"] for p in parts) or None
                    break

            return {
                "id": page_id,
                "title": title,
                "created_time": page.get("created_time", ""),
                "blocks": blocks_resp.json()["results"],
                "project_hint": project_hint,
            }
