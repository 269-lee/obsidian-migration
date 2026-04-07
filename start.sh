#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# .env 없으면 안내
if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "⚠️  backend/.env 파일이 없습니다. backend/.env.example을 복사해서 API 키를 입력해주세요."
  echo "   cp backend/.env.example backend/.env"
  exit 1
fi

echo "🚀 백엔드 시작 중..."
cd "$BACKEND_DIR"
source venv/Scripts/activate
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo "🚀 프론트엔드 시작 중..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

# 프론트엔드 뜰 때까지 대기 후 브라우저 오픈
echo "⏳ 서버 준비 중..."
sleep 4
echo "🌐 브라우저 열기..."
start http://localhost:3000

echo ""
echo "✅ 실행 중 (종료: Ctrl+C)"
echo "   백엔드: http://localhost:8000"
echo "   프론트: http://localhost:3000"

# Ctrl+C 시 두 프로세스 모두 종료
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '👋 종료'" INT
wait
