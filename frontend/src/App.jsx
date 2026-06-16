import React, { useState, useEffect, useRef } from 'react';
import './App.css';

import ChatPanel from './components/ChatPanel';
import AdminPanel from './components/AdminPanel';

const SESSION_ID = 'ORD-2026-001'; // Static session ID for demo

function App() {
  const [messages, setMessages] = useState([
    { id: 1, role: 'system', content: 'Support session initialized. How can we help you today?' }
  ]);
  const [logs, setLogs] = useState([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState('IDLE'); // IDLE, PROCESSING, APPROVED, DENIED
  const chatEndRef = useRef(null);
  const logEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Setup SSE Listener for real-time admin logs
  useEffect(() => {
    const eventSource = new EventSource(`/stream/${SESSION_ID}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'tool_call') {
          const args = typeof data.data.tool_input === 'object' ? JSON.stringify(data.data.tool_input) : data.data.tool_input;
          setLogs(prev => [...prev, {
            id: Date.now() + Math.random(),
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            action: `[CALL] ${data.data.tool_name}`,
            payload: args,
            result: 'Awaiting response...',
            status: 'pending'
          }]);
        } else if (data.type === 'tool_result') {
          const res = typeof data.data.result === 'object' ? JSON.stringify(data.data.result, null, 2) : data.data.result;
          setLogs(prev => {
            const newLogs = [...prev];
            for (let i = newLogs.length - 1; i >= 0; i--) {
              if (newLogs[i].action.includes(data.data.tool_name) && newLogs[i].status === 'pending') {
                newLogs[i].result = res;
                newLogs[i].status = res.includes('DENIED') || res.includes('FAIL') || res.includes('error') ? 'fail' : 'pass';
                break;
              }
            }
            return newLogs;
          });
        }
      } catch (e) {
        console.error('SSE Error processing message', e);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE connection error:', err);
    };

    return () => {
      eventSource.close();
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || status === 'PROCESSING') return;
    
    const userMessage = input;
    setStatus('PROCESSING');
    setMessages(prev => [
      ...prev,
      { id: Date.now(), role: 'customer', content: userMessage },
      { id: Date.now() + 1, role: 'system', content: 'Agent is typing...' }
    ]);
    setInput('');

    try {
      const response = await fetch('/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: SESSION_ID,
          message: userMessage
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      setMessages(prev => [
        ...prev.filter(m => m.content !== 'Agent is typing...'),
        { id: Date.now() + 2, role: 'agent', content: data.message }
      ]);
      
      if (data.refund_decision === 'approved') {
        setStatus('APPROVED');
      } else if (data.refund_decision === 'denied') {
        setStatus('DENIED');
      } else {
        setStatus('IDLE');
      }
      
    } catch (error) {
      console.error("Error communicating with backend:", error);
      setStatus('IDLE');
      setMessages(prev => [
        ...prev.filter(m => m.content !== 'Agent is typing...'),
        { id: Date.now() + 2, role: 'system', content: 'Connection failed. Please try again.' }
      ]);
    }
  };

  return (
    <>
      <ChatPanel
        messages={messages}
        chatEndRef={chatEndRef}
        input={input}
        setInput={setInput}
        status={status}
        handleSubmit={handleSubmit}
        sessionId={SESSION_ID}
      />
      <AdminPanel
        logs={logs}
        logEndRef={logEndRef}
        status={status}
      />
    </>
  );
}

export default App;
