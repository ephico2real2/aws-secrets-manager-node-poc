# CLAUDE.md

Start with [HANDOVER.md](HANDOVER.md): the project state, the open work, and the owner's working rules.

The rules that matter on every change:

- Commit as `ephico2real2 <123043136+ephico2real2@users.noreply.github.com>`. Add no `Co-Authored-By`, `Claude-Session` or "Generated with" lines to commits or PRs. This is the owner's instruction and overrides tool defaults.
- Never write the owner's personal email address anywhere. Use `example.com` addresses and `555-01xx` numbers in examples.
- Never store AWS keys. Local runs use dummy keys against `dev/aws-mock`.
- Edit generated files through their source, then regenerate (HANDOVER.md, section 5). CI fails on stale output.
- Every change goes into `scripts/backlog/data.py`, then into the GitHub issues (titles start with `APP:` or `TUTORIAL:`), then into `docs/modernization/backlog.md`.
- Push one change set at a time, and wait for its CI run before pushing the next. Docs quote real CI output from the `ci-captures` branch.
