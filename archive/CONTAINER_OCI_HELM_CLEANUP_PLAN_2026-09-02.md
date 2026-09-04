# Container, OCI, and Helm Chart Cleanup Plan

Status: Complete — Review Gate 6 passed on 2026-09-02
Created: 2026-08-12
Baseline: `main` @ `60ea9b9` (app `0.4.1`, chart `0.3.2`)

> This file is a historical work log. Its milestone names and deferred items
> describe the repository when this plan closed. See
> [`../CLEANUP_PLAN.md`](../CLEANUP_PLAN.md) for the active plan.

## Purpose

Close the gaps between what Adapt's container and Kubernetes packaging
actually does and what its documentation tells users to do. The work is
split into six phases. Each phase ends at a **review gate**. Implement one
phase per session, stop at the gate, and get the gate reviewed before
starting the next phase.

## Scope

In scope:

- `Dockerfile`, `.dockerignore`
- `.github/workflows/publish-image.yml`, `.github/workflows/helm-ci.yml`
- `charts/adapt/**`
- Container and Kubernetes content in `README.md`,
  `docs/manual/installation.md`, `charts/adapt/README.md`, `mkdocs.yml`

Out of scope (do not change in these phases):

- Application code under `adapt/`, except where a phase names a specific file
- SBOM generation and artifact signing — already owned by milestone M2 in
  `MILESTONES.md`. Do not pull that work forward.
- PyPI publishing (`publish-pypi.yml`, `publish-testpypi.yml`)
- The SQLite migration gap (owned by M3)

## Ordering rationale

The phases run in dependency order, not severity order:

1. **Phase 1** fixes commands that fail when a user runs them, and turns on
   the CI signal that every later phase needs.
2. **Phase 2** corrects chart behavior. This must precede any documentation
   rewrite, because `docs/documentation-contract.md` requires documenting the
   running implementation.
3. **Phase 3** corrects the image. Same reason.
4. **Phase 4** settles the chart's value surface and operator experience.
5. **Phase 5** settles how users obtain the chart, which determines the
   `helm install` command every doc example uses.
6. **Phase 6** rewrites the documentation once, against a surface that has
   stopped moving.

Rewriting docs earlier means rewriting them two or three times.

## Conventions for every phase

- **Leave review, commit, and push to the repository owner.** Implement the
  phase in the working tree, verify it, then stop at the gate.
- **Bump `charts/adapt/Chart.yaml` `version`** in any phase that changes a
  file under `charts/adapt/`. Suggested bumps are listed per phase. Note that
  the `version-increment` job in `helm-ci.yml` only runs on pull requests, so
  nothing enforces this automatically — treat it as a manual step and confirm
  it at each gate.
- **Record every decision in the Decision log** at the end of this document.
  Each phase is implemented in a separate session, so a choice that is not
  written down here is lost to the next implementer.
- **Do not change `Chart.yaml` `appVersion`** in any of these phases. It
  tracks the app release (`0.4.1`) and nothing here bumps the app.
- **Add or update a `helm-unittest` case** for every template behavior change.
  Current count is 25 across `charts/adapt/tests/`.
- **Follow `docs/documentation-contract.md`.** Document what runs. Anything
  not yet implemented goes in an explicitly labeled `Future work` section or
  in `MILESTONES.md` — never as current behavior.
- **Update `PROJECT_STATUS.md` and `MILESTONES.md`** at the end of each phase
  to reflect what actually landed.

## Finding inventory

Every finding from the review, mapped to its phase. Nothing here should be
dropped without a written decision.

| ID | Finding | Phase |
|---|---|---|
| 1.1 | `installation.md:21` has a misspelled organization name | 1 |
| 1.2 | `helm-ci.yml` never triggers on `main` pushes; chart untested since `dc5a615` | 1 |
| 1.3 | Documented bootstrap-admin Secret name wrong for most release names | 1 |
| 1.4 | Documented `kubectl exec ... addsuperuser` crashes with `EOFError` | 1 |
| 1.5 | `values-dev.yaml` header references a Vagrantfile absent from the repo | 1 |
| 1.6 | `installation.md:270` "PVC named after the Helm release" is imprecise | 1 |
| 1.7 | `installation.md:332` broken "Otherwise" sentence | 1 |
| 2.1 | Bootstrap Job and health-test Pod match the Service selector | 2 |
| 2.2 | No `fsGroup`; `runAsUser: 1000` will fail on PVCs owned `root:root` | 2 |
| 2.3 | `Dockerfile` `useradd` does not pin UID 1000 | 2 |
| 2.4 | No `startupProbe`; liveness can restart-loop during startup indexing | 2 |
| 2.5 | Bootstrap Job passes `--allow-weak-password` unconditionally | 2 |
| 3.1 | Published image is amd64-only | 3 |
| 3.2 | `COPY . /app` before `pip install` defeats dependency layer caching | 3 |
| 3.3 | Image ships Python 3.12; CI only tests 3.14 | 3 |
| 3.4 | No OCI labels or `HEALTHCHECK` on a local `docker build` | 3 |
| 4.1 | `NOTES.txt` never says how to reach the service | 4 |
| 4.2 | No documented or supported way to get documents into the docroot | 4 |
| 4.3 | No `values.schema.json`; misspelled `--set` keys silently ignored | 4 |
| 4.4 | `Chart.yaml` has no `home`, `sources`, `maintainers`, `keywords` | 4 |
| 5.1 | Chart is never published; every doc example requires a git clone | 5 |
| 6.1 | No container/Docker documentation anywhere in `docs/` or `README.md` | 6 |
| 6.2 | Helm section sits below the `Manual navigation` footer | 6 |
| 6.3 | Three diverging copies of the Helm docs, already drifted | 6 |
| 6.4 | No deployment entry in the `mkdocs.yml` nav | 6 |
| 6.5 | `image.repository`, `image.tag`, `imagePullSecrets` undocumented | 6 |

---

# Phase 1 — Accuracy and CI floor

**Goal:** no documented command fails when a user runs it, and chart CI runs
on every change to the chart.

**Why first:** these are the only findings that actively mislead a user
today, they require no design decisions, and 1.2 is the verification signal
that Phases 2–5 depend on.

Chart version bump: `0.3.2` → `0.3.3` (patch; `NOTES.txt` changes).

### Tasks

**1.1 — Fix the clone URL.**
`docs/manual/installation.md:21`: correct the organization name. Then grep
the whole repo for that misspelling and fix every hit.

**1.2 — Make chart CI run on `main`.**
In `.github/workflows/helm-ci.yml`, add a `push` trigger for `main` using the
same `paths:` filter as the existing `pull_request` trigger:

```yaml
on:
  push:
    branches: [main]
    paths:
      - charts/adapt/**
      - Dockerfile
      - .ct.yaml
      - .github/workflows/helm-ci.yml
  pull_request:
    paths:
      - charts/adapt/**
      - Dockerfile
      - .ct.yaml
      - .github/workflows/helm-ci.yml
  workflow_dispatch:
```

Leave the `version-increment` job's `if: github.event_name == 'pull_request'`
guard as-is — it needs a base ref to diff against. Consequence to be aware
of: with no pull requests in this repository's workflow, that job never runs,
so `Chart.yaml` version bumps are unenforced. The per-phase bumps in this
plan are manual, and each gate should confirm one happened.

Then **run the workflow on the current chart and record the result.** The
chart has not been linted, unit-tested, or install-smoke-tested since
`dc5a615`; persistence, uploads, `bootstrapAdmin`, and NodePort all landed
after that. Expect failures. Triage them into: fix now if trivial, otherwise
record in the Phase 1 gate notes and route to Phase 2. Do not silence a
failing test to make the phase green.

**1.3 — Correct the bootstrap-admin Secret name in prose.**
The Secret is `<fullname>-bootstrap-admin`, where `adapt.fullname` is
`<release>-adapt` unless the release name already contains `adapt`
(`charts/adapt/templates/_helpers.tpl:5-16`).

- `docs/manual/installation.md:360`: replace `<release>-bootstrap-admin` with
  `<release>-adapt-bootstrap-admin`, and add one sentence: if the release
  name already contains `adapt`, the name collapses to
  `<release>-bootstrap-admin` — `helm get notes <release>` always prints the
  correct command.
- `README.md:287`: same fix. The example installs release `adapt`, so
  `adapt-bootstrap-admin` is correct *for that example* — make the release
  name and the Secret name visibly consistent, or switch the example to a
  non-`adapt` release name to expose the general rule.
- `charts/adapt/templates/NOTES.txt` is already correct (it templates the
  name). Do not change it in this task.

**1.4 — Fix the manual superuser command.**
`adapt addsuperuser` with no `--password` calls `getpass.getpass`
(`adapt/commands/passwords.py:62,93`), which raises `EOFError` under
`kubectl exec` without a TTY. Fix both occurrences:

- `docs/manual/installation.md:333`
- `charts/adapt/templates/NOTES.txt:33-34`

Use the interactive form and say why the flag is required:

```bash
kubectl exec -it deploy/<release>-adapt -- \
  adapt addsuperuser /data --username admin
```

Add one sentence noting that `-it` is required because `addsuperuser` prompts
for the password, and pointing at `--password` / `--password-confirm` /
`--allow-weak-password` for scripted use.

**1.5 — Fix the `values-dev.yaml` header.**
`charts/adapt/values-dev.yaml:1-19` references `/vagrant/adapt/charts/adapt`,
`localhost/adapt-local`, `192.168.56.10`, and "whatever `K3S_IP` is set to in
the Vagrantfile". No Vagrantfile exists in this repo. Rewrite the comment to
be repo-relative and generic:

- Path: `charts/adapt`
- Image: `<your-local-image>:<tag>`, matching `installation.md:403`
- Access: `http://<node-ip>:30080`, with no Vagrant reference

**1.6 — Fix the PVC naming sentence.**
`docs/manual/installation.md:270`: "named after the Helm release" →
`<release>-adapt` (same `fullname` rule as 1.3).

**1.7 — Fix the broken sentence.**
`docs/manual/installation.md:332`: "By default, a fresh install has no users.
Otherwise you need to run ... by hand." Rewrite as two coherent sentences.

### Verification

- A repository-wide search for the misspelled organization name returns nothing.
- Helm CI has a recorded run against the current chart, with each job's
  result written into the Decision log.
- Every `kubectl`, `helm`, and `git clone` command in `README.md`,
  `docs/manual/installation.md`, `charts/adapt/README.md`, and
  `charts/adapt/values-dev.yaml` has been read against the code or template
  that implements it. List the commands checked in the Decision log.

### Out of scope for Phase 1

Do not rewrite `NOTES.txt` beyond the one broken command (that is task 4.1).
Do not consolidate the duplicated Helm docs (that is Phase 6). Do not fix
chart behavior discovered by the new CI run — record it and route it to
Phase 2.

### Exit criteria

- [x] Findings 1.1, 1.3, 1.4, 1.5, 1.6, 1.7 fixed
- [x] `helm-ci.yml` triggers on `main` pushes; a run against current chart
      recorded, with failures triaged and routed
- [x] `Chart.yaml` version `0.3.3`
- [x] `PROJECT_STATUS.md:32` corrected — it currently claims chart CI
      coverage that a workflow without pull requests never delivered

## ⏸ REVIEW GATE 1

Reviewer confirms:

1. No user-facing command in the four files above fails when executed.
2. Helm CI ran against the current chart, and its real result is recorded —
   pass or fail. A failing chart discovered here is a successful Phase 1.
3. Chart behavior findings surfaced by CI were routed to Phase 2, not
   silently fixed or suppressed.
4. `PROJECT_STATUS.md` no longer overstates chart CI coverage.

---

# Phase 2 — Chart correctness

**Goal:** the chart behaves correctly on a real cluster with real storage,
not only on hostPath-backed test provisioners.

**Why here:** Phase 1 established the CI signal; these fixes need it. All of
these change runtime behavior, so they must land before Phase 6 documents
that behavior.

Chart version bump: `0.3.3` → `0.4.0` (minor; changes rendered pod specs).

### Tasks

**2.1 — Stop the bootstrap Job and test Pod from matching the Service.**
`charts/adapt/templates/service.yaml:16-17` selects on `adapt.selectorLabels`
(`app.kubernetes.io/name` + `app.kubernetes.io/instance`). Both
`charts/adapt/templates/admin-bootstrap-job.yaml:26-27` and
`charts/adapt/templates/tests/test-health.yaml:4-5` apply labels that satisfy
that selector, and neither pod has a readiness probe. Consequences: during
`post-upgrade` the Service can route live traffic to a pod running
`adapt addsuperuser`; the `helm test` curl can be routed back to itself.

Fix by adding a distinguishing label — for example
`app.kubernetes.io/component: bootstrap` and
`app.kubernetes.io/component: test` — and adding
`app.kubernetes.io/component: server` to both the Deployment's pod template
and the Service selector. Whatever approach is chosen, the Deployment's
`spec.selector.matchLabels` is immutable on an existing release: if the
server's selector changes, document that upgrading across this chart version
requires `helm uninstall` + `helm install`, or gate the new label so existing
selectors are unaffected. **State the chosen tradeoff explicitly in the
Decision log.**

Also consider narrowing the Deployment's pod-template labels
(`charts/adapt/templates/deployment.yaml:15`) from `adapt.labels` to
`adapt.selectorLabels` plus `podLabels`. `adapt.labels` embeds
`helm.sh/chart` and `app.kubernetes.io/version`, so every chart version bump
mutates the pod template and forces a rollout even when nothing else
changed. This is the stock `helm create` layout. Optional; if skipped, say so.

Add `helm-unittest` cases asserting the bootstrap Job's and test Pod's labels
do **not** satisfy the Service selector.

**2.2 — Add `fsGroup` so persistence works on real storage.**
`charts/adapt/values.yaml:21` has `podSecurityContext: {}` while lines 26-28
set `runAsNonRoot: true`, `runAsUser: 1000`, `runAsGroup: 1000`. Many CSI
drivers present a volume owned `root:root 0755`, so the container cannot
write `.adapt/adapt.db`. CI (kind `standard`) and `values-dev.yaml` (k3s
`local-path`) both use hostPath provisioners that create directories `0777`,
which is why this has never surfaced.

Set:

```yaml
podSecurityContext:
  fsGroup: 1000
```

Add a `helm-unittest` case asserting `spec.template.spec.securityContext.fsGroup`
renders on both the Deployment and the bootstrap Job. Note in the values
comment that `fsGroup` must match `securityContext.runAsGroup` and that some
drivers ignore `fsGroup` (those need `persistence.annotations` or a
pre-chowned `existingClaim`).

**2.3 — Pin the container UID.**
`Dockerfile:16` runs `useradd` with no `--uid`. It lands on 1000 on
`python:3.12-slim` by coincidence, and the chart hardcodes `runAsUser: 1000`
against that coincidence. Change to `useradd --uid 1000 --user-group` (or
explicit `groupadd --gid 1000`) so the image and the chart agree by contract.
Add a comment in `values.yaml` linking `runAsUser`/`runAsGroup`/`fsGroup` to
the UID the Dockerfile pins.

**2.4 — Add a `startupProbe`.**
`charts/adapt/values.yaml:61-66`: liveness begins at 10s and fails after
3 × 10s. With `search_on_startup` and a large document root, indexing can
exceed that window and the pod restart-loops. Add a `probes.startup` block
(disabled or generous by default, e.g. `failureThreshold: 30`,
`periodSeconds: 10` → 5 minutes) and render it in
`charts/adapt/templates/deployment.yaml`. Add a `helm-unittest` case.
Document the tunable in the values comments; full prose goes in Phase 6.

**2.5 — Scope `--allow-weak-password` in the bootstrap Job.**
`charts/adapt/templates/admin-bootstrap-job.yaml:51` passes
`--allow-weak-password` unconditionally. It is correct for the chart's
generated 24-character password, but it also silently accepts a weak password
supplied through `bootstrapAdmin.existingSecret`. Either gate the flag on
`not .Values.bootstrapAdmin.existingSecret`, or keep it and document the
behavior. **Gating is preferred** — a rejected weak password should fail the
Job loudly. If gated, add a `helm-unittest` case for both branches and note
in `values.yaml` that an `existingSecret` password must pass
`adapt/commands/passwords.py:is_weak_password`.

**2.6 — Resolve anything routed from Gate 1.**
Fix chart failures Phase 1's CI run surfaced.

### Verification

- `helm lint charts/adapt` and `helm unittest charts/adapt` pass.
- The kind install smoke test passes across all three node images.
- **`persistence.enabled=true` verified on a provisioner that is not
  hostPath-backed.** kind and k3s cannot prove 2.2. Either add a CI step using
  a driver that presents `root:root`-owned volumes, or verify by hand on a
  real cluster and record the evidence in the Decision log. Without this, 2.2
  is unverified.
- Unit test count rises from 25; state the new count.

### Out of scope for Phase 2

No documentation prose beyond values-file comments. No new user-facing
features. No Dockerfile changes other than the UID pin (2.3).

### Exit criteria

- [x] Findings 2.1–2.5 resolved, each with a `helm-unittest` case
- [x] Gate 1 routed items resolved
- [x] Deployment selector-immutability tradeoff for 2.1 recorded
- [x] `persistence.enabled=true` verified on non-hostPath storage, or the gap
      recorded as an explicit known limitation
- [x] `Chart.yaml` version `0.4.0`

## ⏸ REVIEW GATE 2

Reviewer confirms:

1. Each of 2.1–2.5 has a test that fails against the pre-fix template.
2. The 2.1 approach does not silently break `helm upgrade` on existing
   releases, or the breakage is documented with a migration note.
3. The `fsGroup` fix was validated against storage that actually reproduces
   the problem, or the residual risk is written down.
4. No documentation prose was changed in this phase.

---

# Phase 3 — Container image

**Goal:** the published image runs on the architectures users have, and a
local `docker build` produces the same metadata CI does.

**Why here:** Phase 6 will tell users to pull and run this image. Correct it
first.

No chart changes; no `Chart.yaml` bump unless a chart file is touched.

### Tasks

**3.1 — Publish a multi-arch image.**
`.github/workflows/publish-image.yml:72-77` has no `platforms:`, so the image
is amd64-only. Anyone on Apple Silicon, Raspberry Pi, or Graviton nodes gets
QEMU emulation or an exec-format error. Add:

```yaml
platforms: linux/amd64,linux/arm64
```

Add `docker/setup-qemu-action@v3` before `setup-buildx-action`. Confirm
`ffmpeg` (`Dockerfile:9`) resolves on arm64 in Debian slim — it does, but
verify in the build. Expect the build to get slower; if arm64 build time is
unacceptable, note the decision rather than dropping arm64 silently.

**3.2 — Restore dependency layer caching.**
`Dockerfile:12-14` does `COPY . /app` then `pip install --no-cache-dir .`, so
any source change invalidates the dependency install. Copy
`pyproject.toml` (plus `README.md` and any file the build backend reads)
first, install dependencies, then copy the source. Keep the resulting image
functionally identical — this is a build-time change only.

**3.3 — Reconcile the image's Python version with CI.**
The image is `python:3.12-slim` (`Dockerfile:1`); every workflow tests only
3.14, while `pyproject.toml:10` claims `>=3.11`. Pick one and make it
deliberate:

- Move the image to the version CI tests, **or**
- Add the image's Python version to the `test.yml` matrix, **or**
- Document the choice in the Dockerfile as an intentional stability pin

Any of the three is acceptable; shipping an untested interpreter silently is
not. Record the decision in the Decision log.

**3.4 — Make a local build match a CI build.**
OCI labels are applied by `publish-image.yml:78-81` only, so
`docker build .` locally yields an unlabeled image. Move the static labels
into the `Dockerfile` as `LABEL` instructions with `ARG`-supplied dynamic
values (`org.opencontainers.image.version`, `.source`, `.revision`,
plus `.title`, `.description`, `.licenses`). Keep the workflow supplying the
dynamic values. Optionally add a `HEALTHCHECK` hitting `/health`; note that
Kubernetes ignores it — it is for plain `docker run` users, who are Phase 6's
audience.

Consider pinning the base image by digest alongside the tag. If skipped, say
why.

### Verification

- A release build (or a `workflow_dispatch` dry run) produces a manifest list
  with both platforms. Record `docker buildx imagetools inspect` output.
- `docker run --rm ghcr.io/mcindi/adapt-server:<tag> adapt --help` works on
  both architectures.
- `docker image inspect` shows the expected OCI labels from a plain local
  `docker build`.
- The image still starts and serves `/health` with the default `CMD`.
- Helm CI still passes — `Dockerfile` is in its `paths:` filter.

### Out of scope for Phase 3

SBOM generation and cosign signing. Both are M2 in `MILESTONES.md`. Do not
start them here; do confirm nothing in this phase makes them harder.

### Exit criteria

- [ ] Multi-arch manifest published and inspected — `ghcr.io/mcindi/adapt-server:latest`
      currently lists only `linux/amd64`; this is the open Gate 3 blocker
- [x] Dependency layer caching restored in the Dockerfile
- [x] Python-version decision made and recorded
- [x] Local `docker build` label instructions match CI's build arguments
- [x] `PROJECT_STATUS.md` packaging row updated

## ⏸ REVIEW GATE 3

Reviewer confirms:

1. The published manifest genuinely lists `linux/amd64` and `linux/arm64`,
   verified by inspecting a real build, not by reading the workflow.
2. The image still runs and serves `/health`.
3. The Python-version mismatch was decided, not deferred.
4. No SBOM or signing work leaked in from M2.

---

# Phase 4 — Chart usability

**Goal:** a first-time user who runs `helm install` can reach the service and
get their documents into it.

**Why here:** these change the chart's value surface and its operator-facing
output. Phase 6 documents that surface, so it must settle first.

Chart version bump: `0.4.0` → `0.5.0` (minor; new values).

### Tasks

**4.1 — Rewrite `NOTES.txt`.**
`charts/adapt/templates/NOTES.txt` never tells the user how to reach the
service. This is the single highest-value change in the phase — it is the
first thing every user reads after `helm install`. It must answer, in order:

1. **How do I reach it?** Branch on `.Values.service.type`:
   - `ClusterIP`: the `kubectl port-forward` command, with the real ports
     (`service.port` 80 → local port), and the resulting URL
   - `NodePort`: how to get a node IP, plus `http://<node-ip>:<nodePort>`
   - `LoadBalancer`: the `kubectl get svc -w` command to watch for the
     external IP
   - `ingress.enabled=true`: the configured host(s) from `.Values.ingress.hosts`
2. **How do I log in?** Keep the existing `bootstrapAdmin` branches. Retain
   the reinstall-against-retained-PVC caveat (currently lines 22-27) — it is
   accurate and valuable.
3. **How do I get my documents in?** Point at whatever 4.2 lands on.
4. **What state am I in?** When `persistence.enabled=false`, warn that the
   document root is an `emptyDir` and all content and accounts are lost on
   pod restart. A user who installs with defaults currently gets an empty,
   account-less, ephemeral, unreachable instance with no indication that any
   of that is true.

Follow standard chart-notes practice: short, copy-pasteable, templated names
only — never a hardcoded release name.

**4.2 — Provide a supported way to seed the document root.**
This is the largest genuine product gap. Adapt's premise is that files in a
directory become APIs, and the chart offers no way to put files in that
directory. The templates have no initContainer, no ConfigMap mount, and no
`extraVolumes`. The only paths today are `kubectl cp` or enabling uploads and
then creating an admin and granting root `write`.

Choose **one** minimal mechanism and implement it well. In rough order of
cost:

- **(a) Document `kubectl cp` only.** Zero chart change. Add a
  `helm-unittest`-free runbook to Phase 6. Honest but weak; leaves the gap.
- **(b) `extraVolumes` / `extraVolumeMounts` passthrough.** Small, generic,
  and lets operators mount a ConfigMap, an NFS share, or a pre-populated
  volume. Recommended as the floor.
- **(c) `seed` initContainer.** Copies from a ConfigMap or a user-supplied
  image into the docroot on first start, skipping if non-empty. Best user
  experience, most surface area, needs care around idempotency and the
  `fsGroup` work from Phase 2.

**Recommendation: (b), plus (a) documented as the quick path.** Defer (c) to
its own milestone with a written design. Whatever is chosen, record the
decision and the rejected options in the Decision log — the next reader needs
to know this was a choice.

**4.3 — Add `values.schema.json`.**
A misspelled key (`--set persistance.enabled=true`) is currently accepted and
ignored. Add a JSON Schema covering at minimum `image`, `service`,
`persistence`, `bootstrapAdmin`, `probes`, `resources`, `env`, and
`secretEnv`. Encode the real constraints:

- `service.type` enumerated
- `service.nodePort` integer 30000–32767, or empty string
- `persistence.accessModes` enumerated
- `env` and `secretEnv` as arrays of `{name, value}` objects

Add `helm-unittest` (or `helm template`) cases proving a bad value is
rejected. Verify the schema does not reject `values-dev.yaml` or any
documented `--set` combination. Note that `.ct.yaml` already sets
`validate-chart-schema: true`, which validates `Chart.yaml`, not values —
these are different mechanisms.

**4.4 — Complete `Chart.yaml` metadata.**
`charts/adapt/Chart.yaml` has only `apiVersion`, `name`, `description`,
`type`, `version`, `appVersion`. Add `home` (`https://www.mcindi.com/adapt/`),
`sources` (`https://github.com/McIndi/adapt`), `maintainers`, `keywords`, and
`icon` if one exists. Then remove `validate-maintainers: false` from
`.ct.yaml` — it was added to work around the missing field. This matters more
after Phase 5, when `helm show chart` becomes a user's first look at the
chart.

### Verification

- `helm template` with `service.type` of each of `ClusterIP`, `NodePort`,
  `LoadBalancer`, and with `ingress.enabled=true`, produces correct and
  copy-pasteable notes in all four cases.
- Every command `NOTES.txt` emits has been executed against a live release.
- The schema rejects at least three realistic typos and accepts every
  documented value combination, including `values-dev.yaml`.
- `helm lint`, `helm unittest`, and the kind smoke test pass with
  `validate-maintainers` removed.

### Out of scope for Phase 4

Do not restructure the prose docs — Phase 6. Do not implement seeding option
(c) unless Gate 3 review explicitly approved it.

### Exit criteria

- [x] `NOTES.txt` answers reach / log in / seed / state, for all four service
  exposure modes
- [x] Seeding mechanism chosen, implemented, and the decision recorded
- [x] `values.schema.json` added, with tests
- [x] `Chart.yaml` metadata complete; `validate-maintainers` workaround removed
- [x] `Chart.yaml` version `0.5.0`

## ⏸ REVIEW GATE 4

Reviewer confirms:

1. `NOTES.txt` was rendered under all four exposure modes and every emitted
   command was actually run.
2. A user installing with defaults is now told, in the notes, that their
   instance is empty and ephemeral.
3. The seeding decision is written down with its rejected alternatives.
4. The values schema does not reject any currently documented invocation.

---

# Phase 5 — Chart distribution

**Goal:** users install the chart without cloning the repository.

**Why here:** this determines the `helm install` command in every example
Phase 6 writes. Doing it after Phase 6 means rewriting all of them.

Chart version bump: patch, if any chart file changes.

### Tasks

**5.1 — Decide and record the distribution model.**
Today every documented command is `helm install adapt ./charts/adapt`, which
requires a git clone — while the container image is published to GHCR. Users
reasonably expect a chart they can install directly. Options:

- **(a) OCI registry (recommended):** push to
  `oci://ghcr.io/mcindi/charts/adapt` on release. GHCR already hosts the
  image, `helm push`/`helm install oci://` is native in Helm 3.8+, and it
  needs no `gh-pages` branch or index maintenance.
- **(b) Classic HTTP repo** via `chart-releaser` on GitHub Pages. Note the
  conflict: `pages.yml` already publishes MkDocs to Pages, so this needs care.
- **(c) Stay clone-only** and say so explicitly in the docs as a deliberate
  choice.

If (c) is chosen, this phase is a one-line documentation change plus a
`MILESTONES.md` entry, and Phase 6 proceeds unchanged.

**5.2 — Implement publishing (if (a) or (b)).**
For (a):

- Add a `publish-chart` job, or extend `publish-image.yml`. Model it on the
  existing release-gating pattern: depend on `test.yml`, and reuse the
  release-tag/version match guard at `publish-image.yml:33-43`.
- Also require the chart's own CI to have passed — `helm lint` and
  `helm unittest` at minimum. Do not publish a chart that has not been linted.
- `helm package charts/adapt` then `helm push` to
  `oci://ghcr.io/mcindi/charts`. Needs `packages: write`.
- Decide the trigger deliberately. The chart versions independently of the
  app (`0.5.0` vs `0.4.1`), so `on: release` couples two things that are
  intentionally decoupled. Prefer a tag pattern like `chart-v*`, or a
  `workflow_dispatch` with an explicit version, and **document the release
  procedure** — likely a new `RELEASING.md` section. `MILESTONES.md:185`
  already anticipates a `RELEASING.md`.

**5.3 — Verify the round trip.**
Publish a prerelease chart version, then from a clean directory with no
checkout:

```bash
helm show chart oci://ghcr.io/mcindi/charts/adapt --version <v>
helm install adapt oci://ghcr.io/mcindi/charts/adapt --version <v>
```

Confirm `helm show chart` displays the Phase 4 metadata and that `NOTES.txt`
renders correctly from the packaged chart. A chart that publishes but cannot
be installed from a clean machine has not been verified.

### Verification

- The full install works from a machine with no repository checkout.
- The published chart version matches `Chart.yaml`.
- Chart CI passed before the publish step ran.
- The release procedure is written down and was followed once, by the
  document, to publish the test version.

### Out of scope for Phase 5

Chart signing and provenance (`helm package --sign`, `cosign`) — M2. Note the
hook point; do not implement.

### Exit criteria

- [x] Distribution model decided and recorded
- [x] Publishing implemented and gated on tests plus chart CI
- [x] Clean-machine `helm install` verified against the registry
- [x] Release procedure documented
- [x] The canonical install command for Phase 6 is stated unambiguously
      (`helm install adapt oci://ghcr.io/mcindi/charts/adapt --version
      0.5.1`, published and verified; see Decision log)

## ⏸ REVIEW GATE 5

Reviewer confirms:

1. The chart installed from the registry on a machine with no checkout.
2. Publishing cannot fire on an unlinted or untested chart.
3. Chart-versus-app version decoupling survived the trigger design.
4. Phase 6 has one canonical install command to write against.

---

# Phase 6 — Documentation consolidation

**Goal:** a user can find and follow container and Kubernetes instructions
that match what the code and chart actually do.

**Why last:** the surface has stopped moving. Write it once.

### Tasks

**6.1 — Add container documentation.**
No user-facing document mentions Docker, containers, or GHCR. Verify:
`grep -rn -i "docker\|ghcr\|podman" README.md docs/` returns nothing
meaningful today. The image is published and successfully building
(`publish-image.yml`, verified for v0.4.0 and v0.4.1), but no user is told it
exists.

Write a **Container** section — its own page under `docs/manual/`, referenced
from the new nav group in 6.4 — covering:

- Image coordinates: `ghcr.io/mcindi/adapt-server`, tag policy (`<version>`
  for every release, `latest` for non-prereleases per
  `publish-image.yml:50-60`), and the architectures from Phase 3
- `docker pull` and a working `docker run` with a bind-mounted document root,
  including the UID 1000 ownership requirement from Phase 2.3 — a bind mount
  owned by the host user will fail for a non-root container, and users will
  hit this immediately
- How to create the first superuser in a container (`docker exec -it`, with
  the same TTY note as 1.4)
- Which `ADAPT_*` environment variables apply, cross-referencing the existing
  list at `docs/manual/installation.md:137-166`
- The default `CMD` and how to override it (`Dockerfile:24`)
- Verifying the image (labels, digest). Signature verification is M2 — if
  mentioned at all, mark it `Future work` per the documentation contract.

**6.2 — Fix the installation page structure.**
`docs/manual/installation.md:243` is the
`Manual navigation: Previous | Index | Next` footer, and the entire Helm
section runs from line 245 to the end of the file. On the rendered site the
Kubernetes content appears below the "next page" link. Either move the Helm
content above the footer, or — preferred — move deployment content to its own
page(s) per 6.4 and leave `installation.md` covering local installation.

**6.3 — Collapse the three copies of the Helm docs.**
The same content exists in `README.md:211-302`,
`docs/manual/installation.md:245-405`, and `charts/adapt/README.md`, and has
already drifted. `charts/adapt/README.md` is the thinnest and the one GitHub
renders when browsing the chart: no `bootstrapAdmin`, no NodePort, no
`existingClaim`, no persistence-required warning.

Establish one canonical location — the docs site — and reduce the others:

- `docs/manual/` (or the new deployment page): canonical, complete
- `README.md`: the shortest working install, and a link
- `charts/adapt/README.md`: what the chart is, the canonical install command
  from Phase 5, a values table or a pointer to `values.yaml`, and a link.
  It must not contradict the canonical page.

Delete duplicated persistence tables rather than syncing them.

**6.4 — Add deployment to the nav.**
`mkdocs.yml` has no Docker, Kubernetes, or Deployment entry, so the whole
deployment story is undiscoverable from the published site. Add a nav group,
for example:

```yaml
  - Deployment:
      - Overview: manual/deployment.md
      - Container: manual/container.md
      - Kubernetes (Helm): manual/kubernetes.md
```

Keep `docs/manual/index.md` and the `Previous | Index | Next` footers
consistent with the new structure — those footers are hand-maintained and
will need updating on adjacent pages too.

**6.5 — Document the image values and the day-1 walkthrough.**
`image.repository`, `image.tag`, and `imagePullSecrets` appear in no
document, which blocks private-registry and air-gapped users. Add them, with
digest pinning noted as the way to satisfy a cluster that requires it.

Then write the missing end-to-end walkthrough. Today a user must assemble it
from scattered pieces. One ordered path, verified by running it:

1. Install with persistence enabled and `bootstrapAdmin.enabled=true`
2. Retrieve the generated password (correct Secret name per 1.3)
3. Reach the service (the exposure mode chosen)
4. Get documents into the document root (the Phase 4.2 mechanism)
5. Generate permissions — `adapt admin create-permissions <root> __all__`
6. Create a regular user and assign a group
7. Optionally enable uploads, including the root `write` permission
   requirement already described at `docs/manual/installation.md:205-210`

**6.6 — Add deployment troubleshooting.**
`docs/manual/troubleshooting.md` has no Kubernetes or container content at
all (verified: zero matches for `helm|kube|pod|cluster|docker`). Add entries
for the failures this review predicts and Phases 2–5 touch:

- Pod `CrashLoopBackOff` from a PVC the container cannot write (`fsGroup`,
  2.2)
- Bind-mount permission denied on `docker run` (UID 1000, 2.3)
- Liveness restarts during startup indexing (`startupProbe`, 2.4)
- `bootstrapAdmin` rejected without persistence — the intentional
  `fail()` at `admin-bootstrap-job.yaml:3`
- Failed bootstrap Job blocks reinstall because Helm keeps the failed hook
  for diagnosis. Delete the failed Job before a reinstall. Then make sure
  that its pods release the PVC.
- Bootstrap Job stuck `ContainerCreating` because an `RWO` volume is already
  attached to a node the Job was not scheduled to. This is a real multi-node
  constraint that no current document mentions; the `RWO` guidance at
  `docs/manual/installation.md:321-328` covers replicas only.
- Empty landing page after a default install

**6.7 — Reconcile the status documents.**
Update `PROJECT_STATUS.md` and `MILESTONES.md` to describe what landed across
Phases 1–6. Confirm M2's SBOM and signing scope still reads correctly after
the Phase 3 and 5 changes.

### Verification

- **Every command in every changed document was executed**, against a live
  cluster for the Kubernetes pages and a real Docker daemon for the container
  page. List them in the Decision log. This is the finding class that produced
  1.1, 1.3, and 1.4; the exit bar is execution, not review.
- `mkdocs build --strict` passes (`pages.yml` already gates on it).
- No internal link is broken; the `Previous | Index | Next` footers are
  consistent.
- No Helm or container fact appears in two places with two different values.
- Nothing unimplemented is described as current behavior.

### Exit criteria

- [x] Container documentation exists, and every command in it was run
- [x] Deployment content is in the nav and reachable — locally and on the
      published site (`https://www.mcindi.com/adapt/manual/kubernetes/`,
      verified live after `pages.yml` run 33502635532)
- [x] One canonical Helm document; the other two reduced to pointers
- [x] Day-1 walkthrough written and executed end to end, using release name
      `myadapt` (not `adapt` — see the round-1 and round-2 Finding 1
      write-ups above); the page's canonical install command and every
      other example were also brought into line with `myadapt` in round 2
- [x] Deployment troubleshooting added, including the release-name/
      service-link collision found during Gate 6 round 1
- [x] `mkdocs build --strict` passes
- [x] `PROJECT_STATUS.md` and `MILESTONES.md` reconciled, including the
      `v0.5.0`/image-`0.5.0` correction and the Docs lane restored to `OK`
      after the live publish was confirmed

## ⏸ REVIEW GATE 6 — final

Reviewer confirms:

1. A reader who knows nothing about this project can go from zero to a
   working, populated, logged-in instance using only the published docs, by
   either the container or the Helm path.
2. Every command in the changed documents was executed, and the list is in
   the Decision log.
3. The duplicated Helm docs are gone, not merely synchronized.
4. Nothing in the documentation promises behavior that does not exist.
5. `mkdocs build --strict` passes and the published site nav exposes
   deployment.

---

## Decision log

Append to this section as each phase is implemented. Phases run in separate
sessions with no shared context, so this is the only channel between them.
Record, per phase:

- **Decisions made**, with the options rejected and why. Named decision points
  are 2.1 (selector approach), 3.3 (Python version), 3.4 (digest pinning),
  4.2 (seeding mechanism), and 5.1 (distribution model).
- **Verification performed** — the commands actually executed, the cluster or
  storage driver used, and the results. Phases 1, 4, and 6 require a list of
  commands run; Phase 2 requires the storage driver `fsGroup` was tested
  against; Phase 3 requires the manifest inspection output.
- **Findings routed forward**, especially chart failures Phase 1's first CI
  run surfaces.
- **Residual risk** accepted at the gate, and anything left unverified.
- **Chart version** after the phase, confirming the manual bump happened.

### Phase 1

Completed on 2026-08-12. Review Gate 1 passed after the F1 correction.

- **Decisions made:** Added the `main` push trigger with the same path filter
  as the pull-request trigger. The version-increment guard remains unchanged.
  Documentation uses the chart's `adapt.fullname` rule for resource names.
  Manual superuser creation now allocates a TTY because the command prompts
  for a password. The F1 correction keeps `local-path` as the k3s overlay
  default. The documentation gives `standard` and `hostpath` overrides for
  other local clusters.
- **Verification performed:** Dispatched Helm CI run
  [31600019069](https://github.com/McIndi/adapt/actions/runs/31600019069)
  against `main` at `60ea9b9`. Helm lint passed. All 25 unit tests passed.
  Ephemeral and persistent install tests passed on kind node images for
  Kubernetes 1.31.2, 1.32.0, and 1.33.0. The version-increment job skipped as
  designed because the event was `workflow_dispatch`.
- **Local verification:** Helm 4.2.3 linted chart version 0.3.3 successfully.
  All 25 unit tests passed with `helm-unittest` 0.6.3. The plugin installer
  failed on Windows, so the release archive was extracted into the plugin
  directory. The Linux CI job installed the same plugin version normally.
  Helm rendering produced `storageClassName: standard` and
  `storageClassName: hostpath` with the documented overrides. The strict
  MkDocs build passed after the F1 correction.
- **Commands checked:** The audit covered these commands and variants:
  - `git clone https://github.com/McIndi/adapt.git`
  - `helm install adapt ./charts/adapt`
  - `helm install` with the dynamic-PVC values
  - `kubectl apply -f my-adapt-pvc.yaml`, followed by `helm install` with
    `persistence.existingClaim=my-adapt-pvc`
  - `helm install` with `bootstrapAdmin.enabled=true`
  - `kubectl get secret adapt-bootstrap-admin ...` and the general
    `<release>-adapt-bootstrap-admin` variant
  - `helm get notes <release>`
  - `kubectl exec -it deploy/<release>-adapt -- adapt addsuperuser ...`
  - `helm install` with the NodePort values
  - `helm upgrade --install adapt charts/adapt -f charts/adapt/values-dev.yaml`
  - The inline `helm template`, `helm upgrade`, `helm uninstall`, and
    `kubectl port-forward` references
  `git ls-remote` checked the clone URL. Helm rendering checked each chart
  variant. The source and templates checked the kubectl commands. The CI run
  executed both install modes and `helm test` on all three clusters.
- **Findings routed forward:** No chart failures appeared. Phase 2 keeps its
  existing chart-correctness findings.
- **Residual risk:** GitHub warned that `actions/checkout@v4` and
  `azure/setup-helm@v4` target deprecated Node.js 20 and currently run on
  Node.js 24. This warning did not fail CI. The local machine has no container
  runtime, so the GitHub kind jobs supplied the live-cluster evidence. The new
  `push` trigger remains unverified until a chart-affecting push reaches
  `main`.
- **Chart version:** 0.3.3. `appVersion` remains 0.4.1.

### Phase 2

Completed on 2026-08-12. Review Gate 2 passed after the F2 correction.

- **Decisions made:** Kept the Deployment's immutable
  `spec.selector.matchLabels` unchanged so existing releases can upgrade in
  place. Added `app.kubernetes.io/component: server` to the Deployment pod
  template and Service selector, with distinct `bootstrap` and `test` labels
  on the hook pods. Custom `podLabels` render before the reserved selector
  labels so they cannot override them. Also narrowed the Deployment pod
  labels from `adapt.labels` to stable selector labels, avoiding rollouts
  caused only by chart or app metadata changes. The bootstrap Job bypasses
  password-strength validation only for its chart-generated 24-character
  password; passwords from an existing Secret are validated normally. A
  rejected non-interactive password now makes `adapt addsuperuser` exit 1,
  so the hook Job and Helm operation fail visibly instead of reporting false
  success. Existing users remain a successful no-op for upgrade safety. Gate
  2 authorized the required scope extension into `adapt/` because the chart
  change alone cannot produce a nonzero process exit.
- **Upgrade behavior:** The Deployment's immutable selector remains unchanged,
  but the 0.4.0 Service immediately requires `component: server`. Existing
  pre-0.4.0 pods therefore leave the Service endpoints until the replacement
  pod is Ready. This creates a brief endpoint gap during upgrade, especially
  for the default single replica. The Deployment selector also continues to
  overlap hook pods on name and instance; their Job owner prevents ReplicaSet
  adoption, and removing that overlap would require an immutable-selector
  migration.
- **Verification:** `helm lint charts/adapt` passed with Helm v3.18.6.
  `helm unittest charts/adapt` passed 31 tests in 5 suites using
  helm-unittest v0.6.3, up from 25 tests. Default and bootstrap-enabled
  templates rendered for generated and existing bootstrap secrets. A source
  check confirmed the Dockerfile pins both `groupadd --gid 1000` and
  `useradd --uid 1000 --gid 1000`. An end-to-end Python subprocess regression
  test confirmed a weak non-interactive `addsuperuser` password exits 1 and
  creates no user. The full Python suite passed 333 tests with 1 skipped after
  this Gate 2 correction.
  The 2.3 Helm test locks the chart side of that UID/GID contract, but cannot
  itself fail on a Dockerfile-only regression because Helm cannot read files
  outside the chart. The reviewer built the image with Podman and imported it
  into k3s. The image ran as UID 1000 and GID 1000. The reviewer also verified
  that `/data` used group 1000 with the setgid bit and accepted a write.
  The live Service excluded a ready decoy pod with the old labels. The Helm
  test succeeded. The startup probe had a 30-attempt, 10-second period. A weak
  existing-Secret password made all Job attempts exit 1 and made Helm fail.
  The generated-password path created one administrator. Valid credentials
  returned HTTP 200, and invalid credentials returned HTTP 401. The reviewer
  removed the test namespace and image after the verification.
- **Gate 1 routed items:** None; the Phase 1 chart run reported no chart
  failures.
- **Findings routed forward:** A failed bootstrap Job remains after
  `helm uninstall` because its hook policy keeps failed resources for
  diagnosis. The Job can keep the PVC in `Terminating` and block a reinstall.
  Phase 6.6 will document how to delete the failed Job and release the PVC.
- **Residual risk:** The k3s `local-path` test proved that `fsGroup` works,
  but it did not prove that `fsGroup` is necessary. This provisioner creates
  writable hostPath directories. A non-hostPath driver that presents
  `root:root 0755` storage remains untested. Drivers that ignore `fsGroup`
  require driver-specific `persistence.annotations` or a pre-chowned
  `existingClaim`.
- **Chart version:** 0.4.0. `appVersion` remains 0.4.1.

### Phase 3

Implementation completed on 2026-08-17. Reviewer ran Gate 3 on 2026-08-20 and
did not pass it — see below. Two review findings were corrected the same day:
`Dockerfile`'s metadata-first `COPY` was missing `LICENSE` (declared as a
license file in `pyproject.toml`, and present under the old `COPY . /app`),
and the `PROJECT_STATUS.md` packaging row still described the pre-Phase-3
image instead of the Python 3.14 base, caching split, OCI labels, and
`/health` healthcheck.

- **Decisions made:** Moved the image to Python 3.14 because every current CI
  test job uses 3.14; the package's `>=3.11` support declaration remains
  unchanged. Dependency resolution now reads the PEP 621 dependency list from
  `pyproject.toml` before the application source is copied, then installs the
  local package without dependencies. Added OCI labels with local defaults,
  release-supplied build arguments, and a Python-based Docker healthcheck for
  plain `docker run` users. Added QEMU and an explicit linux/amd64,
  linux/arm64 Buildx target. The base image remains tag-based rather than
  digest-pinned because the project currently follows moving Python slim
  security updates and has no digest update automation; digest pinning should
  return with the M2 supply-chain work.
- **Reviewer verification (2026-08-20):** Added a reusable `Vagrantfile`
  (2 CPUs, 4 GB RAM, Docker, Buildx, QEMU) to get a Linux container runtime,
  with its local state ignored in `.gitignore`. Confirmed: native amd64 image
  builds; `adapt --help` works; all six OCI labels carry the supplied values;
  the default server starts as the non-root `adapt` user; Docker reports the
  container healthy and `/health` returns 200; the Python suite passes
  (333 passed, 1 skipped); no SBOM/signing work leaked in. The emulated arm64
  build resolved and installed Debian's arm64 `ffmpeg` and selected native
  aarch64 Python wheels, but the reviewer stopped it after roughly 28 minutes
  before it finished — arm64 remains unverified end-to-end. Helm could not be
  rerun; it is not installed on the reviewer's host.
- **Findings routed forward:** None.
- **Residual risk:** `ghcr.io/mcindi/adapt-server:latest` currently contains
  only `linux/amd64` plus its attestation manifest — no arm64 manifest has
  been published yet, which is the decisive Gate 3 blocker. Emulated arm64
  build time (>28 minutes, unfinished) may need a native arm64 runner or a
  documented tradeoff if it proves impractical in CI. No SBOM or signing work
  was added; those remain M2 scope.
- **Chart version:** unchanged at 0.4.0 because no chart file changed.

## ⏸ Review Gate 3 — not passed (2026-08-20)

The published `0.4.2` image manifest was inspected and contains both
`linux/amd64` and `linux/arm64`; the Phase 3 arm64 blocker is resolved.

### Phase 4

Implementation completed on 2026-08-21. Review Gate 4 is pending.

- **Decisions made:** Chose option 4.2(b), `extraVolumes` plus
  `extraVolumeMounts`, as the supported seeding mechanism. It supports
  ConfigMaps, NFS, and pre-populated claims without adding an initContainer's
  copy and idempotency policy. The quick path remains `kubectl cp`, which is
  emitted in `NOTES.txt`. Rejected option 4.2(a) as the only mechanism because
  it does not support repeatable or shared sources. Deferred option 4.2(c)
  because an initContainer needs a separate design for first-start detection,
  ownership, and persistence semantics.
- **Verification performed:** The new `values.schema.json` parses as valid
  JSON. On the Vagrant VM, `helm lint charts/adapt` passed and the schema
  script accepted `values-dev.yaml` while rejecting nine invalid values:
  unknown root key, invalid service type, invalid NodePort, invalid access
  mode, `bootstrapAdmin.enabeld`, `probes.livness`, `adapt.rootPth`,
  `ingress.enabeld`, and `resources.limtis`. All 52 helm-unittest tests pass,
  including cases for TLS ingress URLs with multiple paths, schema typo
  rejection in required sections, external-root guards, namespace-qualified
  commands, and retained bootstrap Job notes. Live verification ran on the
  `adapt-phase4-final` kind cluster in namespace `phase4-review`: ClusterIP
  install succeeded; `kubectl get svc ... -n`, pod lookup, `kubectl cp`,
  `kubectl exec -n`, and `kubectl port-forward ... -n` all ran successfully;
  `/health` returned OK through the port-forward; NodePort install succeeded
  and `/health` returned OK through `http://172.18.0.2:30080`; Ingress install
  succeeded and rendered separate `https://example.test/one` and
  `https://example.test/two` notes; bootstrap-admin install succeeded, its
  retained Job reported `Complete`, and the namespace-qualified Secret lookup
  returned the generated password data. A follow-up verification after
  reordering `NOTES.txt` ran the emitted interactive manual-superuser command
  `kubectl exec -it -n phase4-login deploy/phase4-login-adapt -- adapt addsuperuser /data --username admin`
  with a disposable test password; the command created `admin` with
  `is_superuser=1` in the `users` table. The emitted Secret retrieval pipeline
  `kubectl get secret phase4-secret-adapt-bootstrap-admin -n phase4-secret -o jsonpath='{.data.password}' | base64 -d && echo`
  returned the generated password text. Helm tests succeeded for the
  ClusterIP, NodePort, bootstrap-admin, and Ingress releases. The
  LoadBalancer command `kubectl get svc phase4-lb-adapt -n phase4-review -w`
  ran and showed the expected kind state with `EXTERNAL-IP <pending>`.
- **Residual risk:** The emitted `kubectl cp` command requires a Ready server
  pod and a local `./documents` directory. The values schema intentionally
  keeps several Kubernetes pass-through objects permissive while enforcing the
  Phase 4 value constraints. The kind cluster does not provide a real external
  LoadBalancer address, so the LoadBalancer watch command was executed but no
  external IP was assigned.
- **Chart version:** 0.5.0. `appVersion` remains 0.4.2.

### Phase 5

Implementation completed on 2026-08-29, corrected on 2026-08-30 after
reviewer findings, verified via release candidate on 2026-08-31, and closed
with the stable release on 2026-08-31. Review Gate 5 passes.

- **Decisions made:** Chose option 5.1(a), OCI distribution through GHCR at
  `oci://ghcr.io/mcindi/charts/adapt`. It reuses the existing GHCR registry,
  supports Helm's native `helm push` and `helm install oci://` commands, and
  requires neither a `gh-pages` branch nor repository-index maintenance.
  Rejected option (b) because the existing MkDocs Pages deployment would make
  shared Pages publishing unnecessarily complex. Rejected option (c) because
  clone-only installation is an avoidable barrier now that the container
  image is already published. Chart releases trigger only from
  `chart-v<chart-version>` tags, preserving the chart's independent version
  lifecycle from application `v<version>` releases. Following reviewer
  feedback, the first published chart is a release candidate,
  `0.5.1-rc.1` (tag `chart-v0.5.1-rc.1`), rather than the stable `0.5.1`, so
  the clean-machine round trip does not consume the first stable version.
  `0.5.1` will be re-tagged and published as the real release now that the rc
  round trip has passed.
- **Implementation:** Added `publish-chart.yml`. Its push trigger accepts
  only `chart-v*` tags. It calls `test.yml` and the full reusable Helm CI
  workflow before packaging and pushing the chart. It verifies that the tag
  version equals `charts/adapt/Chart.yaml`, then pushes with the
  GitHub-scoped package token. `helm-ci.yml` now supports `workflow_call`;
  its lint/schema/unit and kind smoke jobs remain the concrete chart gate.
  `RELEASING.md` documents the chart release procedure and the canonical
  Phase 6 install command is
  `helm install adapt oci://ghcr.io/mcindi/charts/adapt --version <chart-version>`.
- **2026-08-30 correction:** A reviewer found two issues before any tag was
  pushed. High: the tag/version-match step parsed `Chart.yaml` (YAML) with
  Python's `tomllib`, which raises `TOMLDecodeError` on any real chart file —
  publishing would have failed before packaging on every run. Fixed by
  parsing the version with `helm show chart charts/adapt | awk -F': '
  '/^version:/ {print $2}'` instead, and removed the now-unused
  `actions/setup-python` step from `publish-chart.yml`. Medium: Phase 5 calls
  for testing with a prerelease chart version, but the chart was left at the
  stable `0.5.1`. Fixed by bumping `charts/adapt/Chart.yaml` to
  `0.5.1-rc.1` and changing the chart README's quick-install example to a
  generic `<chart-version>` placeholder instead of a hardcoded version.
  `azure/setup-helm` was also pinned to `v3.21.4` in both workflows.
- **Registry publication (2026-08-31):** Tag `chart-v0.5.1-rc.1` pushed to
  `main` at `705a187`. GitHub Actions run
  [33385954119](https://github.com/McIndi/adapt/actions/runs/33385954119)
  succeeded end to end: the `test` workflow (docs, both FastAPI-version test
  jobs, dependency-audit), the full `helm-ci` workflow (lint/unittest, and
  `kind` install smoke tests on Kubernetes 1.31.2, 1.32.0, and 1.33.0 — the
  version-increment job correctly skipped, since it only runs on pull
  requests), and finally `Package and push chart to GHCR`, which exercised
  the corrected `helm show chart | awk` version-match step for the first
  time against the real chart and passed.
- **Clean-machine round trip (2026-08-31):** On the Vagrant VM, from `/tmp/
  adapt-clean-test` (no repository checkout in that directory) and with no
  registry login (`helm registry logout ghcr.io` run first to rule out
  cached credentials): `helm show chart oci://ghcr.io/mcindi/charts/adapt
  --version 0.5.1-rc.1` pulled anonymously and printed the expected Phase 4
  metadata (`home`, `sources`, `maintainers`, `keywords`, `version
  0.5.1-rc.1`, `appVersion 0.4.2`) — confirming the published package is
  publicly readable without authentication, resolving the open visibility
  question from the review. A fresh `kind` cluster
  (`adapt-phase5-gate`, node image `kindest/node:v1.37.0`) was created, and
  `helm install adapt-gate oci://ghcr.io/mcindi/charts/adapt --version
  0.5.1-rc.1 --wait` succeeded, rendering the same NOTES content produced by
  local packaging. The resulting pod reached `Running`/`1/1 Ready`, and
  `curl` through `kubectl port-forward svc/adapt-gate 18000:80` returned
  `HTTP 200` from `/health`. The release was uninstalled and the kind cluster
  deleted afterward.
- **Stable release (2026-08-31):** `charts/adapt/Chart.yaml` bumped from
  `0.5.1-rc.1` to `0.5.1`; committed and pushed to `main`. Tag `chart-v0.5.1`
  pushed. GitHub Actions run
  [33388716712](https://github.com/McIndi/adapt/actions/runs/33388716712)
  succeeded end to end (docs, both FastAPI-version test jobs,
  dependency-audit, Helm lint/unittest, kind smoke tests on Kubernetes
  1.31.2/1.32.0/1.33.0 — version-increment skipped as designed — then
  package-and-push). Anonymous `helm show chart
  oci://ghcr.io/mcindi/charts/adapt --version 0.5.1` on the Vagrant VM, from
  a clean directory with no cached registry login, pulled digest
  `sha256:8e1aceb63d4e5b16edfd1435499c8b8c6425ab0f424d9e7de41ddbd75ddc2c82`
  and printed the expected metadata. A repeat `kind` install was not run for
  the stable tag: the chart content is identical to the already
  install-verified `0.5.1-rc.1` (only the version string differs), so the
  anonymous `helm show chart` pull was the only additional check needed to
  close out the stable publish.
- **Findings routed forward:** None; the round trip surfaced no new chart
  defects.
- **Residual risk:** OCI chart signing and provenance were intentionally not
  added; they remain M2 work.
- **Chart version:** 0.5.1, published to
  `oci://ghcr.io/mcindi/charts/adapt` and verified. `appVersion` remains
  0.4.2.

### Phase 6

Implementation completed on 2026-08-31. Review Gate 6 passed on 2026-09-02
after three correction rounds.

- **Decisions made:** Added `docs/manual/deployment.md` as a short overview
  page, `docs/manual/container.md` for the published image, and
  `docs/manual/kubernetes.md` as the single canonical Helm reference,
  under a new top-level `Deployment` nav group in `mkdocs.yml` (sibling to
  `User Manual`/`Reference`, not spliced into the linear
  Overview→...→Known Limitations footer chain, except that
  `known_limitations.md` now links forward into it). `docs/manual/installation.md`
  keeps only local/PyPI/source installation and a one-line pointer; its old
  Helm section (`### Persistence modes` through `### Local development
  overlay`) was deleted, not duplicated. `README.md`'s Helm section was cut
  to a four-line container + chart quick-install plus a link.
  `charts/adapt/README.md` keeps its existing minimal quick-install and now
  links to `kubernetes.md` and documents `image`/`imagePullSecrets` as
  chart-surface pointers rather than duplicating their prose. The day-1
  walkthrough and troubleshooting entries went into `kubernetes.md` and
  `troubleshooting.md` respectively, not into `deployment.md`, since every
  step is Kubernetes-specific.
- **New finding surfaced while writing the walkthrough (documented, not a
  regression):** Adapt discovers resources once at process startup — copying
  a file into a running pod's document root (via `kubectl cp` or a volume
  mounted after startup) does not make it reachable until the pod restarts.
  This was previously undocumented. `kubernetes.md` and `troubleshooting.md`
  now state it explicitly, and it was reproduced live (see verification).
- **New finding — image digest pinning does not work through chart values:**
  the Deployment template unconditionally renders
  `{{ image.repository }}:{{ image.tag }}`; setting `image.repository` to a
  `repo@sha256:...` reference still gets `:<tag>` appended, producing an
  invalid image reference. Confirmed with `helm template` against the
  published chart. Documented as a known limitation in `kubernetes.md`
  rather than silently advertising an unsupported pattern.
- **Verification performed (container, on the Phase 3 Vagrant VM):**
  `docker pull ghcr.io/mcindi/adapt-server:0.4.2`; `docker image inspect`
  confirmed all six OCI labels; `docker buildx imagetools inspect` confirmed
  the `linux/amd64` + `linux/arm64` manifest list. `docker run` with a bind
  mount `chown`-ed to `1000:1000` started successfully and `/health`
  returned `200`; `docker exec ... adapt addsuperuser` created a superuser
  non-interactively inside the running container. Reproduced the
  documented failure mode with a `root:root`-owned bind mount: `adapt check`
  raised `PermissionError: [Errno 13] Permission denied: '/data/.adapt'`,
  confirming the UID-1000 requirement is real and not just theoretical.
  Verified `adapt --help` runs and that appending arguments after the image
  name overrides the default `CMD`.
- **Verification performed (Kubernetes day-1 walkthrough, on a fresh `kind`
  cluster, `adapt-phase6`):** `helm install` with
  `persistence.enabled=true,bootstrapAdmin.enabled=true` succeeded and
  rendered the documented `NOTES.txt`; retrieved the generated password from
  `<release>-adapt-bootstrap-admin`; port-forwarded and got `HTTP 200` from
  `/health`; `kubectl cp` copied a test document into the running pod, and
  it returned `404` until `kubectl rollout restart deployment/...` completed,
  after which the same URL returned `401` (unauthenticated, but now
  routed) — this is the discovery-is-startup-only finding above, caught
  live rather than assumed; ran `adapt admin create-permissions __all__`,
  `list-groups`, `create-user`, and `add-to-group` via `kubectl exec` and
  confirmed the resulting group/user state; `helm upgrade --reuse-values`
  with `--set-string env[...].value=...` enabled uploads, after first
  reproducing the values-schema rejection of unquoted `--set` boolean/number
  values (`got boolean, want string` / `got number, want string`) that led
  to documenting `--set-string` explicitly rather than `--set`. Cluster and
  temporary directories were deleted afterward.
- **`mkdocs build --strict`:** passed with the new `Deployment` nav group
  and pages (`python -m mkdocs build --strict`, exit code 0, no
  warnings/errors in the log).
- **Findings routed forward:** None new beyond the two documented above (both
  captured as documentation, not deferred as chart or image work).
- **Residual risk:** The image digest-pinning gap (above) is a real chart
  limitation, not just a documentation gap — it is noted here for a future
  chart-template fix but intentionally left as documentation-only for this
  phase, since Phase 6 is scoped to docs. `docs/manual/security.md` still
  does not cover the upload attack surface (pre-existing gap, tracked in
  `PROJECT_STATUS.md`, out of this phase's scope).
- **Chart version:** unchanged at 0.5.1; no chart file was touched in this
  phase.

#### Review Gate 6 round 1 — failed (2026-09-01)

The reviewer found the walkthrough itself did not work end-to-end
(release name `adapt-adapt` used throughout instead of the chart's actual
collapsed name), two shell-redirection foot-guns (`<strong-password>`,
`<resource>_readonly` as literal, unquoted placeholders), the live site not
yet republished, an incomplete command-execution record, stale version
references (`v0.4.1`/`0.4.2` instead of the actual `v0.5.0`), and a
walkthrough that never explicitly confirmed a login. All six findings were
addressed the same day, re-verified on a fresh `kind` cluster and the Phase 3
Vagrant VM, before Gate 6 was resubmitted:

- **Finding 1 (High, resource names) — root cause was worse than a
  documentation typo.** Testing the corrected walkthrough with release name
  `adapt` (matching every other example in the chart's docs) reproduced a
  real chart bug, not just wrong names in prose: `adapt.fullname` collapses
  to the bare release name `adapt` whenever the release name contains
  `adapt`, so the Service is also named `adapt`. Kubernetes then injects
  Docker-links-style env vars into every pod in the namespace, named after
  each Service — for a Service named `adapt`, that includes `ADAPT_PORT`,
  which collides with and overrides Adapt's own `ADAPT_PORT` config
  variable. The server crash-loops with `ADAPT_PORT must be an integer`.
  Confirmed live: `helm install adapt oci://ghcr.io/mcindi/charts/adapt
  --version 0.5.1 --set persistence.enabled=true
  --set bootstrapAdmin.enabled=true --set bootstrapAdmin.username=admin
  --wait` timed out; `kubectl describe pod` showed
  `CrashLoopBackOff`; `kubectl logs --previous` showed
  `ADAPT_PORT must be an integer`. Reinstalling with release name `myadapt`
  (still exercises the `fullname` collapse rule, since it contains `adapt`,
  but its Service renders as `myadapt` → env prefix `MYADAPT_*`, not
  `ADAPT_*`) installed cleanly. This is a real, currently-unfixed chart gap,
  not merely a documentation error — `kubernetes.md` now carries a
  prominent warning under **Install**, the day-1 walkthrough uses `myadapt`
  throughout, `known_limitations.md` gained a dedicated entry, and
  `troubleshooting.md` gained a matching entry. `README.md` and
  `charts/adapt/README.md`'s quick-install examples were also switched to
  `myadapt` with a one-line pointer, since they are exactly the surface a
  new user copy-pastes first. The chart template itself (`enableServiceLinks:
  false` on the pod spec is the standard fix) was intentionally **not**
  patched in this phase — Phase 6 is scoped to documentation, and a chart
  fix needs its own version bump, `helm-unittest` case, and gate, per the
  conventions at the top of this document. It is recorded here, in
  `PROJECT_STATUS.md`, and in `known_limitations.md` as an open gap rather
  than silently routed around.
- **Finding 2 (High, shell foot-guns) — fixed by removing angle-bracket
  placeholders from copy-pasteable code blocks.** `kubernetes.md`'s
  walkthrough now sets `EDITOR_PASSWORD='choose-your-own-password'` in a
  shell variable and passes `--password "$EDITOR_PASSWORD"`
  (quoted, no literal `<...>`), and uses the concrete, verified group name
  `readme_readonly` (matching the `readme.md` seeded earlier in the same
  walkthrough) instead of a `<resource>_readonly` placeholder.
  `container.md`'s `addsuperuser` example does the same with
  `ADMIN_PASSWORD`. Both were re-run verbatim (see verification below) to
  confirm they now execute without modification.
- **Finding 3 (High, unpublished site) — fixed.** Committed
  (`dfe94ae`) and pushed all Gate 6 corrections to `main`, then ran
  `gh workflow run pages.yml --ref main` (run
  [33502635532](https://github.com/McIndi/adapt/actions/runs/33502635532))
  since `pages.yml` only triggers on `release`/`workflow_dispatch`, not on
  plain pushes. The run passed every gate (`test` reusable workflow: docs,
  both FastAPI-version test jobs, dependency-audit) then `build`/`deploy`.
  Fetched the live pages afterward to confirm: `https://www.mcindi.com/adapt/manual/kubernetes/`
  now renders the corrected page — the release-name warning under
  **Install**, the `myadapt` walkthrough with the quoted `$EDITOR_PASSWORD`
  variable and the login step, and the nav sidebar listing all ten
  `kubernetes.md` sections — and `https://www.mcindi.com/adapt/` confirms
  the site rebuilt. `PROJECT_STATUS.md`'s Docs lane can move back to `OK`
  now that the live site matches the corrected local docs.
- **Finding 4 (Medium, incomplete execution record) — addressed by
  re-verifying and enumerating every distinct command in the changed
  documents**, not just the walkthrough (see verification below).
- **Finding 5 (Medium, stale versions) — fixed.** `PROJECT_STATUS.md`'s
  business-logic and packaging rows referenced `v0.4.1`/image `0.4.2`; the
  actual current release is `v0.5.0` (confirmed via `gh release list` and
  `git tag`), and the actual current multi-arch image tag is `0.5.0`
  (confirmed via `docker buildx imagetools inspect`). Both were corrected.
  `container.md`'s six image-tag references were changed from `0.4.2` to
  `0.5.0` and re-verified against the real `0.5.0` image (pull, label
  inspect, manifest inspect, bind-mount run, non-interactive
  `addsuperuser`, `--help`, `CMD` override). Also newly recorded: the
  chart's `appVersion` (`0.4.2`) has drifted behind the app's `v0.5.0` —
  this does not break installs (the tag still resolves to a real image) but
  is real drift, now noted in `PROJECT_STATUS.md` rather than left
  unmentioned.
- **Finding 6 (Medium, walkthrough not novice-complete) — fixed.** Step 3
  now explicitly says `kubectl port-forward` blocks its terminal and to run
  the following commands in a second terminal (or background it). A new
  step 7 has the reader actually log in — either through a browser at
  `/auth/login`, or with a `curl -X POST .../auth/login -d
  username=editor -d password="$EDITOR_PASSWORD"` that must return `200`
  with a `set-cookie: adapt_session=...` header — and then read the granted
  resource with that session cookie, closing the "populated, logged-in
  instance" gap Gate 6 requires.

**Verification performed (container, re-run against the current `0.5.0`
image, on the Phase 3 Vagrant VM):** `docker pull
ghcr.io/mcindi/adapt-server:0.5.0`; `docker image inspect` confirmed all six
OCI labels with `version: "0.5.0"`; `docker buildx imagetools inspect`
confirmed the `linux/amd64` + `linux/arm64` manifest list. `docker run` with
a bind mount `chown`-ed to `1000:1000` started successfully and `/health`
returned `200` with `"version":"0.5.0"`; `docker exec ... adapt
addsuperuser` with the corrected `$ADMIN_PASSWORD` variable form created a
superuser non-interactively; `adapt --help` and the `adapt serve ... --port
9090` `CMD` override both ran. Test container and bind-mount directory were
removed afterward.

**Verification performed (Kubernetes, on a fresh `kind` cluster,
`adapt-gate6`, enumerating every distinct command touched by this phase's
documents, not only the walkthrough):**

- Reproduced Finding 1 with release name `adapt` (`CrashLoopBackOff`,
  `ADAPT_PORT must be an integer` in `kubectl logs --previous`), then
  `helm uninstall adapt` and `kubectl delete pvc adapt` to reset.
- Full day-1 walkthrough with release name `myadapt`: `helm install
  myadapt ... --set persistence.enabled=true
  --set bootstrapAdmin.enabled=true --set bootstrapAdmin.username=admin
  --wait` (succeeded; rendered notes referencing `myadapt`/
  `myadapt-bootstrap-admin`, not the collapsed-wrong `myadapt-adapt` form);
  `kubectl get secret myadapt-bootstrap-admin -o jsonpath='{.data.password}'
  | base64 -d`; `kubectl port-forward svc/myadapt 8000:80` plus `curl
  http://localhost:8000/health` (`200`); `kubectl cp` of a seeded
  `readme.md` into the running pod, confirmed `404` before restart;
  `kubectl rollout restart deployment/myadapt` +
  `kubectl rollout status`, confirmed `401` (routed, unauthenticated) after
  — reproducing the discovery-is-startup-only finding with the corrected
  names; `kubectl exec deploy/myadapt -- adapt admin create-permissions
  /data __all__` (created `readme_readonly` among other groups, confirming
  the concrete group name used in the rewritten walkthrough);
  `create-user`/`add-to-group` for user `editor` using a quoted
  `$EDITOR_PASSWORD` shell variable (no unquoted placeholder); a real
  `curl -X POST .../auth/login -d username=editor -d
  password="$EDITOR_PASSWORD"` returned `200` with `set-cookie:
  adapt_session=...`, and a follow-up `curl -b cookies.txt
  http://localhost:8000/readme` returned `200` — the walkthrough now ends at
  an actually-verified logged-in, working instance; `helm upgrade
  --reuse-values --set env[0].name=ADAPT_UPLOAD_ENABLED
  --set-string env[0].value=true` enabled uploads. Released with
  `helm uninstall myadapt` and `kubectl delete pvc myadapt`.
- **Persistence modes / existing-PVC / NodePort / image-override sections:**
  `helm template shouldfail ... --set bootstrapAdmin.enabled=true` (no
  `persistence.enabled=true`) reproduced the documented `fail()` guard
  verbatim. `helm install nptest ... --set service.type=NodePort
  --set service.nodePort=30080 --wait` installed and `kubectl get svc`
  confirmed `80:30080/TCP`; uninstalled afterward. `helm template imgtest
  ... --set image.repository=my-registry.example.com/adapt-server
  --set image.tag=0.5.0 --set imagePullSecrets[0].name=my-registry-pull-secret`
  rendered the expected `image:` line, confirming the image-override
  example in `kubernetes.md`.
- **Troubleshooting commands:** `helm install jobtest ...
  --set bootstrapAdmin.existingSecret=doesnotexist` produced a Job stuck in
  `CreateContainerConfigError` (missing Secret) and the install timed out as
  documented; `kubectl delete job jobtest-adapt-bootstrap-admin` was then
  run and confirmed to remove the failed Job (the documented cleanup step),
  after which `helm uninstall jobtest` and `kubectl delete pvc` completed
  cleanup. The `fsGroup`/UID-1000 PVC-ownership entry and the RWO
  node-affinity entry were verified in Phases 2 and 4 respectively (see
  those Decision log entries) and are cross-referenced here rather than
  re-run, since neither chart behavior changed in Phase 6.
- Cluster deleted afterward: `kind delete cluster --name adapt-gate6`.

**`mkdocs build --strict`:** re-run after all fixes; exit code 0, no
warnings or errors.

**Findings routed forward:** the release-name/service-link-collision chart
bug (Finding 1) is a real, unfixed chart defect, not a documentation gap —
it needs its own chart-template fix, `helm-unittest` case, and version bump
in a future session; recorded in `known_limitations.md`,
`troubleshooting.md`, and `PROJECT_STATUS.md` so it is not lost.

**Residual risk:** the image digest-pinning gap (recorded in the first
Gate 6 attempt above) remains a real, unfixed chart limitation. The
`appVersion`/app-version drift (`0.4.2` chart `appVersion` vs. `v0.5.0` app
release) is newly recorded and also unfixed. `docs/manual/security.md`
still does not cover the upload attack surface. None of these are
documentation gaps this phase can close by itself.

#### Review Gate 6 round 2 — failed (2026-09-01)

The reviewer found round 1 fixed the day-1 walkthrough but left the page's
own **canonical install command**, and six other examples on the same page,
still using the bare release name `adapt` — the exact name the page itself
proves crash-loops. `RELEASING.md`'s release-verification runbook had the
same defect. Several fenced `bash` blocks still carried unquoted
angle-bracket placeholders. `PROJECT_STATUS.md` overstated the fix as
covering "every example" when it did not yet. All four were corrected the
same day:

- **Finding 1 (High, canonical command still broken) — fixed.** Every
  `helm install`/`helm upgrade --install` example that used the bare release
  name `adapt` was changed to `myadapt`, including the canonical command at
  the top of **Install**, the local-checkout variant, all three persistence
  modes, the image-override example, both bootstrap-superuser examples, the
  NodePort example, and the local development overlay. The one remaining
  `adapt` in a fenced context is inside the narrative sentence describing
  the bug itself ("running with release name `adapt` deploys, then...") —
  rewritten as prose, not a copy-pasteable command, so it can't be
  mistakenly executed. `charts/adapt/README.md`'s quick-install (already
  `myadapt` from round 1) had its `<chart-version>` placeholder replaced
  with the concrete `0.5.1`, closing the last angle-bracket gap there.
  `RELEASING.md` had two occurrences: the release-verification test (step 7)
  now installs as `adapt-release-check` (matching the already-used
  cluster/namespace name — it contains `adapt`, so `fullname` still
  collapses to the release name itself, but the resulting Service name
  `adapt-release-check` maps to env prefix `ADAPT_RELEASE_CHECK_*`, not
  `ADAPT_*`, so it does not collide), and the generic "Install a released
  chart" example now uses `myadapt` with the same warning inline.
- **Finding 2 (Medium, remaining foot-guns and incomplete verification) —
  fixed.** Removed the remaining unquoted angle-bracket placeholders from
  copy-pasteable `bash` fences: `kubernetes.md`'s manual-bootstrap and
  Secret-retrieval examples now use the concrete `myadapt`/
  `myadapt-bootstrap-admin` names (with the general `<release>` substitution
  rule moved into surrounding prose, not embedded in the command itself);
  the `kubectl cp` example under **Getting documents into the document
  root** uses a concrete illustrative pod name instead of `<namespace>/<pod>`
  and points at the day-1 walkthrough for the live-substituted form; the
  local development overlay now sets `LOCAL_IMAGE`/`LOCAL_TAG` shell
  variables instead of embedding `<your-local-image>`/`<tag>` directly.
  `troubleshooting.md`'s failed-bootstrap-Job cleanup now uses the concrete
  `myadapt-bootstrap-admin` example and splits the "if still present" pod
  delete into its own clearly-labeled command instead of an inline shell
  comment. Also newly executed and recorded, closing the specific gaps the
  reviewer named:
  - `helm show values oci://ghcr.io/mcindi/charts/adapt --version 0.5.1` —
    ran, printed the full default values document.
  - **Existing-PVC install**, on a fresh `kind` cluster
    (`adapt-gate6b`): created a matching `my-adapt-pvc` PersistentVolumeClaim
    by hand (`kubectl apply -f my-adapt-pvc.yaml`, `standard` StorageClass,
    `10Gi`, `ReadWriteOnce`), then `helm install myadapt
    oci://ghcr.io/mcindi/charts/adapt --version 0.5.1
    --set persistence.enabled=true --set persistence.existingClaim=my-adapt-pvc
    --wait`. The first attempt hit the `--wait` timeout while the image was
    still being pulled into the fresh node's containerd cache (a cold-cache
    artifact of the test environment, not a chart defect — the pod reached
    `1/1 Ready` moments later); a clean re-run with a longer timeout
    succeeded outright and `kubectl get pvc` confirmed `my-adapt-pvc` bound
    and reused rather than a new PVC created.
  - `docker ps --filter name=<container>` — ran against a running
    `ghcr.io/mcindi/adapt-server:0.5.0` container with a correctly-owned
    bind mount; confirmed the `STATUS` column reports
    `Up ... (healthy)`, matching the `container.md` claim about the built-in
    `HEALTHCHECK`.
  All test resources (PVC, release, cluster, containers, temp files) were
  removed afterward.
- **`PROJECT_STATUS.md`'s Docs-lane claim corrected** to name the specific
  files brought into consistency (`kubernetes.md`, `README.md`,
  `charts/adapt/README.md`, `RELEASING.md`) and the two release names used
  (`myadapt` for user-facing examples, `adapt-release-check` for the release
  runbook's own verification step), rather than the unqualified "every
  example" phrasing the reviewer correctly flagged as stronger than what
  had actually been changed at that point.

**`mkdocs build --strict`:** re-run after this round's fixes; exit code 0,
no warnings or errors.

**Findings routed forward:** unchanged from round 1 — the release-name/
service-link-collision chart bug is still a real, unfixed chart defect
that needs its own chart-template fix, `helm-unittest` case, and version
bump in a future session.

**Residual risk:** unchanged from round 1 (image digest-pinning gap,
`appVersion` drift, `docs/manual/security.md` upload-surface gap). The
cold-cache `--wait` timeout observed during existing-PVC verification is
noted as an environment artifact, not a documentation or chart defect, and
is not otherwise recorded as a limitation.
- **Publishing this round's fixes:** committed (`beaf2ac`) and pushed to
  `main`, then republished via `gh workflow run pages.yml --ref main` (run
  [33504408052](https://github.com/McIndi/adapt/actions/runs/33504408052),
  all jobs succeeded). Re-fetched
  `https://www.mcindi.com/adapt/manual/kubernetes/` afterward and confirmed
  the canonical **Install** command now reads
  `helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.1`,
  every other example on the page uses `myadapt`, and the round-2 wording
  ("Every example on this page ... uses `myadapt` ... none of them use the
  bare release name `adapt`") is live, not just local.

#### Review Gate 6 round 3 — values-dev header (2026-09-01)

The reviewer found one last executable documentation command outside the
canonical docs pages: `charts/adapt/values-dev.yaml` still used the broken
bare release name `adapt`, unquoted `<your-local-image>` / `<tag>` values,
and the wrong bootstrap Secret name. The header now defines
`LOCAL_IMAGE=your-local-image` and `LOCAL_TAG=your-tag`, runs
`helm upgrade --install myadapt charts/adapt`, passes quoted variable values,
uses `NODE_IP` rather than an angle-bracket shell-redirection placeholder,
and retrieves `myadapt-bootstrap-admin`. Focused VM verification rendered
the exact command values with:

```bash
helm template myadapt charts/adapt -f charts/adapt/values-dev.yaml \
  --set image.repository=your-local-image --set image.tag=your-tag \
  --set image.pullPolicy=IfNotPresent
```

The rendered Secret name was `myadapt-bootstrap-admin`, the Deployment name
and PVC claim name were `myadapt`, the image was
`your-local-image:your-tag`, and the Service was `NodePort` `30080`. The
strict MkDocs build also passed after the comment-only overlay change. This
closes the final remaining Gate 6 command mismatch; the separate
release-name/service-link collision remains documented as an unfixed chart
behavior for a future chart version.

#### Review Gate 6 — passed (2026-09-02)

The reviewer accepted the final gate after the round-3 correction. All five
gate criteria pass.

The reviewer reran the focused Helm lint and render checks. The reviewer also
reran `mkdocs build --strict` and `git diff --check`. GitHub Test run
`33543538226` and Helm CI run `33543538185` passed for commit `5d724cc`.
The repository was clean and synchronized with `origin/main` at acceptance.

## Deliberately deferred

Record these so a future reader knows they were considered, not missed:

- **SBOM and signing** for the wheel, the image, and the chart — M2 in
  `MILESTONES.md`. Phases 3 and 5 note the hook points.
- **Dependabot** for the `docker` ecosystem — M2.
- **Docroot seeding via initContainer** (option 4.2c) if option (b) is chosen
  — needs its own design and milestone entry.
- **Multi-replica support.** The `RWX` and SQLite-locking constraints at
  `docs/manual/installation.md:321-328` are real. Phase 6.6 documents them;
  solving them is out of scope.
- **Base image digest pinning**, if Phase 3.4 skips it.
- **Python lint job** and coverage reporting — later milestones.
