#!/bin/bash
# SPDX-FileCopyrightText: 2026 Wells Riley
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Print setup-guide.html to macintosh-mini-setup-guide.pdf with headless
# Chrome. The fonts come from jsDelivr, so it needs the internet.
set -euo pipefail
cd "$(dirname "$0")"
chrome=${CHROME:-"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"}
"$chrome" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=20000 \
  --print-to-pdf="$PWD/macintosh-mini-setup-guide.pdf" "file://$PWD/setup-guide.html" 2>/dev/null
