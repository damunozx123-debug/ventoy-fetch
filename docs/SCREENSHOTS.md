# CLI screenshots

Ventoy Fetch is a Termux/Python command-line application, so the useful screenshots are terminal output and the interactive selector rather than a made-up Android GUI.

## Capture the real catalog output

Install and run as documented in [INSTALL_TERMUX.md](INSTALL_TERMUX.md), then use Termux's screenshot action after:

```sh
python3 ventoy_fetch.py --list
```

Or save a record of the actual output:

```sh
python3 ventoy_fetch.py --list > catalog-output.txt
```

Only publish a screenshot of the `--list` or menu UI; do not share directories with identifying details, private manifest paths, tokens or download credentials. A catalog screenshot is not proof that a particular ISO was downloaded, verified or booted.

## Documentation status

A screenshot of the running v7 CLI must be captured on Termux or an isolated Linux runner. No unrelated screenshot is presented as evidence.
