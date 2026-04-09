# Backend API 스펙

FastAPI 기반 v1 웹 API (`backend/main.py`).
v2 CLI 파이프라인(`run_migration.py`)과는 별개.

## 주요 엔드포인트

### POST /upload
- 파일 업로드 또는 API 키 입력
- Body: `{ notion_token, slack_token, anthropic_key, pages, channels }`

### POST /migrate
- 마이그레이션 실행 시작
- SSE(Server-Sent Events)로 진행상황 스트리밍
- Response: `text/event-stream`

### GET /status
- 현재 마이그레이션 상태 조회
- Response: `{ status, progress, current_step, error }`

### GET /download
- 완료된 결과 ZIP 다운로드
- Response: `application/zip`

## SSE 스트리밍 방식
```python
async def event_generator():
    yield f"data: {json.dumps({'step': '수집 중...', 'progress': 10})}\n\n"
```

## 에러 처리
- API 키 누락: 400
- 외부 API 실패: 502 + 재시도 정보 포함
- 마이그레이션 실패: 500 + 로그 위치 안내
