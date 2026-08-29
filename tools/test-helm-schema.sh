#!/usr/bin/env bash
set -eu

chart="${1:-charts/adapt}"

helm template schema-valid "$chart" -f "$chart/values-dev.yaml" >/dev/null

assert_rejected() {
  label="$1"
  shift
  if helm template "schema-$label" "$chart" "$@" >/dev/null 2>&1; then
    echo "schema check failed: $label was accepted" >&2
    exit 1
  fi
}

assert_rejected unknown-key --set persistance.enabled=true
assert_rejected service-type --set service.type=Invalid
assert_rejected node-port --set service.nodePort=29999
assert_rejected access-mode --set persistence.accessModes[0]=Invalid
assert_rejected bootstrap-admin-typo --set bootstrapAdmin.enabeld=true
assert_rejected probe-typo --set probes.livness.path=/bad
assert_rejected adapt-typo --set adapt.rootPth=/bad
assert_rejected ingress-typo --set ingress.enabeld=true
assert_rejected resources-typo --set resources.limtis.cpu=1

echo "Helm values schema accepted values-dev.yaml and rejected nine invalid values."