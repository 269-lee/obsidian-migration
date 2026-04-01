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
        with httpx.Client() as client:
            response = client.post(
                f"{self.BASE_URL}/search",
                headers=self.headers,
                json={"filter": {"value": "page", "property": "object"}, "page_size": 100},
            )
            response.raise_for_status()
            return response.json()["results"]

    def get_page_content(self, page_id: str) -> dict:
        with httpx.Client() as client:
            page_resp = client.get(
                f"{self.BASE_URL}/pages/{page_id}", headers=self.headers
            )
            page_resp.raise_for_status()
            page = page_resp.json()

            blocks_resp = client.get(
                f"{self.BASE_URL}/blocks/{page_id}/children", headers=self.headers
            )
            blocks_resp.raise_for_status()

            title_prop = page.get("properties", {}).get("title", {})
            title_parts = title_prop.get("title", [])
            title = "".join(t["plain_text"] for t in title_parts) or "Untitled"

            return {
                "id": page_id,
                "title": title,
                "created_time": page.get("created_time", ""),
                "blocks": blocks_resp.json()["results"],
            }
