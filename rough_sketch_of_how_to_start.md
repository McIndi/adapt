Here's the setup, since your VM is a single-node k3s cluster (Vagrant/VirtualBox, host-only IP `192.168.56.10`), built by [Vagrantfile](../Vagrantfile) at the `repos` root. `/vagrant` inside the VM maps to that root, so the chart lives at `/vagrant/adapt/charts/adapt`.

**1. Bring the VM up and connect**

```bash
cd /c/Users/cliff/mcindi/repos
vagrant up
vagrant ssh
```

**2. Inside the VM — sanity-check the cluster and chart**

```bash
kubectl get nodes
kubectl get storageclass
helm lint /vagrant/adapt/charts/adapt
helm plugin install https://github.com/helm-unittest/helm-unittest --version v0.6.3 --verify=false
helm unittest /vagrant/adapt/charts/adapt
```

`kubectl get storageclass` matters — note whichever one is marked `(default)` (k3s ships `local-path`), since that's what you'll pass as `persistence.storageClass` below.

**3. Build the current working tree into an image and load it into k3s**

Your host has no `docker`, so build inside the VM with podman and import straight into containerd — no registry needed:

```bash
sudo dnf install -y podman
podman build -t adapt-local:test /vagrant/adapt
podman save adapt-local:test | sudo k3s ctr images import -
```

**4. Install: ephemeral mode (default) — confirm data does NOT survive a restart**

```bash
helm install adapt-eph /vagrant/adapt/charts/adapt \
  --set image.repository=localhost/adapt-local --set image.tag=test --set image.pullPolicy=IfNotPresent

kubectl rollout status deploy/adapt-eph
kubectl exec deploy/adapt-eph -- sh -c 'echo hello > /data/probe.txt'
kubectl delete pod -l app.kubernetes.io/instance=adapt-eph
kubectl rollout status deploy/adapt-eph
kubectl exec deploy/adapt-eph -- cat /data/probe.txt   # expect: No such file — proves emptyDir is ephemeral
helm uninstall adapt-eph
```

**5. Install: dynamic PVC mode — confirm data DOES survive a restart**

```bash
helm install adapt-pvc /vagrant/adapt/charts/adapt \
  --set image.repository=adapt-local --set image.tag=test --set image.pullPolicy=IfNotPresent \
  --set persistence.enabled=true --set persistence.size=1Gi --set persistence.storageClass=local-path

kubectl get pvc
kubectl rollout status deploy/adapt-pvc
kubectl exec deploy/adapt-pvc -- sh -c 'echo hello > /data/probe.txt'
kubectl delete pod -l app.kubernetes.io/instance=adapt-pvc
kubectl rollout status deploy/adapt-pvc
kubectl exec deploy/adapt-pvc -- cat /data/probe.txt   # expect: hello — proves the PVC persisted
```

**6. Bootstrap a superuser and smoke-test the app, including the new upload endpoint**

```bash
kubectl exec deploy/adapt-pvc -- adapt addsuperuser /data \
  --username admin --password 'Test-Passw0rd!' --password-confirm 'Test-Passw0rd!'

kubectl port-forward deploy/adapt-pvc 8000:8000
```

In a second VM shell (`vagrant ssh` again):

```bash
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST http://127.0.0.1:8000/auth/login \
  -d "username=admin&password=Test-Passw0rd!"

CSRF=$(grep adapt_csrf /tmp/cookies.txt | awk '{print $7}')
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST http://127.0.0.1:8000/admin/permissions \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $CSRF" \
  -d '{"resource":"__root__","action":"write","description":"root upload write"}'

echo "hello from vm test" > /tmp/probe.txt
curl -s -c /tmp/cookies.txt -b /tmp/cookies.txt -X POST http://127.0.0.1:8000/api/uploads \
  -H "X-CSRF-Token: $CSRF" \
  -F "filename=probe.txt" -F "file=@/tmp/probe.txt"
```

Note: `/api/uploads` is currently gated by `upload.enabled` (defaults to `false`) — pass `--set persistence.enabled=true --set upload.enabled=true` on the `helm install` in step 5 if you want to exercise this via `curl` rather than getting a `403`.

**7. Install: existing-claim mode**

```bash
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: adapt-manual-pvc
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: local-path
  resources:
    requests:
      storage: 1Gi
EOF

helm install adapt-existing /vagrant/adapt/charts/adapt \
  --set image.repository=adapt-local --set image.tag=test --set image.pullPolicy=IfNotPresent \
  --set persistence.enabled=true --set persistence.existingClaim=adapt-manual-pvc

kubectl get pvc adapt-manual-pvc   # should stay Bound to the pod, not get a second PVC created
```

**8. Cleanup**

```bash
helm uninstall adapt-pvc adapt-existing 2>/dev/null
kubectl delete pvc --all
```

```bash
exit          # leave the VM
vagrant halt  # or `vagrant destroy` to fully tear it down
```
Try logging in from a private or incognito browser window, or a different browser altogether.

Confirm he's signing in at Anthropic Partner Academy (via the https://partner-sso.anthropic.com sign-in flow) rather than the standard Anthropic Academy login page, and that he's using his company email address rather than a personal one.