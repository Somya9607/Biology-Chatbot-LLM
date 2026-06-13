'use client'

import { useEffect, useState } from 'react'
import { Gauge } from 'lucide-react'
import { getMetrics, type MetricsResponse } from '@/lib/api'

/** Live metrics panel, auto-refreshing every 10s. */
export default function MetricsPanel() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const m = await getMetrics()
        if (active) setMetrics(m)
      } catch {
        /* ignore transient errors */
      }
    }
    poll()
    const id = setInterval(poll, 10000)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [])

  const cells = [
    { label: 'Queries', value: metrics ? metrics.query_count : '—' },
    { label: 'Avg ms', value: metrics ? metrics.avg_latency_ms.toFixed(0) : '—' },
    { label: 'P95 ms', value: metrics ? metrics.p95_latency_ms.toFixed(0) : '—' },
    {
      label: 'Err rate',
      value: metrics ? `${(metrics.error_rate * 100).toFixed(1)}%` : '—',
    },
  ]

  return (
    <div className="rounded-lg border border-navy-light bg-navy-card p-3">
      <div className="mb-2 flex items-center gap-1.5">
        <Gauge className="h-4 w-4 text-bio-green" />
        <h2 className="font-mono text-sm font-bold">Metrics</h2>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {cells.map((c) => (
          <div key={c.label} className="rounded-md bg-navy-light p-2 text-center">
            <div className="font-mono text-lg font-bold text-bio-green">{c.value}</div>
            <div className="font-mono text-[10px] uppercase tracking-wide text-gray-400">
              {c.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
