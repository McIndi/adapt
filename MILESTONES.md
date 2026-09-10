# Milestones — adapt

Adapt uses eight review lanes: business logic, interface, data, packaging,
automation, tests, docs, and security. A milestone closes only when its planned
work passes the review gate in `CLEANUP_PLAN.md` and the affected lanes in
`PROJECT_STATUS.md` are current.

`CLEANUP_PLAN.md` is the active execution plan. This file is the shorter
roadmap.

## Completed foundation

### M0 — Walking skeleton (done)

Adapt installs and runs, has tested interfaces and SQLite storage, publishes a
Python package, and has a maintained user manual.

### M1 — Security floor (done)

Dependencies have bounded versions. CI runs `pip-audit`. `SECURITY.md` defines
the reporting path, supported versions, and the first threat-model notes.

The completed Kubernetes deployment tracer also delivered the OCI image and
Helm chart workflows, durable chart storage, bootstrap credentials, service
access, Helm tests, kind tests, and consolidated deployment documentation. Its
detailed work log is archived at
`archive/CONTAINER_OCI_HELM_CLEANUP_PLAN_2026-09-02.md`.

### M2 — Coordinated 0.5.2 release (done)

Application, image, and chart `0.5.2` are public. The chart disables
service-link injection and supports `image.digest`. A Vagrant VM `kind`
install named `adapt` became Ready and `/health` returned version `0.5.2`.
Chart `0.5.2-rc.1` was not published; the stable chart passed the anonymous
pull and live install.

## Active roadmap

### M3 — Dependency and supply-chain hardening

Status: In progress (Phase 3)

Goal: automate dependency maintenance, pin the container base image, and give
consumers verifiable release evidence.

Phases:

2. Dependency automation and base-image pinning (done; Review Gate 2 passed
   2026-09-10).
3. Artifact SBOMs, provenance, and signing.

Exit criteria:

- Dependabot covers Python, GitHub Actions, and Docker dependencies.
- The Python base image uses a readable tag and a pinned multi-platform digest.
- Current registry evidence is inventoried before new signing is added.
- Python distributions, the container image, and the chart have documented
  SBOM and verification paths.
- Missing image and chart signatures or attestations are produced with
  least-privilege CI permissions and verified after a public pull.
- Existing PyPI Trusted Publishing attestations are retained and are not
  duplicated without a documented need.

### M4 — Quality visibility

Status: Planned

Goal: make Python static checks and test coverage visible and enforceable in
pull requests.

Phase:

4. Python lint and coverage visibility.

Exit criteria:

- Ruff is a required CI check with a documented initial rule set.
- CI publishes one stable coverage summary.
- The coverage baseline and threshold policy are recorded.
- Deliberate lint and coverage failures have proved both gates work.

### M5 — Declarative docroot seeding

Status: Conditional

Goal: support safe chart-managed seed content only if a current user workflow
requires it.

Phase:

5. Declarative docroot seeding.

Exit criteria:

- The requirement and design choice are recorded, or M5 closes as `N/A`.
- If implemented, seeding is idempotent, preserves existing files, works with
  persistent storage, and passes install and upgrade tests.

### M6 — Multi-replica operation

Status: Conditional

Goal: support more than one replica only after an availability requirement and
safe state architecture are approved.

Phase:

6. Multi-replica operation.

Exit criteria:

- The availability objective and architecture decision are recorded, or M6
  closes as `N/A` and the single-replica limit remains explicit.
- If implemented, concurrent writes, pod loss, migrations, bootstrap races,
  rolling upgrades, and rollback pass without data loss or access-control
  regressions.

### Keycloak OIDC (product tracer, not M2)

Status: Done

A Vagrant VM now starts Keycloak on `192.168.58.30:8080` for a live SSO
check. Automated tests still mock Keycloak.

Goal: optional Keycloak identity for the browser UI, REST API, and `/mcp/`,
while local passwords and API keys keep working.

This tracer is independent of the coordinated `0.5.2` packaging work in M2.
Schema changes stay additive SQLite `ALTER` statements until a migration
tool exists.

Exit criteria:

- OIDC enables only when issuer and client_id are set.
- Browser SSO uses authorization code and PKCE.
- REST and MCP accept Bearer JWTs with iss, aud, exp, and JWKS checks.
- Unauthenticated `/mcp/` requests return RFC 9728 protected-resource metadata
  when OIDC is on.
- JIT users and `oidc_managed` group sync leave manual memberships in place.
- Tests cover tokens, PRM, MCP 401, callback, local login, and CSRF without
  a live Keycloak.

### MCP Python SDK 2.2 (product tracer, not M3)

Status: In progress (local tests green)

Goal: run `/mcp` on `mcp>=2.2,<3` (`MCPServer`) without an OpenTelemetry
exporter.

This tracer is independent of M3 supply-chain work. It does not add Jaeger,
OTLP, or a tracer provider.

Exit criteria:

- `pyproject.toml` requires `mcp>=2.2,<3`.
- Tools, auth, and the FastAPI mount still work on Streamable HTTP.
- Tests use the v2 client types (`httpx2`, `is_error`, `input_schema`).
- Host-header and 4 MiB body behavior are documented.
- OpenTelemetry remains unconfigured.

## Unscheduled work

The following gaps remain outside the six ordered phases:

- Database schema migrations and a tested backup-and-restore drill.
- Automated version selection and changelog generation.
- Secret scanning, static security analysis, and container vulnerability
  scanning.

Create a scoped milestone before starting any of these items. Schema migration
and restore work becomes a prerequisite if M6 is approved.
