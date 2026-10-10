#!/usr/bin/env bash
# Build the single Lambda zip (root = src/ contents) and sanity-check it.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf build && mkdir -p build
.venv/bin/python - <<'EOF'
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
.venv/bin/python -c "import zipfile; print('\n'.join(sorted({n.split('/')[0] for n in zipfile.ZipFile('build/dusttrack-backend.zip').namelist() if n.strip('/')})))"
TMPDIR_CHECK=$(mktemp -d)
.venv/bin/python -c "import zipfile; zipfile.ZipFile('build/dusttrack-backend.zip').extractall('$TMPDIR_CHECK')"
PYTHONPATH="$TMPDIR_CHECK" .venv/bin/python -c "
import api.handler
import workflow.validate_input, workflow.analyse_image, workflow.fetch_weather
import workflow.update_cadence, workflow.score_segment, workflow.publish_work_list
print('import check: api.handler + 6 workflow handlers OK')
"
rm -rf "$TMPDIR_CHECK"
