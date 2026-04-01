const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function fetchNotionPages(token: string) {
  const res = await fetch(`${BASE_URL}/api/sources/notion/pages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!res.ok) throw new Error('Notion 페이지 목록 조회 실패')
  return res.json()
}

export async function fetchSlackChannels(token: string) {
  const res = await fetch(`${BASE_URL}/api/sources/slack/channels`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!res.ok) throw new Error('Slack 채널 목록 조회 실패')
  return res.json()
}

export async function fetchGoogleDocs(credentials: Record<string, string>) {
  const res = await fetch(`${BASE_URL}/api/sources/google/docs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credentials }),
  })
  if (!res.ok) throw new Error('Google Docs 목록 조회 실패')
  return res.json()
}
