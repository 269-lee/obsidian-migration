'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { FolderEditor } from '@/components/FolderEditor'

const DEFAULT_FOLDERS = ['Projects', 'Areas', 'Resources', 'Inbox']

export default function StructurePage() {
  const router = useRouter()
  const [folders, setFolders] = useState<string[]>(DEFAULT_FOLDERS)

  function handleNext() {
    sessionStorage.setItem('folder_structure', JSON.stringify(folders))
    router.push('/migrate')
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold">폴더 구조 설정</h1>
        <p className="text-gray-500 mt-1">
          Obsidian vault의 폴더 구조입니다. Claude가 각 노트를 알맞은 폴더에 분류합니다.
        </p>
      </div>

      <div className="bg-gray-50 rounded-lg p-4">
        <p className="text-sm text-gray-500 mb-3">
          기본값은 PARA 방법론입니다. 자유롭게 수정하세요.
        </p>
        <FolderEditor folders={folders} onChange={setFolders} />
      </div>

      <div className="text-sm text-gray-400 space-y-1">
        <p><strong>Projects</strong> — 현재 진행 중인 작업</p>
        <p><strong>Areas</strong> — 지속 관리 영역 (팀, 건강, 재무 등)</p>
        <p><strong>Resources</strong> — 주제별 참고자료</p>
        <p><strong>Inbox</strong> — 분류 전 임시 보관</p>
      </div>

      <button
        onClick={handleNext}
        disabled={folders.length === 0}
        className="w-full bg-black text-white rounded-lg py-3 font-medium disabled:opacity-50"
      >
        마이그레이션 시작 →
      </button>
    </div>
  )
}
