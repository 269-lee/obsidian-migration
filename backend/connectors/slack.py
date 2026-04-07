import time
import httpx
from datetime import datetime, timedelta


class SlackConnector:
    BASE_URL = "https://slack.com/api"

    def __init__(self, token: str):
        self.headers = {"Authorization": f"Bearer {token}"}

    def list_channels(self) -> list[dict]:
        channels = []
        cursor = None
        with httpx.Client() as client:
            while True:
                params = {"types": "public_channel,private_channel", "limit": 200}
                if cursor:
                    params["cursor"] = cursor
                response = client.get(
                    f"{self.BASE_URL}/conversations.list",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                channels.extend(data.get("channels", []))
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
        return channels

    def get_messages(self, channel_id: str, days: int = 365) -> list[dict]:
        """최근 N일치 메시지 전체 수집 (커서 페이지네이션)"""
        oldest = (datetime.now() - timedelta(days=days)).timestamp()
        messages = []
        cursor = None
        with httpx.Client(timeout=30) as client:
            while True:
                params = {
                    "channel": channel_id,
                    "limit": 1000,
                    "oldest": str(oldest),
                }
                if cursor:
                    params["cursor"] = cursor
                response = client.get(
                    f"{self.BASE_URL}/conversations.history",
                    headers=self.headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                messages.extend(data.get("messages", []))
                if not data.get("has_more"):
                    break
                cursor = data.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
                time.sleep(0.5)  # Slack API 레이트 리밋 방지
        return messages

    def get_threads(self, channel_id: str, channel_name: str, days: int = 365) -> list[dict]:
        """채널의 스레드를 개별 문서 단위로 수집.

        스레드가 있는 메시지는 replies까지 포함해서 하나의 문서로 반환.
        스레드 없는 단발 메시지는 같은 날짜끼리 묶어서 하나의 문서로 반환.
        """
        messages = self.get_messages(channel_id, days=days)
        if not messages:
            return []

        threads: list[dict] = []
        standalone: list[dict] = []  # 스레드 없는 단발 메시지

        with httpx.Client(timeout=30) as client:
            for msg in messages:
                if msg.get("bot_id"):
                    continue
                # 스레드 부모 메시지 (reply_count > 0)
                if msg.get("reply_count", 0) > 0:
                    thread_ts = msg["ts"]
                    replies = self._get_replies(client, channel_id, thread_ts)
                    all_msgs = [msg] + [r for r in replies if not r.get("bot_id")]
                    content = self._format_thread(all_msgs)
                    # 첫 메시지 텍스트를 제목으로 사용 (최대 50자)
                    first_text = msg.get("text", "").strip().replace("\n", " ")[:50]
                    title = f"#{channel_name} | {first_text}" if first_text else f"#{channel_name} 스레드"
                    threads.append({
                        "title": title,
                        "content": content,
                        "source": "slack",
                        "date": datetime.fromtimestamp(float(thread_ts)).strftime("%Y-%m-%d"),
                        "channel": channel_name,
                        "project_hint": None,
                    })
                elif not msg.get("thread_ts"):
                    # 스레드에 속하지 않는 단발 메시지
                    standalone.append(msg)

        # 단발 메시지는 날짜별로 묶어서 하나의 문서로
        if standalone:
            by_date: dict[str, list[dict]] = {}
            for msg in standalone:
                date = datetime.fromtimestamp(float(msg["ts"])).strftime("%Y-%m-%d")
                by_date.setdefault(date, []).append(msg)
            for date, msgs in sorted(by_date.items()):
                content = self._format_thread(msgs)
                threads.append({
                    "title": f"#{channel_name} | {date} 대화",
                    "content": content,
                    "source": "slack",
                    "date": date,
                    "channel": channel_name,
                    "project_hint": None,
                })

        return threads

    def _get_replies(self, client: httpx.Client, channel_id: str, thread_ts: str) -> list[dict]:
        """스레드 replies 수집"""
        try:
            response = client.get(
                f"{self.BASE_URL}/conversations.replies",
                headers=self.headers,
                params={"channel": channel_id, "ts": thread_ts, "limit": 200},
            )
            response.raise_for_status()
            msgs = response.json().get("messages", [])
            return msgs[1:]  # 첫 번째는 부모 메시지이므로 제외
        except Exception:
            return []

    def _format_thread(self, messages: list[dict]) -> str:
        """메시지 목록을 마크다운으로 변환"""
        lines = []
        for msg in messages:
            ts = msg.get("ts", "")
            try:
                dt = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                dt = ts
            user = msg.get("user", "unknown")
            text = msg.get("text", "").strip()
            if text:
                lines.append(f"**{user}** ({dt})")
                lines.append(text)
                lines.append("")
        return "\n".join(lines)
