import ChatInterface from '@/components/ChatInterface'
import HealthStatus from '@/components/HealthStatus'
import IngestionPanel from '@/components/IngestionPanel'
import MetricsPanel from '@/components/MetricsPanel'

export default function Home() {
  return (
    <main className="flex h-screen flex-col gap-3 p-3 md:flex-row">
      {/* Left sidebar */}
      <aside className="flex w-full flex-col gap-3 md:w-72 md:shrink-0">
        <HealthStatus />
        <IngestionPanel />
        <MetricsPanel />
      </aside>

      {/* Chat */}
      <section className="flex-1 overflow-hidden rounded-lg border border-navy-light bg-navy">
        <ChatInterface />
      </section>
    </main>
  )
}
