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

Nginx can either serve static assets from `/var/www/lpa.spoerico.com/` and
proxy `/chat` + `/health` to `127.0.0.1:8060`, or simply reverse-proxy
*everything* to the backend — the FastAPI app mounts the built Vite bundle
under `/` and `/assets`, so a single `location /` block is enough (see below).

## Production notes

A few things that aren't obvious from the code but bit us during the first
production deploy. All of these apply to any similar small personal-agent
app behind nginx.

### Single-container layout

The backend serves the built frontend too (`app.main` mounts `dist/assets`
at `/assets` and returns `dist/index.html` on `/`). That means the
production nginx doesn't need a separate `root` for static files — one
reverse-proxy block handles HTML, JS/CSS, `/chat` and `/health` together.
This also avoids the `sudo` dance of copying frontend assets into
`/var/www/` on every deploy.

### Reverse proxy and SSE

`/chat` returns a `text/event-stream` that may stay open for tens of
seconds while the agent runs its tool loop. Nginx must not buffer or time
it out:

```nginx
server {
    server_name lpa.spoerico.com;
    location / {
        proxy_pass http://127.0.0.1:8060;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE: stream bytes as they arrive, don't idle-kill the connection
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
```

Without `proxy_buffering off`, the browser sits on a blank screen until
the whole agent run completes and nginx flushes the buffered stream at
the end — looks like a hang.

### Docker bridge → host loopback

If the LiteLLM proxy runs on the host (not inside the same Docker
network), `LITELLM_BASE_URL=http://127.0.0.1:4000/v1` does **not** work
from inside the container — `127.0.0.1` there is the container itself.
Fix: run the container with `--add-host=host.docker.internal:host-gateway`
and set `LITELLM_BASE_URL=http://host.docker.internal:4000/v1`.

### Knowledge base hot-swap vs. bake-in

The Dockerfile does `COPY backend/kb ./kb`, so the image always ships
with whatever KB was committed at build time. Adding a read-only bind
mount at `/app/kb` at `docker run` time **overrides** the baked-in
directory — useful for hot-swapping without rebuilds, but it means an
empty host directory will silently yield an empty KB. If you use the
bind mount, make sure the host directory is populated before the
container starts.

### HTTP → HTTPS redirect gotcha for POST

If a browser loads the page over HTTP *before* you enable TLS and then
keeps the tab open while you run `certbot --nginx --redirect`, the next
POST to `/chat` will hit the freshly-added HTTP→HTTPS 301 redirect. Most
browsers re-issue a 301-redirected POST as a **GET**, and the GET hits
FastAPI's POST-only `/chat` endpoint, which returns **405 Method Not
Allowed**. Users see `HTTP 405` in the UI and assume the backend is
broken. Reload the page over HTTPS to fix it. To prevent this entirely,
set up TLS *before* anyone loads the page.

### Smoke tests

```bash
# Public
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://lpa.spoerico.com/health
curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://lpa.spoerico.com/

# End-to-end via nginx (will hang for ~10–60s while the tool loop runs —
# that's normal; -v will show the 200 + text/event-stream headers immediately)
curl -sS -v --max-time 5 -X POST https://lpa.spoerico.com/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Was ist Lp(a)?"}]}' 2>&1 \
  | grep -E '^< HTTP|^< content-type'
```

