# Grounding for BBB Basketball

Read `METHOD.md`, `docs/HANDOFF.md`, `docs/DATA_MAP.md`, and the relevant dated examples before analysis or code changes. State the data cutoff and source revision. If private configuration is absent, use the exact workbook-title and tab-fingerprint discovery in DATA_MAP before asking the user for a URL. The user's current instructions take priority.

- `METHOD.md` is the canonical policy. The workbook Method tab is a generated mirror with a commit and content hash. Check both when refreshing; reconcile an approved sheet change before replacing it.
- Analyze the full matchup: offense strength versus the defense's specific conceded opportunities. Separate total volume from shot quality. Read absolute rates and baseline differences beside percentiles. A single positive or negative statistic is not a qualification rule.
- Run passes in order. Carry forward Advance / Watchlist / Reject, the strongest counterevidence and the reason for each ranking change. Up to N means a maximum, including zero. Do not manufacture replacements.
- Complete availability research with official reports and credible local reporting, then use an evidence-based expected rotation and state confidence. Confirmed starters are not a prerequisite. Substantial alternatives belong in conditional ranges.
- Review players one team at a time. Use observed minutes, attempts, conversion, creator-to-shooter links and shot-type fit. Bench players are eligible. A good player does not retroactively qualify a rejected team.
- Keep the private workbook ID, credentials, picks and account information in local configuration. This repository is public. Do not commit private workbook exports, account screenshots, credentials or personal bet records. Do not change repository visibility without the user's instruction.
- Preserve the existing workbook, Pick Review entries, dated cutoffs and coverage notes. A refresh request stops after refresh. Do not announce complete coverage unless it is verified.
- Prefer existing scripts and focused validation. Never claim that running the core screen completes tracking, availability, player selection or a Sheets write. Record which stages actually ran.

Useful commands and the refresh boundary are documented in `README.md` and `docs/REFRESH.md`. `docs/examples/2026-11-17.md` explains both forced-selection and single-metric-veto failures.
