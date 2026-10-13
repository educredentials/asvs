#!/usr/bin/env bash
# Discover git remotes and generate evidence-ready link info.
# Usage:
#   git-remote.sh                    # Show all remotes
#   git-remote.sh <remote>           # Show details for one remote
#   git-remote.sh --urls             # Show URLs only
#   git-remote.sh --link owner repo branch path   # Generate a blob URL

set -euo pipefail

REPO_DIR="${1:-.}"
cd "$REPO_DIR" 2>/dev/null || { echo "Error: not a git repo"; exit 1; }

if [[ "${1:-}" == "--urls" ]]; then
    git remote -v | grep -oP '(?<=\t)[^ ]+' | sort -u
    exit 0
fi

if [[ "${1:-}" == "--link" && "${2:-}" && "${3:-}" && "${4:-}" && "${5:-}" ]]; then
    REMOTE_NAME="$2"
    OWNER="$3"
    REPO="$4"
    BRANCH="$5"
    PATH_ARG="$6"

    REMOTE_URL=$(git remote get-url "$REMOTE_NAME" 2>/dev/null)

    if echo "$REMOTE_URL" | grep -q "github.com"; then
        echo "https://github.com/${OWNER}/${REPO}/blob/${BRANCH}/${PATH_ARG}"
    elif echo "$REMOTE_URL" | grep -q "gitlab"; then
        # Extract host from URL (strip protocol)
        HOST=$(echo "$REMOTE_URL" | sed -E 's|^https?://([^/:]+).*|\1|')
        echo "https://${HOST}/${OWNER}/${REPO}/-/blob/${BRANCH}/${PATH_ARG}"
    else
        echo "Unknown host for remote '${REMOTE_NAME}': ${REMOTE_URL}"
        echo "Expected github.com or gitlab host"
        exit 1
    fi
    exit 0
fi

# Default: show all remotes with details
echo "Git Remotes:"
echo "============"
for remote in $(git remote); do
    URL=$(git remote get-url "$remote")
    echo ""
    echo "  ${remote}: ${URL}"

    if echo "$URL" | grep -q "github.com"; then
        OWNER=$(echo "$URL" | grep -oP '(?<=:|/)[^/]+(?=/[^/]+\.git)')
        REPO=$(echo "$URL" | grep -oP '(?<=/)[^/]+(?=\.git)')
        echo "    Host:     GitHub"
        echo "    Owner:    ${OWNER:-unknown}"
        echo "    Repo:     ${REPO:-unknown}"
    elif echo "$URL" | grep -q "gitlab"; then
        HOST=$(echo "$URL" | sed -E 's|^https?://([^/:]+).*|\1|')
        REST=$(echo "$URL" | grep -oP '(?<=://)[^/]+(.*)' | sed 's|^https\?://[^/]*||')
        OWNER=$(echo "$REST" | cut -d'/' -f1)
        REPO=$(echo "$REST" | cut -d'/' -f2 | sed 's/\.git$//')
        echo "    Host:     ${HOST}"
        echo "    Owner:    ${OWNER:-unknown}"
        echo "    Repo:     ${REPO:-unknown}"
    else
        echo "    Host:     unknown (${URL})"
    fi

    BRANCH=$(git remote show "$remote" 2>/dev/null | grep "HEAD branch" | awk '{print $NF}' || echo "unknown")
    echo "    Default:  ${BRANCH}"
done

# Show evidence link examples for a sample path
echo ""
echo "Evidence link examples (for src/main.js on main):"
for remote in $(git remote); do
    LINK=$(bash "$0" --link "$remote" owner repo main src/main.js 2>/dev/null || echo "(skip)")
    echo "  ${remote}: ${LINK}"
done