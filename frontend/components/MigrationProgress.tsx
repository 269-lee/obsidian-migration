interface Props {
  percent: number
  message: string
  filesWritten: number
}

export function MigrationProgress({ percent, message, filesWritten }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex justify-between text-sm">
        <span className="text-gray-600">{message}</span>
        <span className="font-medium">{percent}%</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div
          className="bg-black h-2 rounded-full transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
      {filesWritten > 0 && (
        <p className="text-xs text-gray-400">{filesWritten}개 파일 저장됨</p>
      )}
    </div>
  )
}
