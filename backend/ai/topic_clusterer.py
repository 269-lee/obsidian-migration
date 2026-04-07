"""
주제 기반 클러스터링
- 모든 소스(Notion + Slack)의 내용을 소스 무관하게 주제별로 군집화
- 각 문서를 먼저 주제 단위 chunk로 분해한 뒤, 유사 chunk끼리 묶음
"""
import json
import anthropic


class TopicClusterer:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chunk_document(self, doc: dict) -> list[dict]:
        """문서 하나를 주제 단위 chunk로 분해"""
        # 내용이 거의 없으면 스킵
        if len(doc["content"].strip()) < 50:
            return []

        text = doc["content"][:6000]  # 너무 길면 앞부분만

        response = await self.client.messages.create(
            model="claude-haiku-4-5-20251001",  # 단순 분해 작업 → 저렴한 모델
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""다음은 "{doc['title']}" ({doc['source']}) 의 내용입니다.

{text}

이 내용을 주제 단위로 분해해주세요.
하나의 주제는 하나의 일관된 논의/업무/이슈를 의미합니다.
내용이 없거나 의미 없는 chunk는 포함하지 마세요.

반드시 아래 JSON 배열로만 응답하세요:
[
  {{
    "topic_hint": "이 chunk의 핵심 주제 (짧은 한국어 라벨)",
    "summary": "이 chunk의 핵심 내용 요약 (2-4문장)",
    "key_points": ["핵심 포인트1", "핵심 포인트2"],
    "people_mentioned": ["언급된 사람 이름 (내부 팀원만, 외부 협업사 직원 제외)"]
  }}
]"""
            }]
        )

        text_resp = response.content[0].text.strip()
        if text_resp.startswith("```"):
            text_resp = text_resp.split("```", 2)[1]
            if text_resp.startswith("json"):
                text_resp = text_resp[4:]
            text_resp = text_resp.rsplit("```", 1)[0].strip()

        chunks = json.loads(text_resp)
        # 소스 정보 + project_hint 첨부
        for chunk in chunks:
            chunk["source_title"] = doc["title"]
            chunk["source_type"] = doc["source"]
            chunk["source_date"] = doc.get("date", "")
            chunk["project_hint"] = doc.get("project_hint")  # Notion project property
        return chunks

    async def cluster_chunks(self, all_chunks: list[dict], folder_structure: list[str], vault_schema: dict = None) -> list[dict]:
        """모든 chunk를 주제별로 군집화 (400개씩 배치 처리)"""
        BATCH_SIZE = 150
        all_clusters = []
        for batch_start in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[batch_start:batch_start + BATCH_SIZE]
            batch_clusters = await self._cluster_batch(batch, batch_start, folder_structure, vault_schema)
            all_clusters.extend(batch_clusters)
        return all_clusters

    async def _cluster_batch(self, batch: list[dict], offset: int, folder_structure: list[str], vault_schema: dict = None) -> list[dict]:
        """chunk 배치 하나를 군집화 (chunk당 1줄 출력으로 안정적인 JSON 생성)"""
        chunks_summary = json.dumps([
            {
                "id": i,
                "topic_hint": c["topic_hint"],
                "summary": c["summary"][:80],
                "source": c["source_title"],
            }
            for i, c in enumerate(batch)
        ], ensure_ascii=False)

        folders_str = ', '.join(folder_structure)

        response = await self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            messages=[{
                "role": "user",
                "content": f"""다음 chunk 목록에서 각 chunk에 클러스터 이름을 할당하세요.

chunk 목록:
{chunks_summary}

사용 가능한 폴더: {folders_str}

규칙:
- 주제가 같은 chunk끼리 같은 cluster_name 사용
- 주제가 다르면 다른 cluster_name
- cluster_name은 구체적인 한국어로 (예: "맞추다 실기 기능 기획", "주간 지표 회의록")
- 의미없는 chunk는 cluster_name을 "general"로
- folder는 {folders_str} 중 하나

반드시 아래 JSON 배열로만 응답하세요. 줄 수는 반드시 {len(batch)}개:
[
  {{"id": 0, "cluster_name": "클러스터명", "folder": "폴더명"}},
  {{"id": 1, "cluster_name": "클러스터명", "folder": "폴더명"}}
]"""
            }]
        )

        text_resp = response.content[0].text.strip()
        if text_resp.startswith("```"):
            text_resp = text_resp.split("```", 2)[1]
            if text_resp.startswith("json"):
                text_resp = text_resp[4:]
            text_resp = text_resp.rsplit("```", 1)[0].strip()

        assignments = json.loads(text_resp)

        # cluster_name으로 그룹화하여 clusters 생성
        from collections import defaultdict
        groups: dict[str, dict] = defaultdict(lambda: {"chunks": [], "folder": "Resources"})
        for item in assignments:
            idx = item["id"]
            if idx < len(batch):
                groups[item["cluster_name"]]["chunks"].append(batch[idx])
                groups[item["cluster_name"]]["folder"] = item.get("folder", "Resources")

        clusters = []
        for name, data in groups.items():
            if not data["chunks"]:
                continue
            clusters.append({
                "name": name,
                "folder": data["folder"],
                "description": "",
                "chunks": data["chunks"],
            })
        return clusters
