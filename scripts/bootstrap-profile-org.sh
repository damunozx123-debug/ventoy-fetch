#!/usr/bin/env bash
# Munoz Tech Labs bootstrap: runs only on the owner's device with their GitHub CLI login.
set -Eeuo pipefail

OWNER="damunozx123-debug"
SOURCE_REPO="$OWNER/ventoy-fetch"
ORG_SLUG="${ORG_SLUG:-munoz-tech-labs}"
SCOPE="${1:-all}"
SOURCE_URL="https://raw.githubusercontent.com/$SOURCE_REPO/master"
BACKUP_DIR="$HOME/.local/share/munoz-tech-labs/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

log() { echo "[setup] $*"; }
warn() { echo "[manual step] $*" >&2; }
die() { echo "[stopped] $*" >&2; exit 1; }

case "$SCOPE" in all|profile|org) ;; *) die "Use: bash bootstrap-profile-org.sh [all|profile|org]" ;; esac
for command in gh curl python3 base64; do
  command -v "$command" >/dev/null 2>&1 || die "Missing $command. In Termux: pkg install gh curl python coreutils"
done

log "Using GitHub CLI; authentication is handled by GitHub, not this script."
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth login --hostname github.com --git-protocol https --web --scopes "repo,user,read:org"
fi
ACTUAL_OWNER="$(gh api user --jq '.login')"
if [ "$ACTUAL_OWNER" != "$OWNER" ]; then
  die "GitHub CLI is logged in as $ACTUAL_OWNER. Switch to $OWNER using gh auth switch or reauthenticate. No changes made."
fi
log "Account confirmed: $ACTUAL_OWNER"

fetch_template() {
  local name="$1" destination="$2"
  curl --fail --location --silent --show-error --retry 2 "$SOURCE_URL/$name" --output "$destination"
  test -s "$destination" || die "Missing template: $name"
}

# Updates one file using the GitHub Contents API; backs up previous content on this device.
publish_file() {
  local target_repo="$1" target_path="$2" source_file="$3" old_sha="" encoded="" backup=""
  old_sha="$(gh api "repos/$target_repo/contents/$target_path" --jq '.sha' 2>/dev/null || true)"
  if [ -n "$old_sha" ]; then
    backup="$BACKUP_DIR/$(echo "$target_repo--$target_path" | tr '/' '_')"
    if gh api "repos/$target_repo/contents/$target_path" --jq '.content' | tr -d '\r\n' | base64 --decode > "$backup"; then
      if cmp -s "$backup" "$source_file"; then
        log "Already current: $target_repo/$target_path"
        return
      fi
      log "Previous version saved locally: $backup"
    else
      rm -f "$backup"
      warn "Couldn't back up $target_repo/$target_path; skipping the update."
      return
    fi
  fi
  encoded="$(python3 -c 'import base64,sys; print(base64.b64encode(open(sys.argv[1],"rb").read()).decode("ascii"))' "$source_file")"
  if [ -n "$old_sha" ]; then
    gh api --method PUT "repos/$target_repo/contents/$target_path" --field "message=Update public profile and community documentation" --field "content=$encoded" --field "sha=$old_sha" >/dev/null
  else
    gh api --method PUT "repos/$target_repo/contents/$target_path" --field "message=Publish public profile and community documentation" --field "content=$encoded" >/dev/null
  fi
  log "Published: https://github.com/$target_repo/blob/HEAD/$target_path"
}

if [ "$SCOPE" = "all" ] || [ "$SCOPE" = "profile" ]; then
  log "Preparing personal GitHub profile README..."
  fetch_template "PROFILE_README.md" "$TEMP_DIR/profile.md"
  if ! gh repo view "$OWNER/$OWNER" --json name >/dev/null 2>&1; then
    gh repo create "$OWNER/$OWNER" --public --add-readme --description "Daniel Munoz | Practical technology projects and professional portfolio"
    log "Created public GitHub profile repository"
  fi
  publish_file "$OWNER/$OWNER" "README.md" "$TEMP_DIR/profile.md"
  if gh api --method PATCH user --field "name=Daniel Munoz" --field "location=Auckland, New Zealand" --field "bio=⚡ Mod it. Fix it. Automate it. | Linux • Android • Networking | Building useful tools | Open to IT roles, paid tech work & collaborations 🇳🇿" --field "hireable=true" >/dev/null 2>&1; then
    log "Updated GitHub name, bio, location and hireable indicator."
  else
    warn "Profile fields unchanged; GitHub OAuth may need Profile write permission. Try gh auth refresh -s user, then rerun."
  fi
  if gh api "repos/$SOURCE_REPO/pages" >/dev/null 2>&1; then
    log "GitHub Pages already configured for $SOURCE_REPO."
  else
    if gh api --method POST "repos/$SOURCE_REPO/pages" --field "source[branch]=master" --field "source[path]=/docs" >/dev/null 2>&1; then
      log "GitHub Pages requested from master/docs; verify after deployment."
    else
      warn "GitHub Pages not enabled; visit https://github.com/$SOURCE_REPO/settings/pages and select master/docs."
    fi
  fi
  log "Profile: https://github.com/$OWNER"
fi

if [ "$SCOPE" = "all" ] || [ "$SCOPE" = "org" ]; then
  log "Checking organisation ownership: $ORG_SLUG"
  ORG_ROLE="$(gh api "user/memberships/orgs/$ORG_SLUG" --jq '.role' 2>/dev/null || true)"
  if [ "$ORG_ROLE" != "admin" ]; then
    warn "The organisation does not yet exist under your ownership, or permissions are insufficient."
    warn "Create the free organisation in a browser: https://github.com/account/organizations/new"
    warn "Suggested login: $ORG_SLUG. After creation run: ORG_SLUG=$ORG_SLUG bash bootstrap-profile-org.sh org"
  else
    if ! gh repo view "$ORG_SLUG/.github" --json name >/dev/null 2>&1; then
      gh repo create "$ORG_SLUG/.github" --public --add-readme --description "Organization profile and shared community guidelines"
      log "Created public organization profile repository: $ORG_SLUG/.github"
    fi
    fetch_template "org-kit/profile/README.md" "$TEMP_DIR/org-profile.md"
    fetch_template "org-kit/CONTRIBUTING.md" "$TEMP_DIR/CONTRIBUTING.md"
    fetch_template "org-kit/SECURITY.md" "$TEMP_DIR/SECURITY.md"
    fetch_template "org-kit/ISSUE_TEMPLATE/bug_report.yml" "$TEMP_DIR/bug_report.yml"
    fetch_template "org-kit/PULL_REQUEST_TEMPLATE.md" "$TEMP_DIR/PULL_REQUEST_TEMPLATE.md"
    fetch_template "org-kit/OPERATING_PLAN.md" "$TEMP_DIR/OPERATING_PLAN.md"
    fetch_template "org-kit/RELEASE_CHECKLIST.md" "$TEMP_DIR/RELEASE_CHECKLIST.md"
    publish_file "$ORG_SLUG/.github" "profile/README.md" "$TEMP_DIR/org-profile.md"
    publish_file "$ORG_SLUG/.github" "CONTRIBUTING.md" "$TEMP_DIR/CONTRIBUTING.md"
    publish_file "$ORG_SLUG/.github" "SECURITY.md" "$TEMP_DIR/SECURITY.md"
    publish_file "$ORG_SLUG/.github" ".github/ISSUE_TEMPLATE/bug_report.yml" "$TEMP_DIR/bug_report.yml"
    publish_file "$ORG_SLUG/.github" "PULL_REQUEST_TEMPLATE.md" "$TEMP_DIR/PULL_REQUEST_TEMPLATE.md"
    publish_file "$ORG_SLUG/.github" "OPERATING_PLAN.md" "$TEMP_DIR/OPERATING_PLAN.md"
    publish_file "$ORG_SLUG/.github" "RELEASE_CHECKLIST.md" "$TEMP_DIR/RELEASE_CHECKLIST.md"
    log "Organization homepage ready: https://github.com/$ORG_SLUG"
    log "Repositories remain in your personal account unless you deliberately transfer them."
  fi
fi

log "Bootstrap finished. Previous file versions (if any): $BACKUP_DIR"
log "Upload your avatar manually in https://github.com/settings/profile; the REST API does not offer an avatar upload operation."
