import httpx


class SlackConnector:
    BASE_URL = "https://slack.com/api"

    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}"}

    def list_channels(self) -> list[dict]:
        with httpx.Client() as client:
            response = client.get(
                f"{self.BASE_URL}/conversations.list",
                headers=self.headers,
                params={"types": "public_channel,private_channel", "limit": 200},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("channels", [])

    def get_messages(self, channel_id: str) -> list[dict]:
        with httpx.Client() as client:
            response = client.get(
                f"{self.BASE_URL}/conversations.history",
                headers=self.headers,
                params={"channel": channel_id, "limit": 1000},
            )
            response.raise_for_status()
            return response.json().get("messages", [])
