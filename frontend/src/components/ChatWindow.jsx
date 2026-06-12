import React, { useEffect, useRef, useState } from 'react'
import MessageBubble from './MessageBubble.jsx'

/**
 * ChatWindow
 * ─────────────────────────────────────────────────────────────────
 * Customer-facing chat panel. Displays messages and input bar.
 *
 * Props:
 *   messages   – array of message objects
 *   isLoading  – bool: agent is thinking
 *   onSend     – fn(text: string)
 *   isConnected – bool
 */

const QUICK_PROMPTS = [
  { label: '🎧 Defective headphones', text: 'Hi! I need to return my order ORD-2026-001. The wireless headphones arrived with a broken headband and one ear cup doesn\'t work.' },
  { label: '💿 Digital product denial', text: 'I want a refund for my Adobe Creative Suite license, order ORD-2026-007. I didn\'t use it much.' },
  { label: '⏰ Expired window', text: 'My yoga mat from order ORD-2026-002 is terrible quality. I want my money back.' },
  { label: '🪑 Clearance item', text: 'I want to return the winter jacket I bought on clearance, order ORD-2026-008.' },
]

export default function ChatWindow({ messages, isLoading, onSend, isConnected }) {
  const [input, setInput]       = useState('')
  const bottomRef               = useRef(null)
  const textareaRef             = useRef(null)

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSend = () => {
    const text = input.trim()
    if (!text || isLoading) return
    onSend(text)
    setInput('')
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="chat-window glass">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-header__left">
          <div className="chat-header__logo">🛒</div>
          <div>
            <h1 className="chat-header__title">ShopEasy Support</h1>
            <p className="chat-header__subtitle">AI Refund Agent</p>
          </div>
        </div>
        <div className="chat-header__status">
          <span className={`status-dot ${isConnected ? 'status-dot--online' : 'status-dot--offline'}`} />
          <span>{isConnected ? 'Live' : 'Reconnecting...'}</span>
        </div>
      </div>

      {/* Messages area */}
      <div className="chat-messages">
        {isEmpty ? (
          <div className="chat-empty">
            <div className="chat-empty__icon">🤖</div>
            <h2 className="chat-empty__title">Hello! I'm RefundBot</h2>
            <p className="chat-empty__desc">
              I can help you with refund requests for your ShopEasy orders.<br />
              Please share your order ID or email to get started.
            </p>

            {/* Quick prompt buttons */}
            <div className="chat-quick-prompts">
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Try a scenario:
              </p>
              {QUICK_PROMPTS.map((qp) => (
                <button
                  key={qp.label}
                  className="quick-prompt-btn"
                  onClick={() => { onSend(qp.text) }}
                >
                  {qp.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Typing indicator */}
            {isLoading && (
              <div className="msg-row msg-row--ai fade-in-up">
                <div className="msg-avatar msg-avatar--ai">🤖</div>
                <div className="msg-bubble msg-bubble--ai" style={{ padding: '14px 18px' }}>
                  <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <div className="typing-dot" />
                    <span style={{ marginLeft: 6, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Analyzing your request...
                    </span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="Describe your issue or paste your order ID..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={isLoading}
          style={{ resize: 'none' }}
        />
        <button
          className={`chat-send-btn ${isLoading || !input.trim() ? 'chat-send-btn--disabled' : ''}`}
          onClick={handleSend}
          disabled={isLoading || !input.trim()}
          title="Send message (Enter)"
        >
          {isLoading ? (
            <span className="spinner" />
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
    </div>
  )
}
