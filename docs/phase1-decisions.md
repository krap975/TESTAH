# Phase 1 implementation decisions

- The canonical architecture.md was absent. Copy the supplied complete Testah Markdown design to that path without altering either source reference.
- Keep the API a modular monolith. Future domain modules contain only Python package markers.
- Use an application factory to isolate configuration, engines, and sessions between tests and runtime.
- SQLAlchemy uses synchronous request-scoped sessions. Relative SQLite URLs resolve under backend/ regardless of the command working directory. Enable SQLite foreign keys on every connection.
- Alembic owns schema initialization. Revision 0001_foundation establishes its version table without premature domain models. Future feature migrations add their own tables. The API never calls create_all.
- GET /api/health verifies SELECT 1 and returns service, status, and database connectivity. It is a connectivity check, not future feature readiness. Database failure returns 503.
- API errors use one error/code/message envelope. Validation errors never echo raw submitted values. Unexpected errors expose only a generic message.
- Exact CORS origins come from server environment settings. Only GET is currently needed; future phases must explicitly extend methods alongside their APIs.
- The browser reads a public API base URL, checks health with an eight-second timeout, cancels abandoned requests, and offers a manual retry. No credentials are needed or exposed.
- Navigation routes use explicit unimplemented empty states. No fabricated business data or integration success is shown.
- RAI prompt contracts, agent protocol, payment approvals and idempotency, event cursor, scoring rules, authentication, and restart recovery remain future scoped decisions. No Phase 2 work is included.

