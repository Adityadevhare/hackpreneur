# AGENTS.md — HACKPRENEUR Project Instructions

This file gives coding agents the project context, architecture rules and working
expectations for HACKPRENEUR. Read it before inspecting or changing the codebase.

## Project identity

HACKPRENEUR is a platform connecting hackathon participants, judges/mentors and
organizers. Its three pillars are:

- **Connect** — build lasting relationships between participants, mentors and organizers.
- **Collaborate** — help teams keep working together after the event.
- **Continue** — help hackathon projects and relationships survive beyond a single event.

The product goal is continuity: projects, teams, mentorship and feedback should not
disappear when the hackathon ends.

## Current technology stack

Frontend:

- React
- TypeScript
- Vite
- Plain CSS

Backend:

- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic

Database:

- Supabase PostgreSQL
- Separate administrative and restricted runtime database connections

Authentication:

- Supabase Auth issues JWT access tokens.
- FastAPI verifies tokens using public JWKS keys.
- Backend authorization is independent of frontend roles.

## Repository layout

```text
hackpreneur/
├── AGENTS.md
├── README.md
├── .gitignore
├── backend/
│   ├── main.py              FastAPI app and routes
│   ├── auth.py              Supabase JWT verification
│   ├── database.py          SQLAlchemy engine, session, Base
│   ├── models.py            SQLAlchemy models
│   ├── init_db.py           Applies Alembic migrations
│   ├── alembic.ini
│   ├── alembic/             Migration environment and revisions
│   ├── requirements.txt
│   ├── test_app.py
│   ├── test_auth.py
│   ├── test_security_hardening.py
│   ├── .env.example
│   └── hackpreneur.db       Legacy SQLite artifact (must be preserved)
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── main.tsx
    │   ├── lib/supabase.ts  Supabase browser client
    │   └── ...
    ├── package.json
    ├── vite.config.ts
    ├── test_supabase_init.js
    └── .env.example
```

The backend is not a Python package: modules are imported as top-level modules when
commands are run from `backend/`.

## Established architecture decisions

1. **Preserve existing working functionality.** Do not rewrite unrelated code or
   remove behavior that already works.
2. **Supabase Auth establishes identity; HACKPRENEUR establishes permissions.**
   A valid Supabase token proves who the user is. It does not grant platform
   privileges by itself.
3. **Multiple platform roles per account are supported.** A user may be, for example,
   a participant and a mentor at the same time.
4. **Platform-role verification and event-specific assignments are separate.**
   Being a judge on the platform does not automatically assign a person to review a
   specific event or project.
5. **Backend authorization is mandatory for privileged operations.** Frontend checks
   are only user-experience aids; they are never a security boundary.
6. **One project has one owner: an individual or a team.** Ownership must be explicit
   and stored in the database.
7. **Project creator attribution remains permanent.** Creator history must not be
   erased when ownership or membership changes.
8. **Projects support public, unlisted and private visibility.** Access rules must be
   enforced by the backend, not only hidden in the UI.
9. **Team membership does not automatically grant access to every team project.**
   Project-level access must be checked separately.
10. **Judges only access projects and private repositories they are authorized to
    review.** No broad judge access.
11. **Private conversations are visible only to their participants.** Conversations
    must not leak through APIs, logs or AI processing.
12. **GitHub tokens remain backend-only.** Never send, store or expose GitHub tokens in
    frontend code, browser storage or API responses.
13. **AI access requires both source authorization and user authorization.** The AI
    may use a source only when the requesting user is allowed to access it and the
    source itself permits AI processing.
14. **Private messages are excluded from AI ingestion by default.** Inclusion requires
    explicit, informed permission.
15. **Platform administrators and moderators are separate roles.** Do not merge their
    permissions or treat one as a synonym for the other.
16. **Sensitive actions must be auditable.** Record who did what, when, and to which
    resource, without storing secrets or sensitive message content.

## Database and migration rules

### Connection roles

- **Alembic must use `DATABASE_ADMIN_URL`.**
- **Application database access must use `DATABASE_URL`.**
- **`DATABASE_RUNTIME_URL` is the restricted runtime connection.**
- **Never introduce fallback from runtime to admin credentials.** If the runtime
  configuration is missing, fail rather than silently using admin access.
- **Runtime roles must not gain superuser, `BYPASSRLS`, DDL or migration privileges.**
- Migration and administrative work must remain separate from application runtime
  access.

### Row-level security (RLS)

- **Do not create permissive RLS policies.** Avoid `USING (true)`-style shortcuts and
  broad `PUBLIC` grants.
- **RLS must be designed around verified backend user context.** The backend must
  establish who the user is before touching protected data.
- **Never assume `auth.uid()` automatically works with direct SQLAlchemy
  connections.** Supabase's `auth.uid()` relies on request context that a plain
  SQLAlchemy connection may not provide.
- **Use transaction-scoped trusted user context when implementing RLS.** Set the
  verified user context for the transaction and clear or scope it safely.
- **Never trust a user ID supplied by the frontend.** Derive identity from a verified
  token, not from request bodies, query parameters or headers controlled by the client.

### Legacy SQLite database

- **Preserve the original SQLite database as a legacy artifact.**
  `backend/hackpreneur.db` must not be modified, migrated, deleted or replaced.
- Do not point runtime configuration back to SQLite.

## Authentication and authorization rules

- **Verify JWT signatures cryptographically.**
- **Validate issuer, audience, expiry and subject.**
- **Restrict signing algorithms to those supported by the actual Supabase project.**
  Do not accept `none`, arbitrary symmetric algorithms or unconfigured algorithms.
- **Fail closed on JWKS failures.** A network or key-lookup failure must reject the
  request, never allow it.
- **Never decode JWT claims and trust them without verification.**
- **Never use `user_metadata` for authorization.** Users can often edit metadata.
- **Never interpret Supabase's `role` claim as a HACKPRENEUR platform role.** The
  Supabase role (for example `authenticated`) is an authentication concept, not a
  platform permission.
- **Never expose tokens or secrets in API responses or logs.**

The backend must remain the source of truth for permissions. Frontend role checks are
convenience only.

## API and code conventions

- Keep FastAPI route handlers small; put reusable logic in focused modules.
- Use Pydantic models for request and response validation.
- Use SQLAlchemy 2.x style sessions and explicit transaction handling.
- Use `Depends(get_db)` for database sessions.
- Do not duplicate session lifecycle logic in route modules.
- Return consistent HTTP status codes and avoid leaking internal exception details.
- Keep public API responses free of credentials, tokens and connection strings.
- Prefer minimal, readable implementations over premature abstraction.
- Follow the existing plain-CSS approach; do not introduce a UI framework unless
  explicitly approved.
- Do not add comments unless they explain non-obvious intent.
- Keep Windows PowerShell compatibility in documented commands.

## Security and secrets

- Never print `.env` values, credentials, tokens, API keys or database connection
  strings.
- Never commit `.env` files, local databases, tokens or keys.
- Keep `.env.example` limited to placeholders.
- Never put secret keys in frontend code. Only publishable/public frontend values may
  be exposed through Vite environment variables.
- Do not log raw authorization headers, JWTs, passwords or connection URLs.
- Do not add fallback secrets or hardcoded production identifiers as a convenience.
- Treat logs, error messages and test output as potentially public.

## Development workflow

Follow this sequence:

**Discuss → Decide → Document → Implement → Test → Review → Commit/Push**

For each task:

1. Inspect the relevant files first.
2. Explain the existing implementation.
3. Identify dependencies and risks.
4. Make only approved changes.
5. Run the relevant tests.
6. Report the exact files changed.
7. Report actual test results.
8. Identify remaining issues.
9. Stop and wait for approval when requested.

Do not begin a new roadmap item or unrelated refactor without explicit approval.

## Testing

### Backend

Run from `backend/`:

```powershell
python -m pytest -q
```

Notes:

- `test_app.py` and `test_security_hardening.py` are integration tests. They require
  live Supabase PostgreSQL configuration, admin/runtime roles and RLS setup.
- `test_auth.py` uses a mocked JWKS client and locally generated keys.
- The declared backend requirements currently do not include the test runner or
  HTTP client, so a test environment may need `pytest` and `httpx` installed
  separately.
- Never claim tests passed unless they were actually executed.
- Do not weaken or delete a failing security test to make the suite pass.

### Frontend

```powershell
cd frontend
npm run lint
npm run build
node test_supabase_init.js
```

Notes:

- `test_supabase_init.js` is a standalone script, not part of the npm scripts.
- It reads `frontend/.env.local`; never print that file or its values.

## Git and change management

- Do not rewrite unrelated code.
- Do not delete or revert existing uncommitted work.
- Do not stage, commit or push without explicit permission.
- Before reporting completion, show which files changed.
- Keep changes focused on the approved task.
- Do not create empty commits or amend commits unless explicitly instructed.

## Current roadmap

1. Backend foundation and database.
2. GitHub integration.
3. RAG pipeline.
4. AI evaluation and security testing.
5. Core platform functionality.
6. Frontend integration.
7. Polish and deployment.

## Current task status

- **Task 1: PostgreSQL foundation** — reported complete.
- **Task 1.1: Database security audit** — complete.
- **Task 1.2: Database role hardening** — reported complete.
- **Task 2.1: Supabase frontend SDK** — reported complete.
- **Task 2.2: JWT verification** — implemented; final security corrections pending.
- **Task 2.3: Frontend/backend authentication integration** — not started.

Do not begin any roadmap implementation as part of documentation or audit work.

## Definition of done

A task is complete only when:

- The approved scope is implemented.
- Relevant tests have been run and actual results reported.
- No unrelated files were changed.
- No secrets or sensitive values were exposed.
- Remaining risks or follow-up work are stated clearly.
- The user has reviewed the result when review was requested.

## Stop conditions

Stop and ask before:

- Changing authentication or authorization behavior.
- Changing database roles, grants or RLS policies.
- Running or editing migrations against a shared database.
- Introducing new dependencies or architectural patterns.
- Deleting, migrating or modifying the legacy SQLite database.
- Committing, pushing, rebasing or reverting.
