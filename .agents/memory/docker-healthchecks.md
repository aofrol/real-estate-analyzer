---
name: Docker healthchecks and Replit compatibility
description: Why CMD/CMD-SHELL healthchecks fail in Replit Docker, how to run Docker services alongside a native frontend, and root-ownership pitfalls from Docker volume mounts.
---

## Rule 1 — No Docker healthchecks
Never use `healthcheck: test: ["CMD", ...]` or `["CMD-SHELL", ...]` in `docker-compose.yml` on Replit.

**Why:** Docker healthchecks execute via `docker exec`, which calls `setns` to enter the container's Linux namespaces. Replit's sandbox blocks `setns`. The container can be running fine, but every healthcheck attempt throws:
```
OCI runtime exec failed: exec failed: unable to start container process:
error executing setns process: exit status 1: unknown
```
This exhausts retries → `unhealthy` → dependents abort.

**How to apply:** Remove all `healthcheck:` blocks. Replace `condition: service_healthy` with `condition: service_started`. Use `restart: unless-stopped` on dependents to self-recover from startup races.

---

## Rule 2 — Docker NAT port mapping is invisible to Replit's port watcher
Replit's `waitForPort` detects sockets owned by direct child processes of the workflow. Docker's NAT mapping (`5000:3000`) is implemented by `iptables` inside the Docker daemon — no child process owns the socket. Even though `curl localhost:5000` works, the watcher never fires.

**Fix:** Run the web-facing service (Next.js) natively in the workflow foreground. Run backend services (db, redis, api, worker) with `docker compose up -d <services>` (detached). Set `outputType: "webview"` with `waitForPort: 5000` in the Replit workflow.

Workflow command:
```bash
docker compose up -d db redis backend worker --build && cd frontend && ([ -d node_modules ] || npm install) && npm run dev
```

---

## Rule 3 — Docker volumes create root-owned files on the host
Any file written inside a Docker container (running as root) to a bind-mounted host directory will be owned by `root:root` on the host. This includes `node_modules/`, `.next/`, `next-env.d.ts`, etc. The host runner user cannot modify or delete them.

**Fix:** Use Docker itself (running as root) to fix ownership or delete:
```bash
docker run --rm -v "$(pwd)/frontend:/app" node:20-alpine sh -c "chown -R HOST_UID:HOST_GID /app"
# or to delete:
docker run --rm -v "$(pwd)/frontend:/app" node:20-alpine sh -c "rm -rf /app/node_modules /app/.next"
```

**Prevention:** Avoid anonymous volumes that leak root-owned content to the host. For Replit dev workflow, run Next.js natively (not in Docker) so the host user always owns the files.

---

## Rule 4 — Replit Package Firewall may block specific pinned npm versions
Pinned package versions (e.g. `next@14.2.20`) may be blocked by Replit's security firewall. Use `"next": "latest"` and `"eslint-config-next": "latest"` in `package.json`. The actual installed version will be pinned in `package-lock.json`.

---

## Rule 5 — Replit workflow outputType for Docker Compose projects
- Use `outputType: "console"` only if there is NO webview (no port to show). The Replit Preview shows "Your app crashed" when a console-type workflow is in failed state.
- Use `outputType: "webview"` with `waitForPort: 5000` for the main user-facing app — but only when a process in the workflow directly owns port 5000 (not via Docker NAT).

---

## Rule 6 — Run post-merge migrations from the host
Do not use `docker compose exec` for readiness checks or `docker compose run` to reach the database by its Compose service name in this Replit environment.

**Why:** `exec` fails because `setns` is blocked, and an ephemeral Compose run container can time out connecting to the sibling database even while the database is healthy and its published host port works.

**How to apply:** Probe PostgreSQL from the host with `pg_isready` against its published port. Run Alembic with the managed workspace Python and replace the Compose hostname `db` with `127.0.0.1` in the runtime-only database URL; never print that URL.
