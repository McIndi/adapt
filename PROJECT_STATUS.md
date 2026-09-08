<!-- MILEMARKER: milestone=M1 lanes_ok=7/8 lag=0 updated=2026-09-08 -->
# Project Status — adapt

Tracked with the [milemarker-8](https://github.com) skill: eight lanes,
one walking skeleton, then tracer rounds. See `MILESTONES.md` for the
ladder and `RELEASING.md` for the path from commit to published release.

Status tokens: `OK`, `WIP`, `TODO`, `LAG`, `N/A`. `LAG` means the lane is
behind the current milestone. A milestone counts as reached only when
every lane below reads `OK` for it.

**Last closed milestone:** M1 — Security floor. The Kubernetes deployment
tracer also passed its final review gate. M2 — Coordinated 0.5.2 release is
next.
The active implementation sequence is in `CLEANUP_PLAN.md`. The completed
cleanup record is under `archive/`.

The completed deployment tracer added an entire new deployment surface — a
Helm chart (`charts/adapt/`) with its own CI
(`helm-ci.yml`) — plus a file upload feature, PVC-backed persistence and
automated superuser bootstrapping for the chart, a NodePort option for
clusters without an Ingress controller, a container-image publish
pipeline to GHCR, and a fixed authorization bug in the web UI. The app
released as `v0.5.0` and the chart is now also published to
`oci://ghcr.io/mcindi/charts/adapt`. The container/Kubernetes
documentation that surface needed has been consolidated into a single
canonical location and published live. Verifying it surfaced a real chart
bug (the `adapt` release-name/service-link collision, still open — see
the Docs lane) rather than just documentation gaps. All of it is
reflected in the lane table below; see the per-lane notes for detail and
for what is still open. The immediate work is a coordinated `0.5.2` release.
It aligns the application, image, chart version, and chart `appVersion`. It
also corrects the release-name failure and adds digest image references.

## Lane status

| # | Lane | Status | Next action |
|---|------|--------|-------------|
| 1 | Business logic | OK | Optional Keycloak OIDC is available for UI, REST, and MCP. Local passwords and API keys still work when OIDC is off, and when it is on unless `local_login` is false. Next packaging work remains the M2 `0.5.2` release. |
| 2 | Interface | OK | FastAPI app, generated per-resource routes, admin UI, MCP server, uploads, OIDC login/callback/logout, RFC 9728 PRM, and MCP 401 challenge when OIDC is configured. |
| 3 | Data | WIP | Application data: SQLite via SQLModel still uses `create_all()` and has no migration tool. OIDC added additive `ALTER` columns (`usergroup.oidc_managed`, `dbsession.id_token`). Deployment data: the Helm chart supports PVC-backed persistence through dynamic provisioning or a pre-created claim. |
| 4 | Packaging | OK | PyPI publishing uses OIDC trusted publishing. GHCR publishes the multi-platform image and the Helm chart. Chart `0.5.1` passed anonymous pull and kind install tests. Phase 1 publishes the application, image, and chart as `0.5.2`. It also sets chart `appVersion` to `0.5.2` and adds digest image selection. The application and chart retain separate tag types. Base-image digest pinning is Phase 2. The artifact evidence inventory, SBOMs, and missing image or chart signatures are Phase 3. PyPI already exposes Trusted Publishing provenance, so Phase 3 must inspect that evidence before adding anything there. |
| 5 | Automation | OK | CI runs the Python test matrix and `pip-audit`. Helm CI runs lint, unit, schema, and kind checks. The chart gained an `oidc:` values block mapping to `ADAPT_OIDC_*`. The chart, image, and PyPI publish workflows require their test gates and matching release versions. Dependabot and base-image refresh automation are Phase 2. Supply-chain evidence is Phase 3. Python lint and coverage are Phase 4. Backup and restore automation remains unscheduled. |
| 6 | Tests | OK | 352 Python tests passed locally, with 1 skipped. Helm unittest was not run here because the helm CLI is not installed; Helm CI still runs it. Coverage reporting is Phase 4. |
| 7 | Docs | OK | Security, MCP, configuration, spec, Helm README, installation, and SECURITY.md cover Keycloak OIDC, PRM, JWT audience, DCR, and JIT group mapping. M2 still has the chart release-name workaround and upload threat notes in Phase 1. |
| 8 | Security | OK | OIDC validates iss/aud/exp against Keycloak JWKS, uses PKCE for browser SSO, stores JIT users with unusable password hashes, and exempts Bearer-only POSTs from CSRF. Token audience and DCR stay operator responsibilities documented in SECURITY.md. Secret scanning and SAST remain unscheduled. |

Keep this table's shape stable (one row per lane, status in column 3) so
it stays `grep`-able — see the rollup convention at the bottom.

## Gap summary (M0 closure — done)

Business logic, interface, tests, and docs had already run far ahead of a
"walking skeleton". The M0 security floor is now closed too:

- [x] No secret is hardcoded (verified: CSRF tokens and API keys use
      `secrets.token_urlsafe`; API keys stored as SHA-256 hashes; config
      reads from `ADAPT_*` env vars; the Helm chart's admin-bootstrap
      credentials are generated into a Kubernetes Secret, not hardcoded
      into chart values).
- [x] Dependencies are pinned/constrained — `pyproject.toml` deps now
      carry lower + upper version bounds (e.g. `fastapi>=0.115,<1.0`,
      `pillow>=12.3,<13`) instead of being fully open-ended.
- [x] CI runs one automated dependency-vulnerability scan —
      `.github/workflows/test.yml` gained a `dependency-audit` job
      running `pip-audit`, gating on findings, with zero ignored findings.
- [x] Transport and TLS assumptions are stated somewhere findable —
      `docs/manual/security.md` and the README both document that secure
      cookies/HSTS require `--tls-cert`/`--tls-key`.
- [x] `SECURITY.md` exists, with a reporting path and a first
      threat-model note.

M0 and M1 remain closed. The deployment tracer also passed its final review
gate. Its remaining findings now start the ordered plan: the coordinated
`0.5.2` release in M2, supply-chain hardening in M3, and quality work in M4.
M5 and M6 remain conditional on real user or availability requirements.

## Lane guidance

Fixed reference for what belongs in each lane, how it depends on its
neighbors, and what tools help. Update the table above as work lands;
leave this guidance section as-is.

### 1. Business logic
What fits: features, fixes, breaking changes, the rules the system
enforces. This lane sets the version number (see `RELEASING.md`).
Neighbors: any change here can push interface, data, tests, docs, or
security to `LAG` — that's the ripple rule. Sweep the other seven lanes
before calling a change finished.
Modern expectations: automated tests of real behavior, not just
happy-path smoke checks; type checking where the language supports it.

### 2. Interface
What fits: CLI, web UI, REST API, SDK — however a human or another
system reaches this one.
Neighbors: tracks business logic (every new capability needs a way in)
and docs (reference docs track the interface directly — a changed flag
or endpoint without a doc update is a `LAG`, not a nitpick).
Tools: whatever the project already uses for its interface framework;
for APIs, keep the OpenAPI/schema in sync with the code, not hand-edited
separately.

### 3. Data
What fits: storage, retrieval, schema, migrations, sync.
Neighbors: automation (a tested backup-and-restore path is a data lane
requirement, but the restore *script* lives in automation), and security
(encryption at rest and access control are security's call, applied
here).
Modern expectations: schema changes go through migrations, never manual
edits to a live schema.

### 4. Packaging
What fits: how artifacts get built and published — OCI images, PyPI
packages, npm packages.
Neighbors: automation (the publish step normally runs from CI), and
security (signing and SBOM generation happen at publish time — security
owns the requirement, packaging carries it out).
Modern expectations: reproducible builds, pinned dependencies, a
generated SBOM and provenance record attached to every published
artifact.

### 5. Automation
What fits: anything that runs without a human — CI/CD, infrastructure as
code, deployment, backup and restore.
Neighbors: packaging (CI is usually what publishes), data (automation
carries the tested restore script for data's backup path), security
(dependency and secret scanning normally run here, as CI steps).
Modern expectations: CI/CD by default; a backup-and-restore path that has
actually been exercised, not just written.

### 6. Tests
What fits: unit, integration, end-to-end tests, and whatever coverage
signal the project tracks.
Neighbors: business logic (new behavior needs new coverage) and
automation (tests must run in CI, gating merges, not just exist locally).
Modern expectations: tests that exercise real behavior, not just mocks of
mocks; coverage visible in CI, not just on someone's laptop.

### 7. Docs
What fits: README plus the Diataxis set — tutorial, how-to guide,
reference, explanation.
Neighbors: interface (reference docs track the interface's actual shape)
and business logic (a changelog entry per user-visible change).
Modern expectations: docs are part of the increment, not a follow-up
ticket.

### 8. Security
What fits: authentication and authorization, secret management,
supply-chain integrity, data protection, input validation, audit logs,
threat models, compliance controls.
Owns (even though the evidence for these often lives in another lane's
files): signing, SBOM generation, dependency scanning, secret scanning,
encryption at rest and in transit, least-privilege access. When packaging,
automation, or data claims `OK` on any of these, security is the lane
accountable for it actually being true.
Neighbors: packaging and automation (signing, scanning, and SBOM
generation are wired into the build/publish pipeline), data (encryption
and access control apply to stored data).
Tools:
- **pip-audit** or **Safety** — dependency vulnerabilities (Python).
- **Bandit**, or an equivalent SAST tool for the project's language.
- **gitleaks** or **trufflehog** — secret scanning.
- **Trivy** or **Grype** — container/image scanning.
- **cosign** / **sigstore** — artifact signing.
- A short threat-model note as an ongoing practice, not a one-time
  document — revisit it when the attack surface changes.

## The ripple rule

A change to business logic can push interface, data, tests, docs, or
security to `LAG`. Before calling a change done, sweep these lanes and
update their status. A milestone is not reached while any lane is `LAG`.

## Cross-project rollup convention

The first line of this file is a fixed-format, `grep`-able marker:

```
<!-- MILEMARKER: milestone=M1 lanes_ok=8/8 lag=0 updated=2026-08-11 -->
```

Keep it current whenever the lane table changes. To see status across many
projects at once, from a directory containing multiple repos:

```bash
grep -r "^<!-- MILEMARKER:" --include=PROJECT_STATUS.md .
```

This gives one line per project: its milestone, how many of the eight
lanes are `OK`, and how many are `LAG`.
