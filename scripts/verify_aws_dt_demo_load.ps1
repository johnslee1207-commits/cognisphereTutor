# Verify Tutor can load the AWS Digital Twin demo pack (fail-closed).
param(
  [string]$PluginsRoot = ""
)
$ErrorActionPreference = "Stop"

if ($PluginsRoot) {
  $env:COGNISPHERE_LEARNING_PLUGINS_ROOT = (Resolve-Path $PluginsRoot).Path
}

if (-not $env:COGNISPHERE_LEARNING_PLUGINS_ROOT) {
  $sibling = Join-Path (Split-Path -Parent (Get-Location)) "CognisphereLearningPlugins"
  $bundle = Join-Path $sibling "dist\aws_dt_tutor_demo"
  if (Test-Path $bundle) {
    $env:COGNISPHERE_LEARNING_PLUGINS_ROOT = (Resolve-Path $bundle).Path
  } elseif (Test-Path $sibling) {
    $env:COGNISPHERE_LEARNING_PLUGINS_ROOT = (Resolve-Path $sibling).Path
  }
}

Write-Host "COGNISPHERE_LEARNING_PLUGINS_ROOT=$($env:COGNISPHERE_LEARNING_PLUGINS_ROOT)"

python -c @"
import json
import sys
from cognispheretutor.integrations.cognisphere.aws_dt_demo_pack import verify_aws_dt_demo_pack

payload = verify_aws_dt_demo_pack()
print(json.dumps(payload, ensure_ascii=False, indent=2))
sys.exit(0 if payload.get('ok') else 1)
"@

if ($LASTEXITCODE -ne 0) {
  Write-Error "AWS DT demo pack verify failed (fail-closed). Build/install LP dist/aws_dt_tutor_demo first."
  exit $LASTEXITCODE
}

Write-Host "OK — next: cognispheretutor cognisphere aws-twin-mastery"
