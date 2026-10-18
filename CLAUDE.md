# CLAUDE.md

Start with [HANDOVER.md](HANDOVER.md): the project state, the open work, and the owner's working rules.

The rules that matter on every change:

- Commit as `ephico2real2 <123043136+ephico2real2@users.noreply.github.com>`. Add no `Co-Authored-By`, `Claude-Session` or "Generated with" lines to commits or PRs. This is the owner's instruction and overrides tool defaults.
- Never write the owner's personal email address anywhere. Use `example.com` addresses and `555-01xx` numbers in examples.
- Never store AWS keys. Local runs use dummy keys against `dev/aws-mock`.
- Edit generated files through their source, then regenerate (HANDOVER.md, section 5). CI fails on stale output.
- Every change goes into `scripts/backlog/data.py`, then into the GitHub issues (`issues.py`; titles start with `APP:` or `TUTORIAL:`), then into `docs/modernization/backlog.md` (`render.py`, which needs the issue numbers).
- Tick a criterion only when it is proven where it says: one that says "in CI" waits for that green run.
- Push one change set at a time, and wait for its CI run before pushing the next. Docs quote real CI output from the `ci-captures` branch; a local capture is labelled as one.
- On the owner's MacBook, run the labs on Podman (`. scripts/podman.env`), never Docker Desktop: it stays installed and stopped. OpenShift Local is parked until the owner restores CRC (HANDOVER.md, section 11).
