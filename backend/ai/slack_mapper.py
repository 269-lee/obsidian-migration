"""
Slack 클러스터 → Notion 노트 매핑
- 각 Slack 클러스터를 기존 Notion 노트와 비교
- 연관성이 높으면 A (기존 노트에 섹션 추가)
- 맥락이 다르면 C (연결된 하위 노트로 생성)
- 매칭 없으면 archive
"""
import json
import anthropic


class SlackMapper:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def map(
        self,
        slack_clusters: list[dict],
        notion_notes: list[dict],  # [{"title": ..., "summary": ..., "folder": ...}]
    ) -> list[dict]:
        """
        Returns:
            [
              {
                "cluster_name": "Slack 클러스터 이름",
                "treatment": "A" | "C" | "archive",
                "target_note": "매칭된 Notion 노트 제목 (A/C일 때)",
              },
              ...
            ]
        """
        if not notion_notes:
            return [
                {"cluster_name": cl["name"], "treatment": "archive", "target_note": None}
                for cl in slack_clusters
            ]

        notion_index = json.dumps(
            [{"title": n["title"], "summary": n.get("summary", "")} for n in notion_notes],
            ensure_ascii=False,
        )

        slack_index = json.dumps(
            [{"name": cl["name"], "description": cl.get("description", "")} for cl in slack_clusters],
            ensure_ascii=False,
        )

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""다음은 Slack에서 추출한 대화 클러스터들입니다:
{slack_index}

다음은 Notion에서 이미 생성된 노트들입니다:
{notion_index}

각 Slack 클러스터를 Notion 노트와 매핑하고 처리 방식을 결정해주세요.

처리 방식 기준:
- **A**: Slack 내용이 해당 Notion 노트와 같은 주제이고 내용을 보강할 수 있음
         → 기존 노트 하단에 "## Slack 논의" 섹션으로 추가
- **C**: Slack 내용이 관련 Notion 노트가 있지만 맥락이 조금 다름 (다른 시점의 논의, 파생된 이슈 등)
         → 해당 Notion 노트에 연결된 별도 하위 노트로 생성
- **archive**: 관련 Notion 노트가 없거나, 잡담/공지 등 지식 가치가 낮음
               → Archive/Slack/ 에 별도 저장

반드시 아래 JSON 배열로만 응답하세요:
[
  {{
    "cluster_name": "Slack 클러스터 이름 (위 목록과 정확히 동일하게)",
    "treatment": "A",
    "target_note": "매칭된 Notion 노트 제목 (treatment가 archive면 null)"
  }}
]"""
            }]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()

        results = json.loads(text)

        # 검증: target_note가 실제 Notion 노트 목록에 있는지 확인
        valid_titles = {n["title"] for n in notion_notes}
        for r in results:
            if r.get("target_note") and r["target_note"] not in valid_titles:
                r["treatment"] = "archive"
                r["target_note"] = None

        return results
