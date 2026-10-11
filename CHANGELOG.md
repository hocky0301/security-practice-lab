# Changelog

## 0.1.0 - 2026-10-11

First public version.

- Modules: release approval and context, dependency exception policy, tool definition contracts, one-use authorization, shared budget, memory and revocation, audit log, recovery, observation freshness.
- 139 unit tests, standard library only.
- Saved synthetic results in `results/`, and `verify_reproduction.py` to recompute and compare them.
- A browser demo of observation freshness: `demos/green_room.html`.
- GitHub Actions workflow (Python 3.11 and 3.12) and Dependabot settings for the Actions versions. They have not yet run on GitHub as of this version.
- `scripts/verify_fresh_clone.sh`: clone, install in a new virtual environment, run the tests and the reproduction check.
