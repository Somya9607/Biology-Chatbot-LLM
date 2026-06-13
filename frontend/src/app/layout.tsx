import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'BioBot — Biology RAG Chatbot',
  description: 'Local, open-source Retrieval-Augmented Generation over biology textbooks.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-navy text-white antialiased">{children}</body>
    </html>
  )
}
