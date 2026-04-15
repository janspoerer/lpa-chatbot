# lpa-chatbot

> This is a public repository and a public application.

This application is mainly a German application for people that want to inform themselves about Lipoprotein(a), a dangerous, genetically determined cholesterol particle that has seen enormous attention in the medical community in recent years. About 1/5 of the Western population is affected by it.

Answers are grounded in a curated local markdown knowledge base that an
agent searches and reads on demand — no invented facts.

## Architecture

- **Backend**: FastAPI + OpenAI SDK driving a tool-calling loop against a
  LiteLLM OpenAI-compatible endpoint (target model: Qwen via LiteLLM).
  Tools exposed to the agent: `list_files`, `read_file`, `keyword_search`.
- **Frontend**: React + TypeScript (Vite). Multi-turn chat with history in
  `localStorage` and a "clear history" button. Tool calls are surfaced in
  the UI so you can see which files the agent consulted.
- **Knowledge base**: drop `.md` files into `backend/kb/` (local dev) or into
  the host-mounted KB directory on the server. No rebuild needed.
- **Deploy**: single Docker image containing backend + built frontend, via
  `pull_build_start_container.sh`.

## Local development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit values
uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/chat` and `/health` to the backend.
Drop markdown files into `backend/kb/` and they become available immediately.

## Configuration

| Variable              | Default                    | Purpose                        |
| --------------------- | -------------------------- | ------------------------------ |
| `LITELLM_BASE_URL`    | `http://127.0.0.1:4000/v1` | OpenAI-compatible endpoint     |
| `LITELLM_API_KEY`     | `sk-noop`                  | Bearer token                   |
| `LPA_MODEL`           | `qwen3.5-35b`              | Model name as known to LiteLLM |
| `MAX_TOOL_ITERATIONS` | `8`                        | Tool-loop safety cap           |
| `REQUEST_TIMEOUT_S`   | `120`                      | Per-request timeout            |

For Qwen to be reachable at `LITELLM_BASE_URL`, add a `model_list` entry to
`litellm_config.yaml` pointing at the reverse-SSH tunnel to the MacBook's
`llama-server`, then restart the litellm router.

## Deployment (Hetzner)

```bash
./pull_build_start_container.sh prod 8060
```

The script pulls master, builds a multi-stage image (frontend → backend
runtime), runs the container with env from
`/home/deploy/dev/credentials/lpa-chatbot/.env`, bind-mounts
`/home/deploy/dev/data/lpa-chatbot/kb` read-only (so you can add `.md` files
without rebuilding), and copies the built frontend to
`/var/www/lpa.spoerico.com/` for nginx.

Nginx needs to serve static assets from `/var/www/lpa.spoerico.com/` and
proxy `/chat` and `/health` to `127.0.0.1:8060`.
