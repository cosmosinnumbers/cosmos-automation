#!/usr/bin/env bash
# Push what a workflow step committed, robustly (self-heal, owner 04/11/2026: "il sistema si deve autorisolvere").
# On 4/11 a log written by tools/post_qc.py and left out of the commit made "git pull --rebase" refuse ("You have
# unstaged changes") in every run of threads-build, and Threads posted nothing all day. Here:
#   - every change under logs/ is committed too (the logs are the publishers' memory: what is out is never redone);
#   - any other modified file is stashed around the pull (--autostash), so it can never block it again;
#   - logs/*.jsonl merge as union (.gitattributes), so two runs appending at the same time do not conflict;
#   - a failed rebase is aborted and the pull + push retried 5 times with backoff.
# Usage: bash tools/git_sync.sh ["commit message for the logs"]   Exit 1 only if the push failed 5 times.
set -u
git config user.name >/dev/null || git config user.name "cosmos-bot"
git config user.email >/dev/null || git config user.email "cosmos-bot@users.noreply.github.com"
git add -A logs 2>/dev/null || true
git diff --cached --quiet || git commit -q -m "${1:-log: ${GITHUB_WORKFLOW:-workflow}}"
branch="${GITHUB_REF_NAME:-$(git rev-parse --abbrev-ref HEAD)}"
for i in 1 2 3 4 5; do
  if git pull -q --rebase --autostash origin "$branch" && git push -q origin "HEAD:$branch"; then
    exit 0
  fi
  git rebase --abort 2>/dev/null || true
  sleep $((i * 5))
done
echo "git_sync: push to $branch failed 5 times" >&2
exit 1
