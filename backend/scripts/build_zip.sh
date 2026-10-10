#!/usr/bin/env bash
# Build the single Lambda zip (root = src/ contents) and sanity-check it.
# Uses PYTHON (default "python"); see scripts/check.sh header.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"
rm -rf build && mkdir -p build
"$PY" - <<'EOF'
import os
import zipfile

with zipfile.ZipFile("build/dusttrack-backend.zip", "w", zipfile.ZIP_DEFLATED) as archive:
    for root, dirs, files in os.walk("src"):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            if name.endswith(".pyc"):
                continue
            path = os.path.join(root, name)
            archive.write(path, os.path.relpath(path, "src"))
EOF
echo "zip: $(du -h build/dusttrack-backend.zip | cut -f1) build/dusttrack-backend.zip"
echo "top-level entries:"
"$PY" -c "import zipfile; print('\n'.join(sorted({n.split('/')[0] for n in zipfile.ZipFile('build/dusttrack-backend.zip').namelist() if n.strip('/')})))"
TMPDIR_CHECK=$(mktemp -d)
"$PY" -c "import zipfile; zipfile.ZipFile('build/dusttrack-backend.zip').extractall('$TMPDIR_CHECK')"
PYTHONPATH="$TMPDIR_CHECK" "$PY" -c "
import api.handler
import workflow.validate_input, workflow.analyse_image, workflow.fetch_weather
import workflow.update_cadence, workflow.score_segment, workflow.publish_work_list
print('import check: api.handler + 6 workflow handlers OK')
"
rm -rf "$TMPDIR_CHECK"
