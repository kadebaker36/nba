# Handoff — November 17, 2026

## Authority and grounding

The workflow has migrated from a workbook-only Method tab to canonical `METHOD.md` in this repository. The Method mirror records the source commit and hash. Current user instructions supersede either. Check that workbook policy changes have been reconciled before regenerating the mirror.

Start future sessions with: "Ground in kadebaker36/nba: read AGENTS.md, METHOD.md and docs/HANDOFF.md, then check the live workbook's cutoff and coverage. Follow the passes in order and analyze players one team at a time."

## Last verified data snapshot

The working workbook was refreshed through November 16, 2026: 205/205 completed games and 3,280 box-score checks. Defender-distance tracking matched 204/205 games, 408 team-games and 41,000 possessions. There were 103 partially tracked team-games. Fully tracked sensitivity retained 305 team-games. These counts describe that dated run, not a current automatic refresh or proof of predictive performance.

The user's earlier refresh and shot-quality archive remains separate from Git. Private connection details belong in local configuration; obtain the existing workbook through the authorized Google connection rather than creating another workbook.

## Implementation state

- Core and play-by-play runner migrated from v0.2.1, with current policy grounding and metadata attached. The legacy five-component sorter remains a research screen only.
- Defender-distance fetching, leave-one-defense-out expected threes, and full-tracking sensitivity are available as separate reproducible scripts. The original November 17 analysis was date-specific; the migrated scripts accept arbitrary data directories and derive coverage from the input rather than assuming 205 games.
- Reports include the canonical method revision and hash. The method export generates Sheets API requests; applying them requires an authorized connection and live tab metadata. There is no automatic Google Sheets data writer or scheduled refresh.
- Catch-and-shoot opportunities and individual player profiles require additional targeted NBA queries. Standard play-by-play provides recorded passers on makes, not missed-shot passers or potential assists. Do not pretend those fields are complete.
- Current roles and availability always need a fresh review for the requested slate. Old examples are not current lineup advice.

## Interpretation corrections to preserve

The shortlist must be allowed to shrink. Later passes can reject an initially attractive offense. Equally, overall attempt suppression must not become an automatic veto when an offense may exploit a particular conceded shot profile. Read the dated examples and write the complete thesis before ranking. A user challenge triggers an evidence check, not automatic agreement.
