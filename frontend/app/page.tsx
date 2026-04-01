'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function ConnectPage() {
  const router = useRouter()
  const [claudeApiKey, setClaudeApiKey] = useState('')
  const [notionToken, setNotionToken] = useState('')
  const [slackToken, setSlackToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleConnect() {
    if (!claudeApiKey) {
      setError('Claude API 키를 입력해주세요.')
      return
    }
    if (!notionToken && !slackToken) {
      setError('최소 하나의 툴을 연결해주세요.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const tokens: Record<string, string> = { claude_api_key: claudeApiKey }
      if (notionToken) tokens.notion_token = notionToken
      if (slackToken) tokens.slack_token = slackToken
      sessionStorage.setItem('tokens', JSON.stringify(tokens))
      router.push('/select')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Obsidian Migration</h1>
        <p className="text-gray-500 mt-1">툴을 연결하고 Obsidian vault로 지식을 이전하세요</p>
      </div>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Claude API Key</label>
          <input
            type="password"
            value={claudeApiKey}
            onChange={e => setClaudeApiKey(e.target.value)}
            placeholder="sk-ant-..."
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-400 mt-1">console.anthropic.com 에서 발급 — 서버에 저장되지 않습니다</p>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Notion Integration Token</label>
          <input
            type="password"
            value={notionToken}
            onChange={e => setNotionToken(e.target.value)}
            placeholder="secret_..."
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-400 mt-1">notion.so/my-integrations 에서 발급</p>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Slack Bot Token</label>
          <input
            type="password"
            value={slackToken}
            onChange={e => setSlackToken(e.target.value)}
            placeholder="xoxb-..."
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
          <p className="text-xs text-gray-400 mt-1">api.slack.com/apps 에서 발급</p>
        </div>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <button
        onClick={handleConnect}
        disabled={loading}
        className="w-full bg-black text-white rounded-lg py-3 font-medium disabled:opacity-50"
      >
        {loading ? '연결 중...' : '연결하고 소스 선택 →'}
      </button>
    </div>
  )
}
