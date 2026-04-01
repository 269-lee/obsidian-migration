export interface NotionPage {
  id: string
  title: string
}

export interface SlackChannel {
  id: string
  name: string
}

export interface GoogleDoc {
  id: string
  name: string
}

export interface SourceSelection {
  notion_token?: string
  notion_page_ids: string[]
  slack_token?: string
  slack_channel_ids: string[]
  google_credentials?: Record<string, string>
  google_doc_ids: string[]
  folder_structure: string[]
}

export type MigrationEvent =
  | { type: 'progress'; message: string; percent: number }
  | { type: 'file'; path: string; content: string }
  | { type: 'done'; message: string; percent: number; total: number }
  | { type: 'error'; message: string }
