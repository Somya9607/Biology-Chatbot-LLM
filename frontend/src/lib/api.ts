import axios from 'axios'

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
    // Skip ngrok's free-tier browser-warning interstitial so API calls
    // receive JSON instead of an HTML warning page.
    'ngrok-skip-browser-warning': 'true',
  },
})

// --- Shared types ----------------------------------------------------------
export interface Citation {
  source_file: string
  page_number: number
}

export interface RetrievedChunk {
  text: string
  source_file: string
  page_number: number
  vector_score: number
  rerank_score: number
  rank: number
}

export interface Latency {
  retrieval_ms: number
  reranking_ms: number
  generation_ms: number
  total_ms: number
}

export interface ChatResponse {
  answer: string
  citations: Citation[]
  retrieved_chunks: RetrievedChunk[]
  latency: Latency
  model_used: string
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  chunks?: RetrievedChunk[]
  latency?: Latency
  modelUsed?: string
  error?: boolean
}

export interface ComponentHealth {
  status: 'ok' | 'error' | 'degraded'
  [key: string]: unknown
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error'
  components: {
    vector_db: ComponentHealth
    llm: ComponentHealth
    ocr: ComponentHealth
    embedding: ComponentHealth
  }
}

export interface MetricsResponse {
  query_count: number
  avg_latency_ms: number
  p95_latency_ms: number
  error_count: number
  error_rate: number
}

export interface IngestFileResult {
  filename: string
  status: 'indexed' | 'skipped' | 'error'
  chunks_created: number
  message: string
}

export interface IngestResponse {
  results: IngestFileResult[]
  total_indexed: number
  total_skipped: number
  total_errors: number
  elapsed_seconds: number
}

export interface IngestStatusResponse {
  indexed_documents: Array<Record<string, unknown>>
  total_chunks_in_db: number
}

// --- API calls -------------------------------------------------------------
export async function postChat(query: string): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>('/chat', {
    query,
    top_k: 10,
    top_k_rerank: 4,
  })
  return data
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}

export async function getMetrics(): Promise<MetricsResponse> {
  const { data } = await api.get<MetricsResponse>('/metrics')
  return data
}

export async function getIngestStatus(): Promise<IngestStatusResponse> {
  const { data } = await api.post<IngestStatusResponse>('/ingest/status')
  return data
}

export async function ingestFromDirectory(pdfDir?: string): Promise<IngestResponse> {
  const { data } = await api.post<IngestResponse>('/ingest', { pdf_dir: pdfDir ?? null })
  return data
}

export async function ingestFiles(files: File[]): Promise<IngestResponse> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const { data } = await api.post<IngestResponse>('/ingest', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
