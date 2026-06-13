'use client'

import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { Send, Loader2, FlaskConical } from 'lucide-react'
import { postChat, type Message } from '@/lib/api'
import MessageBubble from './MessageBubble'

/** Main chat experience: input, message list, loading + error handling. */
export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  async function send() {
    const query = inputValue.trim()
    if (!query || isLoading) return

    setMessages((m) => [...m, { role: 'user', content: query }])
    setInputValue('')
    setIsLoading(true)

    try {
      const res = await postChat(query)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          chunks: res.retrieved_chunks,
          latency: res.latency,
          modelUsed: res.model_used,
        },
      ])
    } catch (err: unknown) {
      let detail = 'Request failed. Is the backend running on :8000?'
      if (axios.isAxiosError(err)) {
        detail = err.response?.data?.detail || err.message
      }
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: detail, error: true },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-navy-light px-5 py-3">
        <FlaskConical className="h-5 w-5 text-bio-green" />
        <h1 className="font-mono text-lg font-bold text-white">BioBot</h1>
        <span className="font-mono text-xs text-gray-400">Biology RAG Assistant</span>
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="mt-10 text-center font-mono text-sm text-gray-500">
            Ask a biology question — e.g.{' '}
            <span className="text-bio-green">&quot;What is the function of mitochondria?&quot;</span>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {isLoading && (
          <div className="flex items-center gap-2 font-mono text-sm text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin text-bio-green" />
            Retrieving, reranking and generating…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div className="border-t border-navy-light p-4">
        <div className="flex items-end gap-2">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder="Ask a biology question…"
            className="flex-1 resize-none rounded-lg border border-navy-light bg-navy-card px-3 py-2 font-mono text-sm text-white outline-none focus:border-bio-green"
          />
          <button
            type="button"
            onClick={send}
            disabled={isLoading || !inputValue.trim()}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-bio-green text-navy transition hover:bg-bio-green-dark disabled:opacity-40"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  )
}
