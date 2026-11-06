#!/usr/bin/env bash
# web gate: tsc / eslint / vitest(json) in the pastguard-final worktree. Usage: web_gate.sh <evdir>
W=/c/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106
E=$1; mkdir -p "$E"
cd "$W/wt/final_project_cs/frontend/apps/web" || exit 2
node.exe --version > "$E/node.txt"
node.exe node_modules/typescript/bin/tsc --noEmit > "$E/tsc.log" 2>&1; echo "tsc=$?" > "$E/web-exit.txt"
node.exe node_modules/eslint/bin/eslint.js . > "$E/eslint.log" 2>&1; echo "eslint=$?" >> "$E/web-exit.txt"
node.exe node_modules/vitest/vitest.mjs run --reporter=json --outputFile="C:/Users/kcxsz/AppData/Local/hermes/profiles/guguroute/cache/scratch/pastguard-final-20261106/${E#$W/}/vt.json" > "$E/vt.log" 2>&1; echo "vt=$?" >> "$E/web-exit.txt"
