import React, { useState } from 'react'

/**
 * LogEntry
 * ─────────────────────────────────────────────────────────────────
 * Renders a single agent reasoning step in the admin panel.
 * Each entry is collapsible and color-coded by tool type.
 */

const TOOL_CONFIG = {
  agent_thinking: {
    icon: '🧠',
    label: 'Agent Thinking',
    color: 'var(--accent-teal)',
    bg: 'var(--accent-teal-dim)',
  },
  lookup_customer: {
    icon: '🔍',
    label: 'Lookup Customer',
    color: 'var(--accent-purple)',
    bg: 'var(--accent-purple-dim)',
  },
  validate_policy: {
    icon: '📋',
    label: 'Validate Policy',
    color: 'var(--accent-amber)',
    bg: 'var(--accent-amber-dim)',
  },
  process_refund: {
    icon: '⚡',
    label: 'Process Refund',
    color: 'var(--accent-green)',
    bg: 'var(--accent-green-dim)',
  },
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

function JsonBlock({ data }) {
  if (data === null || data === undefined) return <span style={{ color: 'var(--text-muted)' }}>null</span>
  if (typeof data === 'string') {
    try {
      const parsed = JSON.parse(data)
      return (
        <pre style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-secondary)' }}>
          {JSON.stringify(parsed, null, 2)}
        </pre>
      )
    } catch {
      return <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{data}</span>
    }
  }
  return (
    <pre style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-secondary)' }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  )
}

export default function LogEntry({ entry, index }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = TOOL_CONFIG[entry.tool] || {
    icon: '⚙️', label: entry.tool, color: 'var(--text-secondary)', bg: 'rgba(255,255,255,0.05)'
  }

  // Determine if refund was approved or denied for special styling
  const output = entry.output
  const isApproved = output?.decision === 'approved' || output?.eligible === true
  const isDenied   = output?.decision === 'denied'   || output?.eligible === false

  return (
    <div
      className="log-entry fade-in-up"
      style={{
        borderLeft: `3px solid ${cfg.color}`,
        animationDelay: `${index * 0.04}s`,
        background: isDenied ? 'rgba(255,77,109,0.04)' : isApproved ? 'rgba(0,255,136,0.04)' : undefined,
      }}
    >
      {/* Header row */}
      <button className="log-entry__header" onClick={() => setExpanded(e => !e)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="log-entry__step">{entry.step}</span>
          <span className="log-entry__icon" style={{ background: cfg.bg, color: cfg.color }}>
            {cfg.icon}
          </span>
          <span className="log-entry__label" style={{ color: cfg.color }}>{cfg.label}</span>
          {isDenied  && <span className="badge badge--denied"   style={{ fontSize: '0.6rem' }}>DENIED</span>}
          {isApproved && entry.tool !== 'agent_thinking' && <span className="badge badge--approved" style={{ fontSize: '0.6rem' }}>PASS</span>}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="log-entry__time">{formatTime(entry.timestamp)}</span>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
            {expanded ? '▲' : '▼'}
          </span>
        </div>
      </button>

      {/* Expandable body */}
      {expanded && (
        <div className="log-entry__body">
          <div className="log-entry__section">
            <span className="log-entry__section-label">INPUT</span>
            <JsonBlock data={entry.input} />
          </div>
          <div className="log-entry__section">
            <span className="log-entry__section-label">OUTPUT</span>
            <JsonBlock data={entry.output} />
          </div>
        </div>
      )}
    </div>
  )
}
