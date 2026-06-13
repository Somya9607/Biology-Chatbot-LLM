'use client'

import { useEffect, useRef, useState } from 'react'
import { UploadCloud, FolderInput, Loader2 } from 'lucide-react'
import {
  getIngestStatus,
  ingestFiles,
  ingestFromDirectory,
  type IngestFileResult,
} from '@/lib/api'

function statusColor(status: string) {
  if (status === 'indexed') return 'text-bio-green'
  if (status === 'skipped') return 'text-yellow-400'
  return 'text-red-400'
}

/** PDF ingestion: drag-and-drop upload + server-directory ingest + status. */
export default function IngestionPanel() {
  const [results, setResults] = useState<IngestFileResult[]>([])
  const [busy, setBusy] = useState(false)
  const [summary, setSummary] = useState<string>('')
  const [docCount, setDocCount] = useState<number>(0)
  const [chunkCount, setChunkCount] = useState<number>(0)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function refreshStatus() {
    try {
      const s = await getIngestStatus()
      setDocCount(s.indexed_documents.length)
      setChunkCount(s.total_chunks_in_db)
    } catch {
      /* backend may be down */
    }
  }

  useEffect(() => {
    refreshStatus()
  }, [])

  async function run(promise: Promise<{ results: IngestFileResult[]; total_indexed: number; total_skipped: number; total_errors: number }>) {
    setBusy(true)
    try {
      const res = await promise
      setResults(res.results)
      setSummary(`${res.total_indexed} indexed · ${res.total_skipped} skipped · ${res.total_errors} errors`)
      await refreshStatus()
    } catch {
      setSummary('Ingestion request failed — is the backend running?')
    } finally {
      setBusy(false)
    }
  }

  function onFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    const pdfs = Array.from(files).filter((f) => f.name.toLowerCase().endsWith('.pdf'))
    if (pdfs.length) run(ingestFiles(pdfs))
  }

  return (
    <div className="rounded-lg border border-navy-light bg-navy-card p-3">
      <div className="mb-2 flex items-center gap-1.5">
        <UploadCloud className="h-4 w-4 text-bio-green" />
        <h2 className="font-mono text-sm font-bold">Ingestion</h2>
      </div>

      <p className="mb-2 font-mono text-xs text-gray-400">
        {docCount} docs · {chunkCount} chunks indexed
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          onFiles(e.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
        className={`mb-2 cursor-pointer rounded-md border border-dashed p-3 text-center font-mono text-xs transition ${
          dragging ? 'border-bio-green bg-bio-green/10' : 'border-navy-light text-gray-400'
        }`}
      >
        Drop PDFs here or click to upload
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          className="hidden"
          onChange={(e) => onFiles(e.target.files)}
        />
      </div>

      <button
        type="button"
        onClick={() => run(ingestFromDirectory())}
        disabled={busy}
        className="mb-2 flex w-full items-center justify-center gap-1.5 rounded-md bg-navy-light py-1.5 font-mono text-xs text-bio-green hover:bg-navy disabled:opacity-50"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FolderInput className="h-3.5 w-3.5" />}
        Ingest server directory
      </button>

      {summary && <p className="mb-1 font-mono text-xs text-gray-300">{summary}</p>}

      {results.length > 0 && (
        <ul className="max-h-40 space-y-1 overflow-y-auto">
          {results.map((r, i) => (
            <li key={i} className="flex items-center justify-between font-mono text-[11px]">
              <span className="truncate text-gray-300" title={r.filename}>
                {r.filename}
              </span>
              <span className={`ml-2 whitespace-nowrap ${statusColor(r.status)}`}>
                {r.status} {r.chunks_created > 0 ? `(${r.chunks_created})` : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
