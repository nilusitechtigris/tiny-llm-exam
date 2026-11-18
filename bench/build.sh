#!/bin/sh
# Grade every run in results/, rebuild docs/index.html and render the two images into assets/.
# Image rendering uses WebKit through Swift, so it needs macOS.
set -e
cd "$(dirname "$0")"
python3 grade.py > /dev/null
python3 build_page.py
swift render_png.swift build/card-scorecard.html ../assets/scorecard.png 1080 1350
swift render_png.swift build/card-everyday.html ../assets/everyday.png 1080 1350
