"""
계층 분석기
- 클러스터 목록을 보고 "프로젝트 노트"와 "하위 노트"를 구분
- 판단 근거: Notion project property, 언급 빈도, chunk 수, AI 내용 판단
"""
import json
import anthropic


class HierarchyAnalyzer:
    def __init__(self, api_key: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    def _compute_signals(self, clusters: list[dict]) -> list[dict]:
        """각 클러스터의 계층 판단에 쓸 신호값 계산"""
        # 1. project_hints: Notion project property에 명시된 소속 프로젝트
        #    (chunk에 project_hint가 있으면 해당 cluster는 하위 노트 후보)
        # 2. mention_count: 다른 chunk들의 summary/topic_hint에 이 클러스터 이름이 등장한 횟수
        # 3. chunk_count: chunk가 많을수록 논의가 많이 된 주제

        all_text = " ".join(
            f"{c.get('topic_hint', '')} {c.get('summary', '')}"
            for cluster in clusters
            for c in cluster["chunks"]
        ).lower()

        signals = []
        for cluster in clusters:
            chunk_count = len(cluster["chunks"])

            # project_hints 수집 (chunk 레벨에서 전파된 Notion project property)
            project_hints = list({
                c["project_hint"]
                for c in cluster["chunks"]
                if c.get("project_hint")
            })

            # 다른 클러스터 chunk에서 이 클러스터 이름이 언급된 횟수
            name_lower = cluster["name"].lower()
            mention_count = all_text.count(name_lower)

            signals.append({
                "cluster_name": cluster["name"],
                "folder": cluster["folder"],
                "description": cluster["description"],
                "chunk_count": chunk_count,
                "mention_count": mention_count,
                "project_hints": project_hints,  # 이 클러스터가 소속된 프로젝트 이름 후보
            })

        return signals

    async def analyze(self, clusters: list[dict]) -> list[dict]:
        """
        Returns:
            [
              {"cluster_name": "...", "is_project": True, "parent": None},
              {"cluster_name": "...", "is_project": False, "parent": "부모 클러스터 이름"},
              ...
            ]
        """
        signals = self._compute_signals(clusters)
        cluster_names = [s["cluster_name"] for s in signals]

        response = await self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"""다음은 Obsidian 마이그레이션을 위해 추출된 주제 클러스터들입니다.
각 클러스터를 "프로젝트 노트(최상위)" 또는 "하위 노트(특정 프로젝트에 속함)"로 분류해주세요.

클러스터 목록:
{json.dumps(signals, ensure_ascii=False, indent=2)}

분류 기준:
- project_hints가 있으면 그 클러스터는 해당 프로젝트의 하위 노트
- mention_count가 높고 chunk_count가 많으면 프로젝트 노트 가능성 높음
- 미팅 로그, 이슈, 특정 날짜/사건 중심이면 하위 노트
- 장기적인 목표, 전략, 서비스 기능 전체를 다루면 프로젝트 노트
- 하위 노트의 parent는 반드시 위 클러스터 목록 중 하나의 이름이어야 함
- parent를 찾기 어려우면 null (독립 노트로 처리)

반드시 아래 JSON 배열로만 응답하세요:
[
  {{
    "cluster_name": "클러스터 이름 (위 목록과 정확히 동일하게)",
    "is_project": true,
    "parent": null
  }},
  {{
    "cluster_name": "클러스터 이름",
    "is_project": false,
    "parent": "부모 클러스터 이름 또는 null"
  }}
]

전체 클러스터 이름 목록: {json.dumps(cluster_names, ensure_ascii=False)}
"""
            }]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.rsplit("```", 1)[0].strip()

        hierarchy = json.loads(text)

        # 검증: cluster_name이 실제 목록에 있는지 확인
        valid_names = set(cluster_names)
        for item in hierarchy:
            if item.get("parent") and item["parent"] not in valid_names:
                item["parent"] = None  # 잘못된 parent는 null 처리

        return hierarchy
