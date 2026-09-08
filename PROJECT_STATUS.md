<!-- MILEMARKER: milestone=M2 lanes_ok=5/8 lag=0 updated=2026-09-08 -->
# Project Status — adapt

Tracked with the [milemarker-8](https://github.com) skill: eight lanes,
one walking skeleton, then tracer rounds. See `MILESTONES.md` for the
ladder and `RELEASING.md` for the path from commit to published release.

Status tokens: `OK`, `WIP`, `TODO`, `LAG`, `N/A`. `LAG` means the lane is
behind the current milestone. A milestone counts as reached only when
every lane below reads `OK` for it.

**Last closed milestone:** M1 — Security floor, plus the Kubernetes
deployment tracer. **Current milestone:** M2 — Coordinated 0.5.2 release
(in the repository; publish is still open). Data stays `WIP` on purpose:
schema work still uses `create_all()` plus additive `ALTER` statements.

The active sequence is `CLEANUP_PLAN.md`. The completed Helm and image
work is under `archive/`.

Repository versions are now `0.5.2` (`pyproject.toml`, `adapt/__init__.py`,
chart `version`, chart `appVersion`). The chart sets
`enableServiceLinks: false` and supports `image.digest`. Helm CI installs
a release named `adapt` and runs `helm test`. Tags `v0.5.2` and
`chart-v0.5.2` are not published yet. Follow `RELEASING.md` for that order.

Do not start M3 until Review Gate 1 in `CLEANUP_PLAN.md` passes.

## Lane status

| # | Lane | Status | Next action |
|---|------|--------|-------------|
| 1 | Business logic | OK | No new product behavior in M2. Next: create tag `v0.5.2` after this change lands. |
| 2 | Interface | OK | FastAPI, generated routes, admin UI, MCP, uploads, OIDC. Chart values gained `image.digest`. |
| 3 | Data | WIP | SQLite still uses `create_all()`. OIDC adds columns with `ALTER`. No migration tool. Chart PVC persistence exists. |
| 4 | Packaging | WIP | Source versions are `0.5.2`. PyPI, GHCR image, and OCI chart `0.5.2` are not published. Publish the image before the chart. RC chart `0.5.2-rc.1` then stable `chart-v0.5.2`. |
| 5 | Automation | WIP | Helm CI now installs release name `adapt`. Gate still needs a green kind run on CI and the public registry round trip. Dependabot is M3. |
| 6 | Tests | OK | Helm unit tests cover service links and digest vs tag. Python suite unchanged for this phase. Coverage is M4. |
| 7 | Docs | OK | Security manual covers uploads. `SECURITY.md` tracks `0.5.x`. Kubernetes docs describe digest pins and a valid `adapt` release name. |
| 8 | Security | OK | Upload threat notes are in the security manual. Secret scanning, SAST, and image CVE scans stay unscheduled. SBOM and signing stay M3. |

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
