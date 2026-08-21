---
name: Docker healthchecks in Replit
description: Why CMD/CMD-SHELL healthchecks always fail in Replit's Docker environment and what to use instead.
---

## Rule
Never use Docker `healthcheck: test: ["CMD", ...]` or `["CMD-SHELL", ...]` in `docker-compose.yml` on Replit.

## Why
Docker healthchecks execute via `docker exec`, which internally calls `setns` to enter the container's Linux namespaces. Replit's container sandbox blocks `setns`, so every healthcheck attempt throws:
```
OCI runtime exec failed: exec failed: unable to start container process:
error executing setns process: exit status 1: unknown
```
The container can be fully running and healthy, but every healthcheck fails → the service is marked `unhealthy` → any service with `condition: service_healthy` in `depends_on` refuses to start.

## How to apply
- Remove all `healthcheck:` blocks from `docker-compose.yml` when running on Replit.
- Replace `condition: service_healthy` with `condition: service_started` in all `depends_on` blocks.
- Use `restart: unless-stopped` on dependent services so they self-recover from startup races.
- Add a comment in `docker-compose.yml` explaining the omission so future developers don't re-add healthchecks.

## Replit workflow port detection
Replit's `waitForPort` in `configureWorkflow` also cannot detect ports bound by Docker containers (they appear on the host but Replit's watcher doesn't see them within the 300 s timeout). Use `outputType: "console"` for Docker Compose workflows to avoid the timeout error.
