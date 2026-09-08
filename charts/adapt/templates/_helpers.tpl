{{- define "adapt.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "adapt.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "adapt.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "adapt.labels" -}}
helm.sh/chart: {{ include "adapt.chart" . }}
app.kubernetes.io/name: {{ include "adapt.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "adapt.selectorLabels" -}}
app.kubernetes.io/name: {{ include "adapt.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "adapt.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "adapt.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "adapt.image" -}}
{{- $repo := required "image.repository is required" .Values.image.repository -}}
{{- $digest := default "" .Values.image.digest | toString | trim -}}
{{- $tag := default "" .Values.image.tag | toString | trim -}}
{{- if and $digest $tag -}}
{{- fail "Set image.digest or image.tag, not both. When image.digest is set, leave image.tag empty so the chart renders repository@digest." -}}
{{- end -}}
{{- if $digest -}}
{{- printf "%s@%s" $repo $digest -}}
{{- else -}}
{{- printf "%s:%s" $repo ($tag | default .Chart.AppVersion) -}}
{{- end -}}
{{- end }}
