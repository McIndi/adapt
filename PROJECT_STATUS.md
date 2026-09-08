<!-- MILEMARKER: milestone=M1 lanes_ok=7/8 lag=0 updated=2026-09-08 -->
# Project Status — adapt

Tracked with the [milemarker-8](https://github.com) skill: eight lanes,
one walking skeleton, then tracer rounds. See `MILESTONES.md` for the
ladder and `RELEASING.md` for the path from commit to published release.

Status tokens: `OK`, `WIP`, `TODO`, `LAG`, `N/A`. `LAG` means the lane is
behind the current milestone. A milestone counts as reached only when
every lane below reads `OK` for it.

**Last closed milestone:** M1 — Security floor, plus the Kubernetes
deployment tracer. **Current milestone:** M2 — Coordinated 0.5.2 release
(not started). Data stays `WIP` on purpose: schema work still uses
`create_all()` plus additive `ALTER` statements. That is a named gap, not
M1 `LAG`.

The active sequence is `CLEANUP_PLAN.md`. The completed Helm and image
work is under `archive/`.

Shipped today: Python package and image `0.5.0`, chart `0.5.1` at
`oci://ghcr.io/mcindi/charts/adapt`. Chart `appVersion` is still `0.4.2`.
A Helm release named `adapt` still collides with Kubernetes service links.
Keycloak OIDC for UI, REST, and MCP is implemented in the working tree
(including a Vagrant Keycloak VM). It is not the M2 packaging work.

Assessment 2026-09-08: do not start M3 until M2 Phase 1 in `CLEANUP_PLAN.md`
passes its review gate.

## Lane status

| # | Lane | Status | Next action |
|---|------|--------|-------------|
| 1 | Business logic | OK | Land the Keycloak OIDC working tree on the default branch. Then start M2 Phase 1: `enableServiceLinks: false`, versions `0.5.2`, and image digest values. |
| 2 | Interface | OK | FastAPI, generated routes, admin UI, MCP, uploads, OIDC login/callback/logout, RFC 9728 PRM, and MCP 401 when OIDC is on. No extra interface work is required for M2. |
| 3 | Data | WIP | SQLite still uses `create_all()`. OIDC adds `usergroup.oidc_managed` and `dbsession.id_token` with `ALTER`. No migration tool. Chart PVC persistence exists. Migrations stay unscheduled until M6 needs them. |
| 4 | Packaging | OK for M1 | App `0.5.0`, chart `0.5.1`, chart `appVersion` `0.4.2`. M2 must publish package, image, chart `version`, and chart `appVersion` as `0.5.2`. Tags stay `v0.5.2` and `chart-v0.5.2`. Base-image digest pin is M3 Phase 2. SBOM and signing are M3 Phase 3. |
| 5 | Automation | OK for M1 | Python CI plus `pip-audit`. Helm CI: lint, unit, schema, kind. Chart `oidc:` maps to `ADAPT_OIDC_*`. Vagrant now boots Keycloak for a live SSO check. M2 still needs the `adapt` kind install and digest template tests. Dependabot is M3. Lint and coverage are M4. Backup and restore stay unscheduled. |
| 6 | Tests | OK | Python suite plus `tests/test_oidc.py` (no live Keycloak). Helm unittest lives in CI. M2 adds Helm tests for service-link disable and digest vs tag image refs. Coverage is M4. |
| 7 | Docs | OK for M1 | Manual and spec cover OIDC. M2 must add upload threat notes, remove the "do not name the release `adapt`" warning after the fix, and refresh `SECURITY.md` (it still says supported `0.4.x` and puts SBOM in M2). |
| 8 | Security | OK for M1 | OIDC checks iss/aud/exp on JWKS, PKCE for browser SSO, unusable hashes for JIT users, CSRF exempt for Bearer-only POST. Operator still owns token audience and DCR. M2 adds upload threat notes. Secret scanning, SAST, and image CVE scans stay unscheduled. |

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
