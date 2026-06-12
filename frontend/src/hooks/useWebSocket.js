import { useCallback, useEffect, useRef, useState } from 'react'

const WS_URL = `ws://${window.location.hostname}:8000/api/ws`

/**
 * useWebSocket
 * ─────────────────────────────────────────────────────────────────
 * Custom hook that manages the WebSocket connection to the backend.
 *
 * Returns:
 *   messages    – array of {id, role, content, decision, timestamp}
 *   logs        – array of reasoning log entries from the current run
 *   allLogs     – all logs accumulated across the session
 *   sendMessage – fn(text: string) → fires WS message or HTTP fallback
 *   isConnected – bool
 *   isLoading   – bool (true while agent is processing)
 */
export function useWebSocket() {
  const [messages, setMessages]   = useState([])
  const [logs, setLogs]           = useState([])          // current run logs
  const [allLogs, setAllLogs]     = useState([])          // all session logs
  const [isConnected, setConnected] = useState(false)
  const [isLoading, setLoading]   = useState(false)

  const wsRef      = useRef(null)
  const sessionId  = useRef(crypto.randomUUID())
  const historyRef = useRef([])   // keep history for multi-turn context

  // ── Connect ───────────────────────────────────────────────────
  const connect = useCallback(() => {
    const url = `${WS_URL}/${sessionId.current}`
    const ws  = new WebSocket(url)

    ws.onopen  = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      // Reconnect after 2s
      setTimeout(connect, 2000)
    }
    ws.onerror = () => ws.close()

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      switch (msg.type) {
        case 'status':
          setLoading(msg.data.status === 'processing')
          if (msg.data.status === 'processing') setLogs([])
          break

        case 'log':
          setLogs(prev => [...prev, msg.data])
          setAllLogs(prev => [...prev, msg.data])
          break

        case 'response': {
          const aiMsg = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: msg.data.response,
            decision: msg.data.final_decision,
            timestamp: new Date().toISOString(),
          }
          setMessages(prev => [...prev, aiMsg])
          historyRef.current.push({ role: 'assistant', content: msg.data.response })
          break
        }

        case 'error': {
          const errMsg = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: `⚠️ Error: ${msg.data.message}`,
            decision: null,
            timestamp: new Date().toISOString(),
            isError: true,
          }
          setMessages(prev => [...prev, errMsg])
          break
        }

        default:
          break
      }
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  // ── Send ──────────────────────────────────────────────────────
  const sendMessage = useCallback(async (text) => {
    if (!text.trim()) return

    // Snapshot history BEFORE adding the new user message
    const historySnapshot = [...historyRef.current]

    // Optimistically add user message to UI
    const userMsg = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    // Now add to history ref
    historyRef.current.push({ role: 'user', content: text })

    const payload = { message: text, history: historySnapshot }

    // Try WebSocket first (if open)
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload))
      return
    }

    // Fallback: HTTP POST
    setLoading(true)
    setLogs([])
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`)
      const data = await res.json()

      setAllLogs(prev => [...prev, ...data.reasoning_log])
      setLogs(data.reasoning_log)
      const aiMsg = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.response || '(no response)',
        decision: data.final_decision,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, aiMsg])
      historyRef.current.push({ role: 'assistant', content: data.response || '' })
    } catch (err) {
      console.error('Chat error:', err)
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `⚠️ Error: ${err.message}. Check the backend terminal.`,
        isError: true,
        timestamp: new Date().toISOString(),
      }])
      // Remove the failed user message from history
      historyRef.current.pop()
    } finally {
      setLoading(false)
    }
  }, [])

  return { messages, logs, allLogs, sendMessage, isConnected, isLoading }
}
