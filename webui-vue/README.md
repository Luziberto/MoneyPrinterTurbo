# MoneyPrinterTurbo Cockpit (Vue)

Vue 3 + Vite + TypeScript + Pinia replacement for the Streamlit cockpit
(`webui/`), built against the `/api/v1/cockpit`, `/api/v1/channels` and
`/api/v1/collector` endpoints added alongside it. See the migration plan for
the full phase breakdown; `webui/` stays untouched and running until this
reaches feature parity.

## Development

```bash
npm install
npm run dev            # http://localhost:5173, proxies /api and /tasks to :8080
```

Run the FastAPI backend separately (from the repo root):

```bash
python main.py          # or: docker compose up api
```

## Build

```bash
npm run build           # outputs to webui-vue/dist/
```

The build is not served directly from `dist/` -- a later phase adds a script
that copies `dist/*` into `resource/public/` (the directory `app/asgi.py`
already mounts at `/`), plus a Node build stage in the Dockerfile.

## Status

Phase 2 of the migration plan: scaffold + the Script/Collector/Preview wizard
steps. Render/Result/Publish and the Canais/Tarefas/Config tabs are stubs
pending later phases.
