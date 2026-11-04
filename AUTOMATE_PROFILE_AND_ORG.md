# ⚡ Automated GitHub profile and organisation bootstrap

**Current linked account:** damunozx123-debug. **Suggested organisation name:** Munoz Tech Labs (slug: munoz-tech-labs). The organisation name is a proposal until you create it; don't claim it is available or already registered.

## What has already been published

- Portfolio page: [PORTFOLIO.md](PORTFOLIO.md)
- Personal GitHub profile source: [PROFILE_README.md](PROFILE_README.md)
- Public service offer: [WORK_WITH_ME.md](WORK_WITH_ME.md)
- Project evidence: [PROJECTS.md](PROJECTS.md)
- Website source: [docs/index.html](docs/index.html)
- Organisation profile and contributor/security templates: [org-kit/](org-kit/)
- Business operating plan: [org-kit/OPERATING_PLAN.md](org-kit/OPERATING_PLAN.md)
- Public release checklist: [org-kit/RELEASE_CHECKLIST.md](org-kit/RELEASE_CHECKLIST.md)

## One-copy setup from Android/Termux

GitHub account creation and organisation creation cannot be performed by the current ChatGPT GitHub connection. This script uses **your own GitHub CLI session** on your Android device and never asks you to paste an access token into ChatGPT.

Install dependencies, download the script and execute it:

    pkg install gh curl python coreutils -y
    curl -fL https://raw.githubusercontent.com/damunozx123-debug/ventoy-fetch/master/scripts/bootstrap-profile-org.sh -o bootstrap-profile-org.sh
    bash bootstrap-profile-org.sh

The first run asks you to authorise GitHub through its official login flow if you have not already signed in. It **aborts without making changes** if the active username is not damunozx123-debug.

### What the script automates

1. Creates the **public personal profile repository** named damunozx123-debug (if absent).
2. Publishes the matching README from PROFILE_README.md, backing up previous versions locally before updates.
3. Attempts to set personal display name, bio, location and hireable status via GitHub's user API.
4. Attempts to enable GitHub Pages for this repository from master/docs.
5. If you own the proposed GitHub organisation, creates its **public .github repository**, profile README and common issue/security/contribution templates plus an operating plan and release-readiness checklist.

The script is idempotent for matching file content; reruns reuse existing repositories. It will **not** transfer or publish any of your private app repositories.

## One GitHub organisation setup step

GitHub requires its website flow to create a personal organisation. Open [Create new organisation](https://github.com/account/organizations/new) while logged into damunozx123-debug, choose a Free plan if it suits you, and set the name/slug you actually want.

Suggested brand: **Munoz Tech Labs**; proposed slug: **munoz-tech-labs**.

After creating it, run:

    ORG_SLUG=munoz-tech-labs bash bootstrap-profile-org.sh org

If you choose another slug, substitute it in that command. The script checks that you're an organisation admin before creating its public .github profile repository.

## Still requires GitHub UI

- Upload the penguin **avatar** in [Profile Settings](https://github.com/settings/profile); GitHub's profile-update REST endpoint doesn't offer avatar upload.
- Set and verify your pinned repositories.
- Confirm that the Pages site reports an actual deployment before adding its URL to other profiles.
- Choose any organisation privacy settings, billing tier, logo, team invites or repo transfers deliberately.

## Why this is structured this way

**Personal account** = employment portfolio and attributable project evidence.

**Munoz Tech Labs organisation** = public-facing umbrella for collaboration, services and future releases, without hiding your actual experience or making invented business claims.

**Private prototypes remain private.** Do not equate a simulated demo with paid deployments or a source ZIP with a downloadable Android APK.

## Repairing an older bootstrap (4 November 2026)

If an earlier run printed `gh: Not Found (HTTP 404)`, `base64: invalid input` and `Couldn't back up ...; skipping`, that version contained a bug handling **files that do not exist yet**. It may have created the public organisation's `.github` repository without uploading its profile files.

**Fixed:** commit [0b78169](https://github.com/damunozx123-debug/ventoy-fetch/commit/0b7816963dff229aac15034d1d3106a17f20ee1b). A [CI regression test](https://github.com/damunozx123-debug/ventoy-fetch/actions/runs/41754854568) exercises simulated 404, existing files, backups and 403 denial.

Download the corrected script (this command explicitly overwrites your old local copy), then run org-only mode:

```sh
curl -fL https://raw.githubusercontent.com/damunozx123-debug/ventoy-fetch/0b7816963dff229aac15034d1d3106a17f20ee1b/scripts/bootstrap-profile-org.sh -o bootstrap-profile-org.sh
bash -n bootstrap-profile-org.sh
ORG_SLUG=munoz-tech-labs bash bootstrap-profile-org.sh org
```

When successful, expect **seven `Verified:` lines**, then `Organization homepage ready`. If GitHub denies access with a 403 error, the corrected script stops rather than pretending to have published files. No private repositories are transferred.

Confirm the public homepage at https://github.com/munoz-tech-labs and the backing profile file at https://github.com/munoz-tech-labs/.github/blob/main/profile/README.md.
