#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT}/infrastructure/terraform"
cd "${TF_DIR}"
terraform fmt -check -recursive
terraform init -backend=false -input=false >/dev/null
terraform validate
echo "terraform fmt+validate OK"
