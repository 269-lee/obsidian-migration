# 캐시 프로토콜

CLAUDE.md "API 비용 관련 개발 원칙"의 구현 세부사항.

## 캐시 파일 스키마

### cache_notion.json
```json
[
  {
    "page_id": "abc-123-def",   // ← dedup key (필수, 고유)
    "title": "프로젝트 A",
    "content": "# 마크다운 내용",
    "properties": { "project": "맞추다 실기 확장" },
    "source": "notion"
  }
]
```

### cache_slack.json
```json
[
  {
    "ts": "1234567890.123456",  // ← dedup key (필수, 고유)
    "channel": "C01234ABCDE",
    "text": "메인 메시지",
    "replies": [{ "ts": "...", "text": "답글" }],
    "source": "slack"
  }
]
```

### cache_chunks.json
```json
{
  "abc-123-def": [             // ← page_id 또는 ts를 key로 사용
    { "content": "chunk 내용", "topic": "주제명" }
  ]
}
```

### cache_clusters.json
```json
{
  "cluster_0": {
    "topic": "맞추다 실기 확장",
    "chunks": [...],
    "sources": ["notion", "slack"]
  }
}
```

### cache_synthesis.json
```json
{
  "cluster_0": "# 맞추다 실기 확장\n\n합성된 노트 내용..."
}
```

## dedup Key 규칙

| 소스 | 올바른 key | 잘못된 key |
|------|-----------|-----------|
| Notion | `page_id` | `title` (Untitled 중복 가능) |
| Slack | `channel_ts` | `text[:20]` (동일 텍스트 가능) |
| chunk | `{page_id}_{chunk_index}` | `topic` (중복 가능) |

## 증분 저장 패턴

```python
# 올바른 패턴: 항목 1개 완료마다 즉시 저장
for doc in documents:
    result = await process(doc)
    cache[doc["page_id"]] = result   # dedup key = page_id
    with open(cache_file, "w") as f:
        json.dump(cache, f, ensure_ascii=False)  # 즉시 저장

# 잘못된 패턴: 전체 완료 후 한 번에 저장 (중간 실패 시 전액 재과금)
results = await process_all(documents)
save_cache(results)  # ❌
```

## 정기 정리 일정
- 매주 일요일 00:00 UTC: GitHub Actions `cleanup.yml` 실행
- 캐시 보관 기간: 7일
- 아카이브 보관 기간: 30일
- 수동 실행: `python backend/scripts/cleanup.py`
- 삭제 전 확인: `python backend/scripts/cleanup.py --dry-run`
