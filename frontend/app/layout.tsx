import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Obsidian Migration',
  description: '당신의 지식을 Obsidian으로',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <main className="max-w-2xl mx-auto px-4 py-12">
          {children}
        </main>
      </body>
    </html>
  )
}
