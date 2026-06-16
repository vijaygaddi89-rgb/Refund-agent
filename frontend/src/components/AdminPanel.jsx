import React from 'react';

function AdminPanel({ logs, logEndRef, status }) {
  return (
    <div className="panel admin-panel">
      <div className="panel-header">
        <h2>Admin Dashboard</h2>
        <div className="header-meta text-muted">Agent Reasoning Logs</div>
      </div>

      <div className="timeline-container">
        {logs.length === 0 ? (
          <div className="empty-state text-muted">Waiting for agent activity...</div>
        ) : (
          logs.map((log) => (
            <div key={log.id} className="timeline-node">
              <div className="node-time mono text-muted">{log.time}</div>
              <div className="node-content">
                <div className="node-action mono">{log.action}</div>
                <div className="node-payload mono text-muted">{log.payload}</div>
                <div className={`node-result mono ${log.status}`}>{log.result}</div>
              </div>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>

      {/* Status Indicator */}
      <div className="admin-footer">
        <div className="status-indicator">
          <span className={`status-dot ${status.toLowerCase()}`}></span>
          Status: {status}
        </div>
      </div>
    </div>
  );
}

export default AdminPanel;
