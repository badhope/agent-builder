export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

export function formatFormatName(fmt: string): string {
  return fmt.toUpperCase()
}

export function getStateLabel(state: string): string {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '转换中',
    succeeded: '已完成',
    failed: '失败',
    cancelled: '已取消',
    expired: '已过期',
    paused: '已暂停'
  }
  return map[state] || state
}

export function getStateBadgeClass(state: string): string {
  const map: Record<string, string> = {
    queued: 'badge-yellow',
    running: 'badge-blue',
    succeeded: 'badge-green',
    failed: 'badge-red',
    cancelled: 'badge-gray',
    expired: 'badge-gray',
    paused: 'badge-yellow'
  }
  return map[state] || 'badge-gray'
}