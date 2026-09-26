# support-agent

A customer support agent that decides for each message whether to search a policy document (RAG), look up an order (tool calling), do both, or do neither. It logs the path it took on every query, and it runs locally for free.

## What it does

- **Two tools:**
  - `search_policy(query)` does semantic search over a store policy document, embedded locally and stored in ChromaDB.
  - `get_order_status(order_id)` looks up an order in a SQLite database of sample orders.
- **The model chooses the tools.** Llama 3.3 70B on Groq's free tier picks which tools to call using OpenAI-style tool calling. It can call both in one turn, for example "order 1010 arrived damaged, what can I do?".
- **Every query is logged** with its route (`policy_search`, `order_status`, `both` or `none`), the tools called and their arguments, the latency, the mode (`groq`, `demo` or `fallback`) and any error. Logs go to a SQLite table (browse at `/logs`, summary at `/logs/stats`) and to one JSON line on stdout.
- **The route is derived from the tools actually called.** It is not the model's own claim about what it did, so the log can't disagree with what happened.
- **Guardrails:**
  - The agent asks for an order number instead of guessing one.
  - Order results never include the customer's name or email.
  - Bad tool arguments are sent back to the model as errors it can recover from.
  - There is a hard limit on tool rounds.
  - If the LLM fails, the request falls back to the rule-based agent.
- **Routing eval.** `python -m scripts.eval_routing` scores the agent on 30 labelled questions. The rule-based demo agent scores 29/30. The one miss is a paraphrase ("send something back") that keyword routing can't catch, which is what the LLM agent is for.
- **Web page.** A chat UI shows a route badge and an expandable list of tool calls on every answer, plus live routing stats.

## Quickstart

With Docker:

```bash
git clone https://github.com/joel819/support-agent.git && cd support-agent
docker compose up
```

Without Docker (Python 3.11+):

```bash
git clone https://github.com/joel819/support-agent.git && cd support-agent
pip install -r requirements.txt
uvicorn main:app
```

Open http://localhost:8000. 25 sample orders (1001–1025, every status) and the policy document are loaded on startup. The API docs are at http://localhost:8000/docs.

The first run without Docker downloads the embedding model once (about 90 MB). The Docker image already contains it.

- Tests: `pytest`. There are 48 tests, and they need no API key, no model download and no network access.
- Routing eval: `python -m scripts.eval_routing`

## Routes

| Route | When | Example |
|---|---|---|
| `policy_search` | General question about how things work | "Do you ship to Switzerland?" |
| `order_status` | An order number, asking about that order | "Where is order 1019?" |
| `both` | An order number plus a policy question | "Order 1010 arrived damaged, what can I do?" |
| `none` | Greeting, off-topic, or an order question without a number | "Where is my order?" (asks for the number) |

A log entry (`GET /logs`):

```json
{
  "id": 42, "question": "Order 1010 arrived damaged, what can I do?",
  "route": "both", "mode": "groq", "latency_ms": 912, "error": null,
  "tool_calls": [
    {"name": "get_order_status", "arguments": {"order_id": "1010"}, "ok": true},
    {"name": "search_policy", "arguments": {"query": "damaged item on arrival"}, "ok": true}
  ],
  "answer": "..."
}
```

## Architecture

```
POST /chat ─► service.handle_message ─► get_agent()
                  │                        ├─ GroqAgent  (GROQ_API_KEY set)
                  │                        │    loop ≤ MAX_AGENT_STEPS:
                  │                        │      LLM ─► tool_calls? ─► run_tool ─► results back to LLM
                  │                        │      last step: tools disabled, must answer
                  │                        └─ RuleAgent  (demo mode, and fallback when Groq fails)
                  │                             order-number patterns + keyword intent ─► run_tool
                  │
                  ├─► tools.run_tool ─┬─ search_policy   ─► ChromaDB (policy sections, MiniLM vectors)
                  │                   └─ get_order_status ─► SQLite (orders, items)
                  │
                  └─► routing_log.record ─► SQLite query_log + JSON log line
```

```
main.py                   uvicorn entrypoint
app/
  config.py               settings; demo_mode = no GROQ_API_KEY
  db.py, models.py        SQLite: Order, OrderItem, QueryLog
  schemas.py              ChatIn/ChatOut, LogOut
  knowledge/              policy.md → sections, embeddings (MiniLM / hash), ChromaDB store
  tools/                  search_policy, get_order_status, OpenAI tool schemas, run_tool, route_for
  agent/                  GroqAgent (tool-calling loop), RuleAgent (demo), system prompt
  service.py              run agent, fall back on LLM error, record the route
  routing_log.py          SQLite row + structured log line per query
  routers/                /chat, /logs, /logs/stats, /orders, /health
  static/index.html       chat UI with route badges
data_seed/                policy.md (fictional store) + orders.json (25 orders)
scripts/                  seed.py, eval_routing.py
tests/                    offline pytest suite; the Groq client is mocked
```

**Design choices:**

- **One tool dispatcher for both agents.** `run_tool` serves the LLM agent and the rule agent alike, so routing, logging and tests treat them the same. `run_tool` never raises. Unknown tools and bad arguments come back as error results that the model can read.
- **Policy sections keep their headings.** Each chunk is a `## Section` of the policy, so answers can cite `[Returns]` or `[Warranty]` instead of an anonymous passage.
- **Order numbers are stripped from policy queries** in the rule agent. Otherwise "order 1010 arrived damaged" would match the "Changing an order" section instead of "Damaged items".

## Demo mode

**It runs free, with no API keys.**

| Piece | Cost |
|---|---|
| Embeddings: sentence-transformers `all-MiniLM-L6-v2` on your CPU | free |
| Vector store: ChromaDB in `./data/chroma` | free |
| Database: SQLite in `./data/app.db` | free |
| LLM: Groq free tier. Without a key, the rule-based agent is used | free |

When `GROQ_API_KEY` is empty, the rule-based agent routes with patterns and keywords. It answers from the tool results, filling in the order details and quoting the matching policy sentences, so it never makes anything up. It can't handle paraphrases as well as the LLM, and it doesn't use conversation history. `/health` shows `"demo_mode": true`, and every answer is tagged `demo`.

For the LLM agent, get a free key at https://console.groq.com/keys, put it in `.env` as `GROQ_API_KEY=...`, and restart. Run `python -m scripts.eval_routing` again to compare the two agents on the same 30 questions.

To run fully offline, including without the model download, set `EMBEDDING_BACKEND=hash`. The tests use it.

## Configuration

Every variable is listed with its default in [`.env.example`](.env.example).
