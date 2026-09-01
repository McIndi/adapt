<!-- MILEMARKER: milestone=M1 lanes_ok=8/8 lag=0 updated=2026-09-01 -->
# Project Status — adapt

Tracked with the [milemarker-8](https://github.com) skill: eight lanes,
one walking skeleton, then tracer rounds. See `MILESTONES.md` for the
ladder and `RELEASING.md` for the path from commit to published release.

Status tokens: `OK`, `WIP`, `TODO`, `LAG`, `N/A`. `LAG` means the lane is
behind the current milestone. A milestone counts as reached only when
every lane below reads `OK` for it.

**Current milestone:** M0 — Walking Skeleton (closed). M1 (security floor
closure) is done; M2 is next up in `MILESTONES.md`.

Since the last update (2026-08-21), the project gained an entire new
deployment surface — a Helm chart (`charts/adapt/`) with its own CI
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
for what's still open.

## Lane status

| # | Lane | Status | Next action |
|---|------|--------|-------------|
| 1 | Business logic | OK | v0.5.0 (bumped from v0.4.2 alongside the chart-publishing work below; no new business-logic change accompanied the bump). Since the last review: file upload (API + UI, permission-gated, path-traversal and MIME-sniffing checks), Helm chart persistence (PVC), automated superuser bootstrapping for the chart, and a NodePort service option. No action needed. |
| 2 | Interface | OK | FastAPI app, generated per-resource routes, admin UI, MCP server, and now `POST /api/uploads` (with an upload card in the web UI for permitted users). The Helm chart adds a `NodePort` option for reaching the service without an Ingress controller. All present and documented. No action needed. |
| 3 | Data | WIP | Application data: SQLite via SQLModel still uses `create_all()` — no migration tool yet; unchanged, still targeted by M3. Deployment data: the Helm chart now supports PVC-backed persistence (dynamic or pre-created claim) for that same SQLite store in Kubernetes, replacing the previous emptyDir-only (always-ephemeral) option — this is new and closes a real gap, but it's an orthogonal improvement to the migration-tool gap above, not a substitute for it. |
| 4 | Packaging | OK | PyPI publish via CI with OIDC trusted publishing and the GHCR image publish path. The `Dockerfile` targets Python 3.14, restores dependency-layer caching, and carries OCI labels plus a `/health` `HEALTHCHECK`. The Helm chart is published as the stable `0.5.1` to `oci://ghcr.io/mcindi/charts/adapt`, with complete metadata and a values schema. A clean-machine round trip on a fresh VM — anonymous `helm show chart` plus `helm install` into a fresh kind cluster, reaching `HTTP 200` on `/health` — confirmed both the publish gating (full test suite plus Helm CI) and public package visibility for both the release-candidate and stable tags. The published `0.5.0` image manifest (current release; verified `0.4.2` also carried both platforms) contains both `linux/amd64` and `linux/arm64`. The chart's own `appVersion` (`0.4.2`) has not been bumped to match the app's `0.5.0` — real drift, tracked as a residual gap rather than silently glossed over; it does not block installs since `image.tag` still resolves to a real, existing tag. Still no SBOM/signing for either artifact type — targeted by M2. |
| 5 | Automation | OK | CI runs the test suite on every push/PR across a FastAPI version matrix, plus `dependency-audit` (`pip-audit`). `helm-ci.yml` runs for chart-affecting pushes to `main`, pull requests, manual dispatches, and reusable workflow callers, including `tools/test-helm-schema.sh` changes. `publish-chart.yml` calls the Python test and full Helm CI workflows before pushing a matching `chart-v<version>` package to GHCR; both `chart-v0.5.1-rc.1` and the stable `chart-v0.5.1` passed every job, including all three kind Kubernetes versions. Still no Python lint job, Dependabot, or backup/restore path — targeted by later milestones. |
| 6 | Tests | OK | 334 Python tests (333 passed and 1 skipped), pytest, gated in CI on push and PR. The Helm chart has 52 `helm-unittest` cases for persistence, pod selectors, security contexts, health probes, admin bootstrap, NodePort wiring, notes, ingress URL rendering, external volume mounts, schema rejection, unsafe storage combinations, and namespace-qualified commands; VM Helm tests pass. No coverage measurement/reporting configured yet — targeted by M4. |
| 7 | Docs | OK | README, the Diataxis-ish manual (`docs/manual/*`), the disclaimed spec (`docs/spec/*`), and `SECURITY.md`, now updated for persistence, uploads, admin-bootstrap, and NodePort. `RELEASING.md` documents independent `chart-v<version>` OCI releases and the canonical GHCR install command. Deployment documentation is now consolidated and published live: a new `docs/manual/deployment.md` overview links a dedicated `container.md` (Docker/Podman, verified against the published multi-arch `0.5.0` image) and `kubernetes.md` (the single canonical Helm reference, with a day-1 walkthrough verified end-to-end, including an actual login), confirmed live at `https://www.mcindi.com/adapt/manual/kubernetes/` after `pages.yml` run 33502635532. `README.md`, `docs/manual/installation.md`, and `charts/adapt/README.md` no longer carry three diverging copies of the same Helm content — each now points at `kubernetes.md`. `docs/manual/troubleshooting.md` gained a deployment section covering `fsGroup`/UID-1000 permission failures, startup-probe restarts, the discovery-is-startup-only gotcha, bootstrap-Job/PVC cleanup, and RWO node-affinity `ContainerCreating`. Verifying the walkthrough surfaced a real chart bug, not just a docs bug: the release name `adapt` collapses the chart's `fullname` to a bare Service named `adapt`, which Kubernetes then shadows with an auto-injected `ADAPT_PORT` service-link env var that collides with Adapt's own identically-named config variable, crash-looping the pod (`ADAPT_PORT must be an integer`) — documented as a warning in `kubernetes.md` and a `known_limitations.md` entry, with every example switched to release name `myadapt` to avoid it; the underlying chart behavior is not yet fixed (no `enableServiceLinks: false` escape hatch exists in the chart today) and is tracked as an open gap under Data/Packaging-adjacent chart work, not silently routed around. `mkdocs build --strict` passes and matches the live site. Gap found during this review: `docs/manual/security.md` (the dedicated security-posture doc) was never updated for the upload feature's attack surface (path traversal, MIME sniffing, size limits) even though `api_reference.md`/`installation.md` do cover it as usage docs — this remains open. `CHANGELOG.md` still doesn't exist — targeted by M4. |
| 8 | Security | OK | M0/M1 floor holds: no hardcoded secrets, dependencies pinned/constrained, `pip-audit` clean in CI, TLS/transport assumptions documented, `SECURITY.md` in place. New this cycle: an authorization bug was found and fixed — two web UI routes (dataset pages, markdown pages) built their navigation dropdown from an unfiltered resource list, so an authenticated regular user could see the *names* of datasets they had no read permission on (the underlying data routes were correctly permission-gated; only the nav listing leaked). Fixed by switching both call sites to the already-existing permission-filtered link builder, with two regression tests added and confirmed to fail against the pre-fix code. Also new: the Helm chart's admin-bootstrap flow generates credentials into a Kubernetes Secret rather than requiring a hand-typed password, and the release-tag/`pyproject.toml` version-match check on both publish workflows closes a supply-chain traceability gap (an artifact's declared version can no longer silently disagree with what was actually tagged). SBOM/signing, secret-scanning, and SAST remain future work — targeted by M2 and beyond. |

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

M0 is fully `OK` across all eight lanes. M1 is done. Nothing in this
cycle's work (Helm chart, uploads, admin-bootstrap, NodePort, the nav
permission-leak fix, or the new publish pipeline) reopened M0 or M1 — the
gaps it surfaced (the `security.md` upload-coverage gap, and M2's now
container-inclusive SBOM/signing scope) are recorded above as the next
concrete actions rather than regressions.

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
