# Release readiness checklist

A release is not a release just because a ZIP exists.

## Minimum requirements before adding a public Download button

- [ ] Source ownership and licence verified, including dependencies and upstream attribution.
- [ ] Document exact versions, supported devices/OS, required permissions and installation steps.
- [ ] Automated tests pass for core functions and realistic failure states.
- [ ] A clean installation succeeds on at least one explicitly named supported device or environment.
- [ ] No embedded secrets, API keys, user records, unsafe sample credentials or unauthorised data.
- [ ] Privacy and security risks documented, with a safe way to report bugs.
- [ ] A reproducible release build exists and its checksums are published where appropriate.
- [ ] Any APK is built, signed and tested; do not market a debug-only artifact as a production Android release.
- [ ] Features and measurements are labelled measured, simulated, unsupported or unknown as appropriate.
- [ ] GitHub Release has a changelog, direct asset URL and known-issues section.

## What may be advertised earlier

**Public Python source:** advertise 'source and setup' or 'source ZIP', not 'APK download'.

**Private prototype:** advertise 'request a demo' or 'private preview', not an unverified app-store release.

**Simulated demo:** clearly disclose simulated data, and don't claim client adoption based on test data.

## After the first real release

Track actual installations, bug reports, stars, user retention and explicit customer feedback. A repo view is not a download and a star is not a sale.
