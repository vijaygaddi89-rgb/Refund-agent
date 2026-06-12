import React, { useEffect, useRef, useState } from 'react'
import LogEntry from './LogEntry.jsx'

/**
 * AdminPanel
 * ─────────────────────────────────────────────────────────────────
 * Right-side admin dashboard showing:
 *   - Live agent reasoning logs (streaming)
 *   - CRM customer quick-reference table
 *   - Session statistics
 *
 * Props:
 *   logs      – current run log entries
 *   allLogs   – all logs in this session
 *   isLoading – bool
 */

const CUSTOMERS = [
  { id: 'CUST001', name: 'James Carter',     tier: 'standard', order: 'ORD-2026-001', product: 'Headphones',      amount: 129.99  },
  { id: 'CUST002', name: 'Sara Mitchell',    tier: 'standard', order: 'ORD-2026-002', product: 'Yoga Mat',        amount: 59.99   },
  { id: 'CUST003', name: 'David Nguyen',     tier: 'premium',  order: 'ORD-2026-003', product: 'Coffee Maker',    amount: 219.00  },
  { id: 'CUST004', name: 'Emily Ross',       tier: 'standard', order: 'ORD-2026-004', product: 'Wallet',          amount: 34.99   },
  { id: 'CUST005', name: 'Marcus Bell',      tier: 'standard', order: 'ORD-2026-005', product: 'BT Speaker',      amount: 89.99   },
  { id: 'CUST006', name: 'Priya Sharma',     tier: 'vip',      order: 'ORD-2026-006', product: 'Standing Desk',   amount: 349.00  },
  { id: 'CUST007', name: 'Kevin Turner',     tier: 'standard', order: 'ORD-2026-007', product: '🔒 Adobe License', amount: 599.99  },
  { id: 'CUST008', name: 'Laura Gonzalez',   tier: 'standard', order: 'ORD-2026-008', product: '🏷️ Winter Jacket', amount: 39.99   },
  { id: 'CUST009', name: 'Ryan Patel',       tier: 'premium',  order: 'ORD-2026-009', product: 'Espresso Machine', amount: 299.00  },
  { id: 'CUST010', name: 'Natalie Brooks',   tier: 'standard', order: 'ORD-2026-010', product: 'Running Shoes',   amount: 110.00  },
  { id: 'CUST011', name: 'Alex Thompson',    tier: 'vip',      order: 'ORD-2026-011', product: '4K Monitor',      amount: 479.00  },
  { id: 'CUST012', name: 'Olivia Chen',      tier: 'standard', order: 'ORD-2026-012', product: 'DSLR Camera',     amount: 849.99  },
  { id: 'CUST013', name: 'Samuel White',     tier: 'standard', order: 'ORD-2026-013', product: 'LED Desk Lamp',   amount: 45.00   },
  { id: 'CUST014', name: 'Fatima Al-Hassan', tier: 'premium',  order: 'ORD-2026-014', product: 'Office Chair',    amount: 375.00  },
  { id: 'CUST015', name: 'Jordan Lee',       tier: 'standard', order: 'ORD-2026-015', product: 'Mech Keyboard',   amount: 145.00  },
]

const TIER_COLORS = {
  standard: { color: 'var(--text-secondary)', bg: 'rgba(255,255,255,0.06)' },
  premium:  { color: 'var(--accent-amber)',   bg: 'var(--accent-amber-dim)' },
  vip:      { color: 'var(--accent-teal)',    bg: 'var(--accent-teal-dim)'  },
}

export default function AdminPanel({ logs, allLogs, isLoading }) {
  const [tab, setTab]         = useState('logs')   // 'logs' | 'crm'
  const logsBottomRef         = useRef(null)

  useEffect(() => {
    logsBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  // Stats from allLogs
  const toolCalls = allLogs.filter(l => l.tool !== 'agent_thinking').length
  const approvals = allLogs.filter(l => l.output?.decision === 'approved').length
  const denials   = allLogs.filter(l => l.output?.decision === 'denied').length

  return (
    <div className="admin-panel glass">
      {/* Header */}
      <div className="admin-header">
        <div>
          <h2 className="admin-title">Admin Dashboard</h2>
          <p className="admin-subtitle">Agent reasoning & CRM</p>
        </div>
        {isLoading && (
          <div className="admin-processing">
            <span className="spinner spinner--sm" />
            <span>Processing</span>
          </div>
        )}
      </div>

      {/* Stats row */}
      <div className="admin-stats">
        <div className="stat-card">
          <span className="stat-card__value" style={{ color: 'var(--accent-teal)' }}>{allLogs.length}</span>
          <span className="stat-card__label">Log Entries</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__value" style={{ color: 'var(--accent-purple)' }}>{toolCalls}</span>
          <span className="stat-card__label">Tool Calls</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__value" style={{ color: 'var(--accent-green)' }}>{approvals}</span>
          <span className="stat-card__label">Approved</span>
        </div>
        <div className="stat-card">
          <span className="stat-card__value" style={{ color: 'var(--accent-red)' }}>{denials}</span>
          <span className="stat-card__label">Denied</span>
        </div>
      </div>

      {/* Tab bar */}
      <div className="admin-tabs">
        <button
          className={`admin-tab ${tab === 'logs' ? 'admin-tab--active' : ''}`}
          onClick={() => setTab('logs')}
        >
          🧠 Reasoning Logs {logs.length > 0 && <span className="tab-badge">{logs.length}</span>}
        </button>
        <button
          className={`admin-tab ${tab === 'crm' ? 'admin-tab--active' : ''}`}
          onClick={() => setTab('crm')}
        >
          👥 CRM Profiles
        </button>
      </div>

      {/* Tab content */}
      <div className="admin-content">
        {/* ── Logs tab ─────────────────────────────── */}
        {tab === 'logs' && (
          <div className="logs-container">
            {logs.length === 0 && !isLoading ? (
              <div className="logs-empty">
                <p>🔍 No logs yet.</p>
                <p>Send a chat message to see<br />real-time agent reasoning here.</p>
              </div>
            ) : (
              <>
                {logs.map((entry, i) => (
                  <LogEntry key={`${entry.step}-${i}`} entry={entry} index={i} />
                ))}
                {isLoading && (
                  <div className="log-processing fade-in-up">
                    <span className="spinner spinner--sm" />
                    <span>Agent is reasoning...</span>
                  </div>
                )}
              </>
            )}
            <div ref={logsBottomRef} />
          </div>
        )}

        {/* ── CRM tab ──────────────────────────────── */}
        {tab === 'crm' && (
          <div className="crm-container">
            {CUSTOMERS.map((c) => {
              const tc = TIER_COLORS[c.tier]
              return (
                <div key={c.id} className="crm-row">
                  <div className="crm-row__left">
                    <div className="crm-row__name">{c.name}</div>
                    <div className="crm-row__meta">
                      <code style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{c.order}</code>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem' }}>{c.product}</span>
                    </div>
                  </div>
                  <div className="crm-row__right">
                    <span
                      className="badge"
                      style={{ background: tc.bg, color: tc.color, border: `1px solid ${tc.color}30` }}
                    >
                      {c.tier.toUpperCase()}
                    </span>
                    <span style={{ fontSize: '0.78rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                      ${c.amount.toFixed(2)}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
