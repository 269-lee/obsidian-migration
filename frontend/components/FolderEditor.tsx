'use client'
import { useState } from 'react'

interface Props {
  folders: string[]
  onChange: (folders: string[]) => void
}

export function FolderEditor({ folders, onChange }: Props) {
  const [newFolder, setNewFolder] = useState('')

  function add() {
    const trimmed = newFolder.trim()
    if (!trimmed || folders.includes(trimmed)) return
    onChange([...folders, trimmed])
    setNewFolder('')
  }

  function remove(folder: string) {
    onChange(folders.filter(f => f !== folder))
  }

  function rename(index: number, value: string) {
    const updated = [...folders]
    updated[index] = value
    onChange(updated)
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {folders.map((folder, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="text-gray-400">📁</span>
            <input
              value={folder}
              onChange={e => rename(i, e.target.value)}
              className="flex-1 border rounded px-2 py-1 text-sm"
            />
            <button
              onClick={() => remove(folder)}
              className="text-red-400 hover:text-red-600 text-sm px-2"
            >
              삭제
            </button>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          value={newFolder}
          onChange={e => setNewFolder(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder="새 폴더 이름"
          className="flex-1 border rounded px-2 py-1 text-sm"
        />
        <button
          onClick={add}
          className="border rounded px-3 py-1 text-sm hover:bg-gray-50"
        >
          추가
        </button>
      </div>
    </div>
  )
}
