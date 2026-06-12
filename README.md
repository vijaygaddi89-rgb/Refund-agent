# 🛒 ShopEasy AI Refund Agent

An AI-powered customer support agent that processes or denies e-commerce refunds using a **LangGraph ReAct loop** backed by **Claude (Anthropic)**. Built for the AI Customer Support Agent challenge.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│              React Frontend (Vite)           │
│  ┌────────────────┐  ┌────────────────────┐  │
│  │  Chat Window   │  │   Admin Dashboard  │  │
│  │ (Customer UI)  │  │ (Reasoning Logs)   │  │
│  └───────┬────────┘  └────────┬───────────┘  │
└──────────┼─────────────────────┼─────────────┘
           │  WebSocket /api/ws  │  REST /api
┌──────────▼─────────────────────▼─────────────┐
│            FastAPI Backend (Python)           │
│  ┌─────────────────────────────────────────┐  │
│  │         LangGraph ReAct Agent           │  │
│  │  START → agent_node → tool_node → END  │  │
│  │                                         │  │
│  │  Tools:                                 │  │
│  │  1. lookup_customer   (CRM lookup)      │  │
│  │  2. validate_policy   (rule checking)   │  │
│  │  3. process_refund    (decision)        │  │
│  └──────────────────────┬──────────────────┘  │
│                         │                     │
│  ┌──────────────────────▼──────────────────┐  │
│  │  Data Layer                             │  │
│  │  crm.json (15 customers) │ policy.md    │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

## 🧠 Agent Logic

The agent uses a **LangGraph ReAct loop**:

1. **`agent_node`** — Claude evaluates the customer message and decides which tool to call
2. **`tool_node`** — Executes the chosen tool and logs input/output
3. Loop repeats until Claude produces a final answer (no more tool calls)

### Tools
| Tool | Purpose |
|------|---------|
| `lookup_customer` | Finds customer by ID, email, or order ID from CRM |
| `validate_policy` | Checks all 7 policy rules (digital, sale, window, reason) |
| `process_refund` | Records the final decision: approved / denied / partial / escalated |

## 📋 Mock Data

**15 CRM profiles** covering all policy edge cases:
- Standard / Premium / VIP tier customers
- Digital products (non-refundable once activated)
- Clearance/sale items (final sale, non-refundable)
- Outside return window cases
- Normal refundable orders

## 🚀 Quick Start

### Prerequisites
- Python 3.12+, `uv` package manager
- Node.js 18+
- Anthropic API key

### 1. Clone & configure
```bash
git clone <repo>
cd Refund-agent
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY
```

### 2. Start the backend
```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

### 3. Start the frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## 🎯 Demo Scenarios

### ✅ Standard Approval
> "My order ORD-2026-001 arrived with broken headphones. I'd like a refund."
→ Agent looks up customer → validates policy → **approves** $129.99 refund

### ❌ Digital Product Denial
> "I want a refund for my Adobe Creative Suite license, order ORD-2026-007."
→ Agent identifies digital product → **denies** per Section 2, holds the line against pushback

### ⏰ Outside Return Window
> "My yoga mat from order ORD-2026-002 is terrible quality."
→ Purchased 45 days ago, standard tier (30-day window) → **denies** as outside window

### 🏷️ Clearance Item Denial
> "I want to return the winter jacket from order ORD-2026-008."
→ Clearance item → **denies** per Section 2 (final sale)

---

## 📁 Project Structure

```
Refund-agent/
├── backend/
│   ├── main.py              # FastAPI app (CORS, routers)
│   ├── database.py          # CRM in-memory loader + lookup functions
│   ├── agent/
│   │   ├── graph.py         # LangGraph ReAct state machine
│   │   ├── tools.py         # 3 agent tools with @tool decorator
│   │   ├── state.py         # AgentState TypedDict
│   │   └── prompts.py       # System prompt (with policy embedded)
│   ├── routers/
│   │   ├── chat.py          # POST /api/chat + WebSocket /api/ws
│   │   └── admin.py         # GET /api/admin/customers + /stats
│   └── data/
│       ├── crm.json         # 15 customer profiles
│       └── policy.md        # ShopEasy Refund Policy v3.0
└── frontend/
    ├── src/
    │   ├── App.jsx           # Split-pane layout
    │   ├── components/
    │   │   ├── ChatWindow.jsx    # Customer chat interface
    │   │   ├── MessageBubble.jsx # Chat message with decision badge
    │   │   ├── AdminPanel.jsx    # Reasoning logs + CRM table
    │   │   └── LogEntry.jsx      # Collapsible log step
    │   └── hooks/
    │       └── useWebSocket.js   # WS + HTTP fallback hook
    └── vite.config.js        # Proxy /api → :8000
```

## 🔑 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Single-turn chat (JSON body: `{message, history}`) |
| `WS`   | `/api/ws/{session_id}` | Real-time streaming with reasoning logs |
| `GET`  | `/api/admin/customers` | All 15 CRM profiles |
| `GET`  | `/api/admin/stats` | Aggregate statistics |
| `GET`  | `/health` | Health check |

## 🛡️ Policy Enforcement

The agent enforces **ShopEasy Refund Policy v3.0** with 7 hard rules:
1. ❌ Digital/activated products → immediate denial
2. ❌ Clearance/sale items → immediate denial
3. ❌ Outside return window (30/45/60 days by tier) → denial
4. ❌ Invalid refund reason → denial
5. ✅ Seller errors override window restrictions
6. ⬆️ Ambiguous edge cases → escalate to human
7. 🔒 No override for emotional pressure or verbal claims
