import React from 'react';

function ChatPanel({ messages, chatEndRef, input, setInput, status, handleSubmit, sessionId }) {
  return (
    <div className="panel chat-panel">
      <div className="panel-header">
        <h2>Customer Support</h2>
        <div className="header-meta text-muted">Ticket: {sessionId}</div>
      </div>

      <div className="chat-window">
        {messages.map((msg) => (
          <div key={msg.id} className={`message-wrapper ${msg.role}`}>
            {msg.role === 'system' ? (
              <div className="message system-msg">{msg.content}</div>
            ) : (
              <div className="message-bubble">{msg.content}</div>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      <form className="chat-input-area" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={status === 'PROCESSING'}
          autoFocus
        />
        <button
          type="submit"
          disabled={status === 'PROCESSING' || !input.trim()}
          className={input.trim() ? 'active' : ''}
        >
          Send
        </button>
      </form>
    </div>
  );
}

export default ChatPanel;
