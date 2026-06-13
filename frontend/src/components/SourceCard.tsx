'use client'

import { useState } from 'react'
import { FileText, ChevronDown, ChevronRight } from 'lucide-react'
import type { RetrievedChunk, Citation } from '@/lib/api'

interface SourceCardProps {
  filename: string
  page: number
  score?: number
  text?: string
}

/** A single citation or retrieved chunk: filename + page badge + score bar. */
export default function SourceCard({ filename, page, score, text }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false)
  const pct = score !== undefined ? Math.max(0, Math.min(1, score)) * 100 : null

  return (
    <div className="rounded-md border border-navy-light bg-navy-card p-2 text-xs">
      <button
        type="button"
        onClick={() => text && setExpanded((e) => !e)}
        className="flex w-full items-center gap-2 text-left"
      >
        {text ? (
          expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-bio-green" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-bio-green" />
          )
        ) : (
          <FileText className="h-3.5 w-3.5 text-bio-green" />
        )}
        <span className="truncate font-mono text-white">{filename}</span>
        <span className="ml-auto whitespace-nowrap rounded bg-bio-green/10 px-1.5 py-0.5 font-mono text-bio-green">
          Page {page}
        </span>
      </button>

      {pct !== null && (
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded bg-navy-light">
          <div className="h-full bg-bio-green" style={{ width: `${pct}%` }} />
        </div>
      )}

      {expanded && text && (
        <p className="mt-2 font-mono leading-relaxed text-gray-300">
          {text.slice(0, 200)}
          {text.length > 200 ? '…' : ''}
        </p>
      )}
    </div>
  )
}

/** Helper to build a SourceCard from a Citation. */
export function CitationCard({ citation }: { citation: Citation }) {
  return <SourceCard filename={citation.source_file} page={citation.page_number} />
}

/** Helper to build a SourceCard from a retrieved chunk. */
export function ChunkCard({ chunk }: { chunk: RetrievedChunk }) {
  return (
    <SourceCard
      filename={chunk.source_file}
      page={chunk.page_number}
      score={chunk.rerank_score}
      text={chunk.text}
    />
  )
}
