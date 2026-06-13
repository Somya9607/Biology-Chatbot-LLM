'use client'

import { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
import { getHealth, type HealthResponse } from '@/lib/api'

const LABELS: Record<string, string> = {
  vector_db: 'Vector DB',
  llm: 'LLM',
  ocr: 'OCR',
  embedding: 'Embedding',
}

function dotColor(status?: string) {
  if (status === 'ok') return 'bg-bio-green'
  if (status === 'degraded') return 'bg-yellow-400'
  return 'bg-red-500'
}

/** System health indicators, auto-refreshing every 30s. */
export default function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [reachable, setReachable] = useState(true)

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const h = await getHealth()
        if (active) {
          setHealth(h)
          setReachable(true)
        }
      } catch {
        if (active) setReachable(false)
      }
    }
    poll()
    const id = setInterval(poll, 30000)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [])

  return (
    <div className="rounded-lg border border-navy-light bg-navy-card p-3">
      <div className="mb-2 flex items-center gap-1.5">
        <Activity className="h-4 w-4 text-bio-green" />
        <h2 className="font-mono text-sm font-bold">System Health</h2>
      </div>
      {!reachable ? (
        <p className="font-mono text-xs text-red-400">Backend unreachable (:8000)</p>
      ) : (
        <ul className="space-y-1.5">
          {Object.keys(LABELS).map((key) => {
            const status = health?.components?.[key as keyof HealthResponse['components']]?.status
            return (
              <li key={key} className="flex items-center justify-between font-mono text-xs">
                <span className="text-gray-300">{LABELS[key]}</span>
                <span className={`status-dot ${dotColor(status)}`} />
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
