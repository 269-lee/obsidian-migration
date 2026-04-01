export async function selectVaultFolder(): Promise<FileSystemDirectoryHandle> {
  if (!('showDirectoryPicker' in window)) {
    throw new Error('이 브라우저는 File System Access API를 지원하지 않습니다. Chrome 또는 Edge를 사용해주세요.')
  }
  return await (window as any).showDirectoryPicker({ mode: 'readwrite' })
}

export async function writeMarkdownFile(
  dirHandle: FileSystemDirectoryHandle,
  filePath: string,
  content: string
): Promise<void> {
  const parts = filePath.split('/')
  const filename = parts.pop()!

  let currentDir = dirHandle
  for (const part of parts) {
    currentDir = await currentDir.getDirectoryHandle(part, { create: true })
  }

  const fileHandle = await currentDir.getFileHandle(filename, { create: true })
  const writable = await fileHandle.createWritable()
  await writable.write(content)
  await writable.close()
}
