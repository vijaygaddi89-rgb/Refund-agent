import React from 'react'
import ChatWindow from './components/ChatWindow.jsx'
import { useWebSocket } from './hooks/useWebSocket.js'
import './App.css'

/**
 * App
 * ─────────────────────────────────────────────────────────────────
 * Root layout: full-width chat interface
 */

export default function App() {
  const { messages, logs, sendMessage, isConnected, isLoading } = useWebSocket()

  return (
    <div className="app-layout">
      <ChatWindow
        messages={messages}
        logs={logs}
        isLoading={isLoading}
        onSend={sendMessage}
        isConnected={isConnected}
      />
    </div>
  )
}
