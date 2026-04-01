'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { fetchNotionPages, fetchSlackChannels } from '@/lib/api'
import { SourceSelector } from '@/components/SourceSelector'
import type { NotionPage, SlackChannel } from '@/lib/types'

export default function SelectPage() {
  const router = useRouter()
  const [notionPages, setNotionPages] = useState<NotionPage[]>([])
  const [slackChannels, setSlackChannels] = useState<SlackChannel[]>([])
  const [selectedNotion, setSelectedNotion] = useState<string[]>([])
  const [selectedSlack, setSelectedSlack] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const tokens = JSON.parse(sessionStorage.getItem('tokens') ?? '{}')
    if (!tokens.notion_token && !tokens.slack_token) {
      router.replace('/')
      return
    }

    async function load() {
      try {
        if (tokens.notion_token) {
          const pages = await fetchNotionPages(tokens.notion_token)
          setNotionPages(pages)
        }
        if (tokens.slack_token) {
          const channels = await fetchSlackChannels(tokens.slack_token)
          setSlackChannels(channels)
        }
      } catch {
        setError('데이터 불러오기 실패. 토큰을 확인해주세요.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [router])

  function handleNext() {
    const selection = {
      selectedNotion,
      selectedSlack,
    }
    sessionStorage.setItem('selection', JSON.stringify(selection))
    router.push('/structure')
  }

  if (loading) return <p className="text-gray-500">불러오는 중...</p>

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">마이그레이션 소스 선택</h1>
        <p className="text-gray-500 mt-1">Obsidian으로 옮길 항목을 선택하세요</p>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      <div className="space-y-6">
        {notionPages.length > 0 && (
          <SourceSelector
            title="Notion 페이지"
            items={notionPages.map(p => ({ id: p.id, name: p.title }))}
            selected={selectedNotion}
            onChange={setSelectedNotion}
          />
        )}
        {slackChannels.length > 0 && (
          <SourceSelector
            title="Slack 채널"
            items={slackChannels.map(c => ({ id: c.id, name: `#${c.name}` }))}
            selected={selectedSlack}
            onChange={setSelectedSlack}
          />
        )}
      </div>

      <button
        onClick={handleNext}
        disabled={selectedNotion.length === 0 && selectedSlack.length === 0}
        className="w-full bg-black text-white rounded-lg py-3 font-medium disabled:opacity-50"
      >
        다음: 폴더 구조 설정 →
      </button>
    </div>
  )
}
