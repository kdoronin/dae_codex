#!/usr/bin/env bash
set -euo pipefail

EXPECTED_LOGIN="kdoronin"
REPO_OWNER="kdoronin"
REPO_NAME="dae_codex"
REMOTE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v gh >/dev/null 2>&1; then
  echo "Codex init: gh CLI is required to work with ${REPO_OWNER}/${REPO_NAME}" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "Codex init: git is required" >&2
  exit 1
fi

active_login="$(gh api user --jq '.login' 2>/dev/null || true)"
if [[ "$active_login" != "$EXPECTED_LOGIN" ]]; then
  echo "Codex init: expected GitHub account '${EXPECTED_LOGIN}', got '${active_login:-not authenticated}'" >&2
  echo "Run: gh auth login -h github.com" >&2
  exit 1
fi

github_user_id="$(gh api user --jq '.id' 2>/dev/null || true)"
if [[ -z "$github_user_id" ]]; then
  echo "Codex init: could not read GitHub user id for ${EXPECTED_LOGIN}" >&2
  exit 1
fi

if [[ ! -d .git ]]; then
  git init -b main >/dev/null
else
  git branch -M main >/dev/null 2>&1 || true
fi

if git remote get-url origin >/dev/null 2>&1; then
  current_origin="$(git remote get-url origin)"
  if [[ "$current_origin" != "$REMOTE_URL" ]]; then
    git remote set-url origin "$REMOTE_URL"
  fi
else
  git remote add origin "$REMOTE_URL"
fi

git config user.name "$EXPECTED_LOGIN"
git config user.email "${github_user_id}+${EXPECTED_LOGIN}@users.noreply.github.com"

if ! gh repo view "${REPO_OWNER}/${REPO_NAME}" >/dev/null 2>&1; then
  echo "Codex init: cannot access GitHub repository ${REPO_OWNER}/${REPO_NAME}" >&2
  exit 1
fi

echo "Codex init: ready for ${REPO_OWNER}/${REPO_NAME} as ${EXPECTED_LOGIN}"
