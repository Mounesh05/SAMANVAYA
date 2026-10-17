# Docker deployment (local / single host)

## Architecture

- **MongoDB** runs in the Compose network with a persistent named volume.
- **FastAPI** listens on container port 8000 and is reachable internally as `backend:8000`.
- **Nginx** serves the built React SPA and forwards `/api/*` to FastAPI. The host exposes Nginx on port 8000 by default.
- **Ollama stays on the host**. The backend container calls `http://host.docker.internal:11434`; Compose adds the host-gateway mapping for Linux.

## Start

1. Install Docker Engine/Desktop with the Compose plugin.
2. From the repository root, create a local environment file:

   ```sh
   cp .env.example .env
   ```

   Generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"` and replace `SECRET_KEY` in `.env`. Do not commit `.env`.
3. Ensure Ollama is installed and running on the host. Pull the configured model if needed, for example `ollama pull llama3.2`. On Linux, Ollama must listen on an address reachable from Docker (not only 127.0.0.1); restrict access with your host firewall.
4. Build and start:

   ```sh
   docker compose up --build -d
   docker compose ps
   docker compose logs -f backend frontend
   ```

5. Open `http://localhost:8000`. Nginx serves the frontend and proxies API requests on the same origin. API health is available at `http://localhost:8000/health` through the SPA container's Nginx health endpoint; check backend dependency health directly with `docker compose logs backend` or `docker exec samanvaya-backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"`.
6. To create the initial user, use the script's actual path in the backend image:

   ```sh
   docker exec -it samanvaya-backend python create_first_user.py
   ```

## Configuration notes

- Change the host port with `APP_PORT=8080` in `.env`, then open `http://localhost:8080`.
- Leave `VITE_API_URL` empty for the recommended same-origin Nginx setup. For a separate API host, set it to an absolute URL **including `/api`**, such as `https://api.example.com/api`, and rebuild the frontend.
- For local Vite development, `VITE_DEV_API_TARGET` defaults to `http://localhost:8000`; override it if FastAPI is running elsewhere.
- The root `.env` is used by Compose. `backend/.env.example` is a reference for running the backend directly outside Compose.
- GitHub test-result reporting is optional. Configure `SAMANVAYA_API_URL`, `SAMANVAYA_PROJECT_ID`, and `SAMANVAYA_TEST_RESULTS_TOKEN` as repository secrets to enable uploads from push runs. Pull-request runs do not upload secrets to external services.

## Validate / stop

```sh
docker compose --env-file .env.example config --quiet
docker compose ps
docker compose logs --tail=100 backend frontend mongo
docker compose down
```

Use `docker compose down -v` only if you intentionally want to delete the MongoDB data volume.
