'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { selectVaultFolder, writeMarkdownFile } from '@/lib/filesystem'
import { MigrationProgress } from '@/components/MigrationProgress'
import type { MigrationEvent } from '@/lib/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Status = 'idle' | 'selecting' | 'running' | 'done' | 'error'

export default function MigratePage() {
  const router = useRouter()
  const [status, setStatus] = useState<Status>('idle')
  const [percent, setPercent] = useState(0)
  const [message, setMessage] = useState('')
  const [filesWritten, setFilesWritten] = useState(0)
  const [error, setError] = useState('')

  async function handleStart() {
    setStatus('selecting')
    let dirHandle: FileSystemDirectoryHandle
    try {
      dirHandle = await selectVaultFolder()
    } catch {
      setStatus('idle')
      return
    }

    const tokens = JSON.parse(sessionStorage.getItem('tokens') ?? '{}')
    const selection = JSON.parse(sessionStorage.getItem('selection') ?? '{}')
    const folderStructure = JSON.parse(sessionStorage.getItem('folder_structure') ?? '["Projects","Areas","Resources","Inbox"]')

    const body = {
      claude_api_key: tokens.claude_api_key ?? '',
      notion_token: tokens.notion_token,
      notion_page_ids: selection.selectedNotion ?? [],
      slack_token: tokens.slack_token,
      slack_channel_ids: selection.selectedSlack ?? [],
      google_doc_ids: [],
      folder_structure: folderStructure,
    }

    setStatus('running')
    setPercent(0)
    setFilesWritten(0)

    try {
      const res = await fetch(`${API_URL}/api/migrate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.body) throw new Error('스트림 없음')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const event: MigrationEvent = JSON.parse(line.slice(6))

          if (event.type === 'progress') {
            setPercent(event.percent)
            setMessage(event.message)
          } else if (event.type === 'file') {
            await writeMarkdownFile(dirHandle!, event.path, event.content)
            setFilesWritten(n => n + 1)
          } else if (event.type === 'done') {
            setPercent(100)
            setMessage(event.message)
            setStatus('done')
          } else if (event.type === 'error') {
            throw new Error(event.message)
          }
        }
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '마이그레이션 실패'
      setError(msg)
      setStatus('error')
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">마이그레이션</h1>
        <p className="text-gray-500 mt-1">Obsidian vault 폴더를 선택하면 시작됩니다</p>
      </div>

      {status === 'idle' && (
        <button
          onClick={handleStart}
          className="w-full bg-black text-white rounded-lg py-3 font-medium"
        >
          vault 폴더 선택 후 시작
        </button>
      )}

      {status === 'selecting' && (
        <p className="text-gray-500 text-center">폴더를 선택해주세요...</p>
      )}

      {(status === 'running' || status === 'done') && (
        <MigrationProgress percent={percent} message={message} filesWritten={filesWritten} />
      )}

      {status === 'done' && (
        <div className="space-y-3">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-800">
            완료! Obsidian에서 vault를 열어 확인하세요.
          </div>
          <button
            onClick={() => router.push('/')}
            className="w-full border rounded-lg py-3 text-sm"
          >
            처음으로
          </button>
        </div>
      )}

      {status === 'error' && (
        <div className="space-y-3">
          <p className="text-red-500 text-sm">{error}</p>
          <button
            onClick={() => setStatus('idle')}
            className="w-full border rounded-lg py-3 text-sm"
          >
            다시 시도
          </button>
        </div>
      )}
    </div>
  )
}
