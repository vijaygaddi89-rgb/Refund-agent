import React from 'react'

/**
 * MessageBubble
 * ─────────────────────────────────────────────────────────────────
 * Renders a single chat message with:
 *   - User messages: right-aligned, teal gradient
 *   - Assistant messages: left-aligned, glass card
 *   - Decision badge (approved / denied / escalated / partial)
 */

const DECISION_CONFIG = {
  approved:  { icon: '✓', label: 'Approved',  cls: 'approved'  },
  denied:    { icon: '✗', label: 'Denied',    cls: 'denied'    },
  escalated: { icon: '⬆', label: 'Escalated', cls: 'escalated' },
  partial:   { icon: '◑', label: 'Partial',   cls: 'partial'   },
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function MessageBubble({ message }) {
  const { role, content, decision, timestamp, isError } = message
  const isUser = role === 'user'
  const decisionCfg = decision ? DECISION_CONFIG[decision] : null

  return (
    <div className={`msg-row ${isUser ? 'msg-row--user' : 'msg-row--ai'} fade-in-up`}>
      {/* Avatar */}
      {!isUser && (
        <div className="msg-avatar msg-avatar--ai">
          🤖
        </div>
      )}

      <div className="msg-body">
        {/* Bubble */}
        <div className={`msg-bubble ${isUser ? 'msg-bubble--user' : 'msg-bubble--ai'} ${isError ? 'msg-bubble--error' : ''}`}>
          {/* Decision badge (shown above content for AI messages) */}
          {decisionCfg && (
            <div style={{ marginBottom: 8 }}>
              <span className={`badge badge--${decisionCfg.cls}`}>
                {decisionCfg.icon} {decisionCfg.label}
              </span>
            </div>
          )}

          {/* Message text - preserve newlines */}
          <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{content}</p>
        </div>

        {/* Timestamp */}
        <span className="msg-time">
          {formatTime(timestamp)}
        </span>
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="msg-avatar msg-avatar--user">
          U
        </div>
      )}
    </div>
  )
}
