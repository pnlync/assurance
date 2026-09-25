# CLAUDE.md

Life protection actuarial model (portfolio project). **SPEC.md is the build specification — read it in full before any work, and follow §0 (rules for the agent).**

## Key rules (from SPEC §0, repeated because they are the ones most often broken)
- Never edit the golden values in SPEC §13.3 or the tests that check them. A failing golden test means the implementation is wrong; report the diagnosis.
- No invented regulatory/accounting parameters: every SII / IFRS 17 number must be in SPEC §4 with its source.
- All assumptions live in `assumptions/*.yaml`; no magic numbers in `src/`.
- Experience-study code (`experience.py`) must never read `truth.yaml`. Only `simulate.py` may.
- Every public function's docstring cites the SPEC section it implements.
- Build phase by phase (SPEC §14); write `docs/phase_N_summary.md` after each phase.
- If SPEC is ambiguous or looks wrong: stop and ask. Don't guess.

## Owner context
- The owner is learning life actuarial work through this project and must be able to explain every line in interviews. Prefer readable, explicit numpy over clever code. After each phase, explain what was built in Chinese using policy F1 as the worked example.
- `private_notes/` holds the owner's planning guides (Claude and ChatGPT versions, CV and interview prep). It is gitignored — never commit, quote into public files, or publish it.

## Environment
- Python 3.12 via uv (`uv sync`, `uv run pytest`). SPEC §14 says 3.11; 3.12 is used because uv's 3.11 build is killed by macOS on this machine.
- GitHub: git@github.com:pnlync/assurance.git (SPEC Appendix A calls the repo `life-protection-model`; the package is `lifemodel`).
- Raw data is downloaded manually into `data/raw/` (see its README) and is not committed.
