#!/bin/sh
# Copyright (c) 2024 Thiago Alves
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR="$SCRIPT_DIR/hooks"
GIT_HOOKS_DIR="$(git rev-parse --git-dir)/hooks"

for hook in "$HOOKS_DIR"/*; do
	if [ -f "$hook" ]; then
		hook_name="$(basename "$hook")"
		ln -sf "$hook" "$GIT_HOOKS_DIR/$hook_name"
		echo "Installed $hook_name hook"
	fi
done

echo "Git hooks installed successfully"