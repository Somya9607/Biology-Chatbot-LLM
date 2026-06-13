'use client'

import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { AlertTriangle, Clock } from 'lucide-react'
import type { Message } from '@/lib/api'
import { CitationCard } from './SourceCard'
import RetrievedChunks from './RetrievedChunks'

/** Renders a single chat message (user or assistant). */
export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-bio-green px-4 py-2 text-navy">
          <p className="whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[90%] rounded-2xl rounded-bl-sm border border-navy-light bg-navy-card px-4 py-3">
        {message.error ? (
          <div className="flex items-start gap-2 text-red-400">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        ) : (
          <div className="prose prose-invert max-w-none prose-p:my-2 prose-headings:text-bio-green">
            <ReactMarkdown
              components={{
                code({ inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '')
                  return !inline && match ? (
                    <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div" {...props}>
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  ) : (
                    <code className="rounded bg-navy-light px-1 font-mono text-bio-green" {...props}>
                      {children}
                    </code>
                  )
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3">
            <p className="mb-1 font-mono text-xs uppercase tracking-wide text-gray-400">Sources</p>
            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {message.citations.map((c, i) => (
                <CitationCard key={i} citation={c} />
              ))}
            </div>
          </div>
        )}

        {/* Latency chips */}
        {message.latency && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-gray-400" />
            <span className="chip">retrieval {message.latency.retrieval_ms.toFixed(0)}ms</span>
            <span className="chip">rerank {message.latency.reranking_ms.toFixed(0)}ms</span>
            <span className="chip">llm {message.latency.generation_ms.toFixed(0)}ms</span>
            <span className="chip font-bold">total {message.latency.total_ms.toFixed(0)}ms</span>
            {message.modelUsed && <span className="chip">{message.modelUsed}</span>}
          </div>
        )}

        {/* Retrieved chunks */}
        {message.chunks && <RetrievedChunks chunks={message.chunks} />}
      </div>
    </div>
  )
}
