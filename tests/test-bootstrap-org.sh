#!/usr/bin/env bash
# Regression checks: recreate GitHub's 404 response for a new organisation file.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/storage" "$T/home"
export MOCK_SOURCE_ROOT="$ROOT"
export MOCK_STORE="$T/storage"
export HOME="$T/home"
export PATH="$T/bin:$PATH"

cat > "$T/bin/gh" <<'GH'
#!/usr/bin/env bash
set -Eeuo pipefail
case "${1-}" in
  auth) exit 0 ;;
  repo) exit 0 ;;
  api)
    shift
    method="GET"
    if [[ "${1-}" == "--method" ]]; then method="$2"; shift 2; fi
    path="$1"; shift
    if [[ "$path" == "user" ]]; then echo "damunozx123-debug"; exit 0; fi
    if [[ "$path" == "user/memberships/orgs/munoz-tech-labs" ]]; then echo "admin"; exit 0; fi
    prefix="repos/munoz-tech-labs/.github/contents/"
    if [[ "$path" != "$prefix"* ]]; then echo "Unexpected API path: $path" >&2; exit 2; fi
    rel="${path#"$prefix"}"
    key="${rel//\//_}"
    dest="$MOCK_STORE/$key"
    if [[ "${MOCK_FORBID_PATH-}" == "$rel" ]]; then echo "gh: Forbidden (HTTP 403)" >&2; exit 1; fi
    if [[ "$method" == "PUT" ]]; then
      body=""
      while [[ "$#" -gt 0 ]]; do
        if [[ "$1" == "--field" ]]; then
          case "$2" in
            content=*) body="${2#content=}" ;;
          esac
          shift 2
        else
          shift
        fi
      done
      [[ -n "$body" ]] || { echo "Missing PUT body" >&2; exit 5; }
      printf '%s' "$body" | base64 --decode > "$dest"
      printf '{"content":{"sha":"%040d"}}\n' 0
      exit 0
    fi
    if [[ ! -f "$dest" ]]; then echo "gh: Not Found (HTTP 404)" >&2; exit 1; fi
    query=""
    while [[ "$#" -gt 0 ]]; do
      if [[ "$1" == "--jq" ]]; then query="$2"; shift 2; else shift; fi
    done
    case "$query" in
      .sha) printf '1111111111111111111111111111111111111111\n' ;;
      .content) base64 "$dest" ;;
      *) echo "Unexpected --jq query: $query" >&2; exit 6 ;;
    esac
    ;;
  *) echo "Unexpected gh command: $*" >&2; exit 7 ;;
esac
GH
cat > "$T/bin/curl" <<'CURL'
#!/usr/bin/env bash
set -Eeuo pipefail
url="" output=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --output|-o) output="$2"; shift 2 ;;
    --retry) shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
[[ "$url" == *"/master/"* ]] || { echo "Unexpected template URL: $url" >&2; exit 8; }
cp "$MOCK_SOURCE_ROOT/${url#*"/master/"}" "$output"
CURL
chmod +x "$T/bin/gh" "$T/bin/curl"

bash -n "$ROOT/scripts/bootstrap-profile-org.sh"
bash "$ROOT/scripts/bootstrap-profile-org.sh" org > "$T/first.log" 2>&1

for rel in \
  profile/README.md \
  CONTRIBUTING.md \
  SECURITY.md \
  .github/ISSUE_TEMPLATE/bug_report.yml \
  PULL_REQUEST_TEMPLATE.md \
  OPERATING_PLAN.md \
  RELEASE_CHECKLIST.md; do
  source_rel="org-kit/$rel"
  if [[ "$rel" == ".github/ISSUE_TEMPLATE/bug_report.yml" ]]; then
    source_rel="org-kit/ISSUE_TEMPLATE/bug_report.yml"
  fi
  cmp "$ROOT/$source_rel" "$MOCK_STORE/${rel//\//_}"
done
echo "PASS: seven missing files created from simulated HTTP 404 responses"

bash "$ROOT/scripts/bootstrap-profile-org.sh" org > "$T/second.log" 2>&1
grep -q "Already current" "$T/second.log"
echo "PASS: repeated run checks existing files"

printf '%s' "outdated" > "$MOCK_STORE/CONTRIBUTING.md"
bash "$ROOT/scripts/bootstrap-profile-org.sh" org > "$T/third.log" 2>&1
cmp "$ROOT/org-kit/CONTRIBUTING.md" "$MOCK_STORE/CONTRIBUTING.md"
find "$HOME/.local/share/munoz-tech-labs/backups" -type f -name '*CONTRIBUTING.md' -print -quit | grep -q .
echo "PASS: changed file backed up and refreshed"

export MOCK_FORBID_PATH="SECURITY.md"
if bash "$ROOT/scripts/bootstrap-profile-org.sh" org > "$T/forbidden.log" 2>&1; then
  cat "$T/forbidden.log" >&2
  echo "FAIL: HTTP 403 did not stop the script" >&2
  exit 1
fi
grep -q "Cannot inspect" "$T/forbidden.log"
if grep -q "Organization homepage ready" "$T/forbidden.log"; then
  echo "FAIL: falsely reported organisation ready after HTTP 403" >&2
  exit 1
fi
echo "PASS: 403 aborts without false success"
