#!/bin/bash
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/phone_tweaks.py" audit "$@"
