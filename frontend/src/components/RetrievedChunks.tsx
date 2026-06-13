'use client'

import { useState } from 'react'
import { Layers, ChevronDown, ChevronRight } from 'lucide-react'
import type { RetrievedChunk } from '@/lib/api'

/** Expandable panel listing the top-K retrieved + reranked chunks. */
export default function RetrievedChunks({ chunks }: { chunks: RetrievedChunk[] }) {
  const [open, setOpen] = useState(false)
  if (!chunks || chunks.length === 0) return null

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 font-mono text-xs text-bio-green hover:underline"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <Layers className="h-3.5 w-3.5" />
        Show Sources ({chunks.length})
      </button>

      {open && (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="text-left text-gray-400">
                <th className="px-2 py-1">#</th>
                <th className="px-2 py-1">Source</th>
                <th className="px-2 py-1">Page</th>
                <th className="px-2 py-1">Vector</th>
                <th className="px-2 py-1">Rerank</th>
                <th className="px-2 py-1">Preview</th>
              </tr>
            </thead>
            <tbody>
              {chunks.map((c, i) => (
                <tr key={i} className="border-t border-navy-light align-top">
                  <td className="px-2 py-1 text-bio-green">{c.rank}</td>
                  <td className="px-2 py-1 text-white">{c.source_file}</td>
                  <td className="px-2 py-1">{c.page_number}</td>
                  <td className="px-2 py-1">{c.vector_score.toFixed(3)}</td>
                  <td className="px-2 py-1 text-bio-green">{c.rerank_score.toFixed(3)}</td>
                  <td className="px-2 py-1 text-gray-300">
                    {c.text.slice(0, 120)}
                    {c.text.length > 120 ? '…' : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
