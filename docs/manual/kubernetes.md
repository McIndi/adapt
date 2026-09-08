# Kubernetes (Helm)

Adapt publishes a Helm chart to `oci://ghcr.io/mcindi/charts/adapt` on every
chart release. This page is the canonical reference for deploying it. The
chart source is also in the repository at `charts/adapt/`, with a shorter
pointer in [`charts/adapt/README.md`](https://github.com/McIndi/adapt/blob/main/charts/adapt/README.md)
and in the project [README](https://github.com/McIndi/adapt#readme).

## Install

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2
```

This is the canonical install command — no `git clone` is required. `helm
show chart` and `helm show values` work the same way, against the OCI
reference, without a checkout:

```bash
helm show chart oci://ghcr.io/mcindi/charts/adapt --version 0.5.2
helm show values oci://ghcr.io/mcindi/charts/adapt --version 0.5.2
```

If you are developing the chart itself, install from the local checkout
instead: `helm install myadapt ./charts/adapt`.

The release name `adapt` is valid. The server Deployment and the bootstrap
Job set `enableServiceLinks: false`, so Kubernetes does not inject
`ADAPT_PORT` from a Service named `adapt`. Examples on this page still use
`myadapt` because that name shows the chart `fullname` collapse rule: when
the release name contains `adapt`, resource names equal the release name
(`myadapt`, not `myadapt-adapt`).

## Persistence modes

By default, `/data` uses `emptyDir`. The pod loses its data when it restarts.
Enable persistence to keep document content and `.adapt/` state across
restarts and rescheduling.

**Ephemeral (default):**

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2
```

**Dynamic PVC — cluster provisions the volume automatically:**

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
  --set persistence.enabled=true \
  --set persistence.size=20Gi \
  --set persistence.storageClass=standard
```

The chart creates a `PersistentVolumeClaim` named `<release>-adapt`. If the
release name contains `adapt`, the claim name is `<release>`. If
`storageClass` is empty, the cluster uses its default StorageClass. For
`myadapt`, that means the PVC is named `myadapt`, matching the release name.

**Existing PVC — cluster admin creates the volume beforehand:**

```bash
kubectl apply -f my-adapt-pvc.yaml

helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
  --set persistence.enabled=true \
  --set persistence.existingClaim=my-adapt-pvc
```

The chart does not create a `PersistentVolumeClaim` object in this mode.

### Persistence values reference

| Value | Default | Description |
|---|---|---|
| `persistence.enabled` | `false` | Enable durable storage |
| `persistence.existingClaim` | `""` | Name of a pre-created PVC to mount |
| `persistence.storageClass` | `""` | StorageClass name. Uses the cluster default if empty |
| `persistence.accessModes` | `[ReadWriteOnce]` | PVC access modes |
| `persistence.size` | `10Gi` | Storage request size |
| `persistence.mountPath` | `""` (uses `adapt.rootPath`) | Mount path inside the container |
| `persistence.annotations` | `{}` | Extra annotations on the PVC |

## Image values

| Value | Default | Description |
|---|---|---|
| `image.repository` | `ghcr.io/mcindi/adapt-server` | Image repository |
| `image.tag` | `""` (uses `Chart.yaml` `appVersion`) | Image tag. Leave empty when `image.digest` is set. |
| `image.digest` | `""` | Image digest (`sha256:...`). When set, the chart renders `repository@digest` and does not append a tag. |
| `image.pullPolicy` | `IfNotPresent` | Image pull policy |
| `imagePullSecrets` | `[]` | List of `{name: <secret>}` objects for a private registry |

Point at a private mirror or an air-gapped registry:

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
  --set image.repository=my-registry.example.com/adapt-server \
  --set image.tag=0.5.2 \
  --set imagePullSecrets[0].name=my-registry-pull-secret
```

Pin the image by digest. Do not set `image.tag` in the same install:

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
  --set image.digest=sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
```

Do not put `@sha256:...` inside `image.repository`. The chart would then
render an invalid reference. Signing and provenance for the chart itself
are not yet implemented (milestone M3 in `MILESTONES.md`).

## Upload settings

Uploads are off by default. When you want file ingestion from a browser or
an API, enable uploads with environment configuration values in the chart.

Example `values.yaml` fragment:

```yaml
env:
  - name: ADAPT_UPLOAD_ENABLED
    value: "true"
  - name: ADAPT_UPLOAD_MAX_SIZE_BYTES
    value: "10485760"
  - name: ADAPT_UPLOAD_ALLOWED_EXTENSIONS
    value: ".csv,.md,.txt"
  - name: ADAPT_UPLOAD_STRICT_MIME_SNIFFING
    value: "true"
```

`env` entries render through `values.schema.json`, which requires each
`value` to be a string — pass `--set-string env[0].value=...` (not
`--set`) when setting a numeric or boolean-looking value from the command
line, or the install/upgrade fails schema validation.

When you enable uploads, authenticated users with `write` permission on the
document-root boundary see the upload card on `/`. These users can upload
directly from the landing page. The same users can also call
`POST /api/uploads` with API credentials.

## Admin prerequisites

- Before you use dynamic mode, provide a StorageClass with enough quota.
- For `ReadWriteOnce` volumes, keep `replicaCount=1` (the chart default).
  When the storage driver supports concurrent writers, use an `RWX`-capable
  StorageClass and increase `replicaCount`.
- Adapt reads and writes `.adapt/adapt.db` (SQLite). Two pods that share an
  `RWO` volume cause write conflicts. `RWX` block volumes can cause
  corruption. Network filesystems (NFS, CephFS, Azure Files) with correct
  locking are the supported multi-replica path.
- An `RWO` volume is bound to whichever node its first mounting pod was
  scheduled on. A replacement pod stuck in `ContainerCreating` after a node
  drain or reschedule is usually this constraint, not a chart defect — see
  [Troubleshooting](troubleshooting.md).

## Bootstrapping a superuser

By default, a fresh install has no users. Create one manually, or let the
chart do it automatically for you.

**Manually:**

```bash
kubectl exec -it deploy/myadapt -- \
  adapt addsuperuser /data --username admin
```

This assumes the release name is `myadapt`, so `fullname` collapses to
`myadapt` (it contains `adapt`). For a release name that does not contain
`adapt`, the Deployment is `deploy/<release>-adapt` instead. The `-it` flag
is required because `addsuperuser` prompts for the password. For scripts,
use `--password`, `--password-confirm`, and `--allow-weak-password` as
applicable.

**Automatically**, set `bootstrapAdmin.enabled=true` to run that same
command through a `post-install,post-upgrade` Helm hook Job that gets
credentials from a Kubernetes Secret:

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
  --set persistence.enabled=true \
  --set bootstrapAdmin.enabled=true \
  --set bootstrapAdmin.username=admin
```

**Requires `persistence.enabled=true`.** The bootstrap Job runs in its own
pod. It can share the account database with the main deployment only through
a PVC. If you use `emptyDir` (the default), the two pods get independent,
disconnected volumes, and the created user is invisible to the running
server. The chart does not silently skip this configuration: if you set
`bootstrapAdmin.enabled=true` without persistence, `helm install` and
`helm template` fail.

If you leave `bootstrapAdmin.existingSecret` unset, the chart generates a
Secret named `<release>-adapt-bootstrap-admin` with a random password on the
first install. If the release name contains `adapt`, the name becomes
`<release>-bootstrap-admin` — for `myadapt`, that Secret is
`myadapt-bootstrap-admin`. Run `helm get notes <release>` to get the
correct command for your own release name. On every later `helm upgrade`,
the chart reuses the same Secret value — it does not generate a new
password, so the Secret always matches the password in the created account.
Retrieve it with:

```bash
kubectl get secret myadapt-bootstrap-admin -o jsonpath='{.data.password}' | base64 -d && echo
```

To supply your own credentials, for example from a secrets manager, create a
Secret with `username` and `password` keys. Point
`bootstrapAdmin.existingSecret` at it. Use `existingSecretUsernameKey` and
`existingSecretPasswordKey` to use different key names.

**Caveat:** if you run `helm uninstall` and reinstall against the same
retained PVC, the admin account from the first install still exists with its
original password. `addsuperuser` does nothing for a username that already
exists, so a newly generated Secret value does not apply. If you need that
guarantee across reinstalls, use `bootstrapAdmin.existingSecret` with a known
password. You can also reset the password with
`adapt admin change-password`.

**A failed bootstrap Job blocks reinstall.** Helm retains a failed hook Job
for diagnosis; see [Troubleshooting](troubleshooting.md) for how to clear it.

## Exposing the service

`service.type` defaults to `ClusterIP`. Reach it with `kubectl port-forward`
or your own Ingress. For a directly-reachable address without an Ingress
controller, for example on bare-metal or single-node clusters like k3s, set
it to `NodePort`. You can also pin the port so it stays stable across
reinstalls:

```bash
helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
  --set service.type=NodePort \
  --set service.nodePort=30080
```

Kubernetes applies `service.nodePort` only when `service.type` is `NodePort`
or `LoadBalancer`. Leave it blank to let Kubernetes assign one from its
30000-32767 range.

`helm install`/`helm get notes` prints the exact reach-the-service command
for whichever `service.type` (or Ingress) you configured — read it before
you improvise a `kubectl` command by hand.

## Getting documents into the document root

The templates have no initContainer or ConfigMap-seeding mechanism by
default. Two supported paths:

- **`kubectl cp` (quick path, no chart change):**

  ```bash
  kubectl cp ./documents/. default/myadapt-6f9d8c9b8-abcde:/data
  ```

  Substitute your own namespace and pod name — `helm get notes <release>`
  prints this command with both already filled in for your actual release,
  and the [day-1 walkthrough](#day-1-walkthrough) below shows the exact
  `kubectl get pod ...` substitution used to build it live.

- **`extraVolumes` / `extraVolumeMounts` (repeatable or shared sources):**
  mount a ConfigMap, NFS share, or pre-populated volume below the writable
  document root (for example `/data/documents`), or mount a writable
  NFS/share volume at `/data` with `externalDocumentRoot=true`. Do not mount
  a ConfigMap directly at `/data` — Adapt needs to write `.adapt/` there.

**Adapt discovers resources once, at process startup — not continuously.**
Copying a file into a *running* pod's document root does not make it
reachable until the pod restarts (`kubectl rollout restart
deployment/<release>-adapt`) or the pod is otherwise replaced. This applies
to both `kubectl cp` and any volume mounted after the pod is already running.
If a copied file returns `404` immediately after `kubectl cp`, this is why —
restart the deployment and it resolves. This does not apply to the search
index, which `adapt reindex` (or `search_on_startup`) refreshes without a
restart; it is the resource *route* table that is startup-only.

## Local development overlay

`charts/adapt/values-dev.yaml` bundles persistence, `bootstrapAdmin`, and a
pinned `NodePort` (`30080`) together. Use it to start a durable,
directly-browsable instance for local VM or k3s development, instead of
setting the individual flags above:

```bash
LOCAL_IMAGE=your-local-image
LOCAL_TAG=your-tag

helm upgrade --install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
  -f charts/adapt/values-dev.yaml \
  --set image.repository="$LOCAL_IMAGE" --set image.tag="$LOCAL_TAG"
```

The overlay uses the `local-path` StorageClass from k3s. For kind or
minikube, add `--set persistence.storageClass=standard`. For Docker Desktop,
use `--set persistence.storageClass=hostpath`. For other clusters, set the
value to an available StorageClass.

## Day-1 walkthrough

One ordered path from an empty cluster to a populated, logged-in instance.
Every command below was run in order against a real `kind` cluster while
writing this page, using the release name `myadapt`. Substitute your own
values for `editor` (username), the two example passwords, and the
document(s) you copy in. Everything else can be copy-pasted as-is. The
release name `adapt` is also valid.

1. **Install with persistence and automated bootstrap:**

   ```bash
   helm install myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
     --set persistence.enabled=true \
     --set bootstrapAdmin.enabled=true \
     --set bootstrapAdmin.username=admin \
     --wait
   ```

2. **Retrieve the generated password** (Secret name per the rule above —
   `myadapt` contains `adapt`, so the fullname collapses to `myadapt` and
   the Secret is `myadapt-bootstrap-admin`, not `myadapt-adapt-bootstrap-admin`):

   ```bash
   kubectl get secret myadapt-bootstrap-admin -o jsonpath='{.data.password}' | base64 -d && echo
   ```

3. **Reach the service** (`ClusterIP` shown; see `helm get notes` for
   `NodePort`/`LoadBalancer`/Ingress). `kubectl port-forward` blocks the
   terminal it runs in, so run it in one terminal and the remaining
   commands in a second terminal (or background it with a trailing `&`):

   ```bash
   # terminal 1 — leave this running
   kubectl port-forward svc/myadapt 8000:80
   ```

   ```bash
   # terminal 2
   curl http://localhost:8000/health
   ```

4. **Get documents into the document root**, then restart so Adapt
   discovers them (see
   [Getting documents into the document root](#getting-documents-into-the-document-root)
   for why the restart is required):

   ```bash
   kubectl cp ./documents/. default/$(kubectl get pod -l app.kubernetes.io/instance=myadapt,app.kubernetes.io/component=server -o jsonpath='{.items[0].metadata.name}'):/data
   kubectl rollout restart deployment/myadapt
   kubectl rollout status deployment/myadapt
   ```

   The rollout replaces the pod, so restart the `kubectl port-forward` from
   step 3 (terminal 1) once the rollout finishes — it was pointed at the
   pod that just terminated.

5. **Generate permissions** for everything Adapt discovered:

   ```bash
   kubectl exec deploy/myadapt -- adapt admin create-permissions /data __all__
   ```

   For a single `readme.md` seeded above, this creates (among others) a
   `readme_readonly` group — `adapt admin list-groups /data` lists every
   group `create-permissions` made, using each resource's own name.

6. **Create a regular user and assign a group.** Set the password in a
   shell variable first — a literal `<placeholder>` on the command line is
   not a value to substitute, it is Bash input/output redirection syntax,
   and passing it unquoted breaks the command:

   ```bash
   EDITOR_PASSWORD='choose-your-own-password'

   kubectl exec deploy/myadapt -- \
     adapt admin create-user /data --username editor \
     --password "$EDITOR_PASSWORD" --password-confirm "$EDITOR_PASSWORD"

   kubectl exec deploy/myadapt -- \
     adapt admin add-to-group /data --username editor --group readme_readonly
   ```

7. **Sign in as the new user** and confirm it can read what it was granted.
   From a browser, open `http://localhost:8000/auth/login` (through the
   port-forward from step 3) and log in as `editor`. From a terminal, the
   same login the browser performs is:

   ```bash
   curl -i -c cookies.txt -X POST http://localhost:8000/auth/login \
     -d username=editor -d password="$EDITOR_PASSWORD"
   ```

   A `200` response with a `set-cookie: adapt_session=...` header means the
   login succeeded — this is the "logged-in instance" this walkthrough ends
   at. Reading the resource with that session:

   ```bash
   curl -b cookies.txt http://localhost:8000/readme
   ```

8. **Optionally enable uploads**, remembering the root `write` permission
   requirement from the upload settings section above:

   ```bash
   helm upgrade myadapt oci://ghcr.io/mcindi/charts/adapt --version 0.5.2 \
     --reuse-values \
     --set env[0].name=ADAPT_UPLOAD_ENABLED \
     --set-string env[0].value=true
   ```

Manual navigation: [Previous: Container](container.md) | [Index](index.md)
