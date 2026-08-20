# Container, OCI, and Helm Chart Cleanup Plan

Status: Phase 3 implemented — Review Gate 3 blocked on arm64 publication
Created: 2026-08-12
Baseline: `main` @ `60ea9b9` (app `0.4.1`, chart `0.3.2`)

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

- [ ] `NOTES.txt` answers reach / log in / seed / state, for all four service
      exposure modes
- [ ] Seeding mechanism chosen, implemented, and the decision recorded
- [ ] `values.schema.json` added, with tests
- [ ] `Chart.yaml` metadata complete; `validate-maintainers` workaround removed
- [ ] `Chart.yaml` version `0.5.0`

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

- [ ] Distribution model decided and recorded
- [ ] Publishing implemented and gated on tests plus chart CI
- [ ] Clean-machine `helm install` verified against the registry
- [ ] Release procedure documented
- [ ] The canonical install command for Phase 6 is stated unambiguously

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

- [ ] Container documentation exists, and every command in it was run
- [ ] Deployment content is in the nav and reachable
- [ ] One canonical Helm document; the other two reduced to pointers
- [ ] Day-1 walkthrough written and executed end to end
- [ ] Deployment troubleshooting added
- [ ] `mkdocs build --strict` passes
- [ ] `PROJECT_STATUS.md` and `MILESTONES.md` reconciled

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

Blocker: the published `ghcr.io/mcindi/adapt-server:latest` manifest lists
only `linux/amd64`; `linux/arm64` has not been published. Multi-arch
publication must be verified end-to-end (a real release or dispatch build,
inspected with `docker buildx imagetools inspect`) before Gate 3 can pass.

### Phase 4

_Not started._

### Phase 5

_Not started._

### Phase 6

_Not started._

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
