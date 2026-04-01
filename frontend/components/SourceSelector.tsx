interface Item {
  id: string
  name: string
}

interface Props {
  title: string
  items: Item[]
  selected: string[]
  onChange: (ids: string[]) => void
}

export function SourceSelector({ title, items, selected, onChange }: Props) {
  function toggle(id: string) {
    onChange(
      selected.includes(id) ? selected.filter(s => s !== id) : [...selected, id]
    )
  }

  function toggleAll() {
    onChange(selected.length === items.length ? [] : items.map(i => i.id))
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-medium">{title}</h3>
        <button onClick={toggleAll} className="text-xs text-blue-600">
          {selected.length === items.length ? '전체 해제' : '전체 선택'}
        </button>
      </div>
      <div className="space-y-1 max-h-48 overflow-y-auto border rounded-lg p-2">
        {items.length === 0 && (
          <p className="text-sm text-gray-400 py-2 text-center">항목 없음</p>
        )}
        {items.map(item => (
          <label key={item.id} className="flex items-center gap-2 px-2 py-1 hover:bg-gray-50 rounded cursor-pointer">
            <input
              type="checkbox"
              checked={selected.includes(item.id)}
              onChange={() => toggle(item.id)}
              className="rounded"
            />
            <span className="text-sm">{item.name}</span>
          </label>
        ))}
      </div>
      <p className="text-xs text-gray-400 mt-1">{selected.length}개 선택됨</p>
    </div>
  )
}
