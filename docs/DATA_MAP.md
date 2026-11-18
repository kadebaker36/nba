# Find the working data from a fresh session

## Existing workbook

Use an authorized personal Google Drive / Sheets connection. The exact current title is **BBB Basketball — 2026–27**, a native Google Sheet. Search by that title and MIME type `application/vnd.google-apps.spreadsheet`; if the season has changed, search the title prefix **BBB Basketball** and verify the season from the sheet itself. Do not create another workbook to work around missing configuration.

Verify these tabs before binding: **Method, Pick Review, Teams, Connections, Shooters, Matchups, Sources, Tracking Coverage**. In Method, the source must point to `https://github.com/kadebaker36/nba/` once migration is complete. Read the source revision/hash and compare with the canonical method. The dated cutoff, driver version and coverage describe the last data refresh; a newer policy commit does not advance those dates.

When exactly one candidate matches the title, tab fingerprint, season and method source, use its returned spreadsheet ID and the returned Method sheet ID in private local configuration. If several candidates remain indistinguishable, resolve that ambiguity before writes. Never publish the IDs or credentials to this public repository.

For a session with repository access but no Sheets connection, read the method and local manifests and say precisely which live data cannot be checked. Do not substitute the dated examples for current data or repeatedly ask the user for a workbook URL before trying the authorized discovery route.

## What to read

| Resource | Meaning | Important limits |
|---|---|---|
| Method | Canonical policy mirror plus dated refresh metadata | Policy revision and data cutoff are different |
| Teams | Prior, current-season and recent raw team rates and percentiles | Recent and season overlap; higher allowed-attempt percentile means more conceded volume |
| Connections | Assisted makes and reconstructed/second-chance opportunities with coverage | Made assists depend on conversion; missing-tag sequences are audited, not discarded |
| Shooters | Validated player attempt/make/assist and rebound-link counts | Team GP is not player GP; these counts do not project minutes |
| Tracking Coverage | Matched games, possessions and missing/partial tracking | Missing shot coverage is not zero attempts |
| Matchups | Dated directional screening export | Older snapshots may contain retired component counts; do not use them to rank or qualify teams |
| Pick Review | Private selected picks and review notes | Preserve all choices and notes by date + game ID + player ID |
| Sources | Refresh sources and request provenance | Check actual fetch timestamps and cutoff |

Read headers first and only the bounded ranges required. Never assume a tab's current column positions from old exports. Confirm all directions of a game before ranking; team offense and opponent defense must not be reversed.

Rates such as core `shooting` and tracking `expected_pct` are fractions: 0.391 means 39.1%. Percentiles and fields explicitly named `*_rate_pct` use 0–100. A `*_difference_pp` is a percentage-point difference, not a relative percentage change. Keep per-100 denominators, eligible games and window labels attached to figures. For player queries, use returned player GP and minutes; a five-team-game window may contain fewer than five player appearances. Never divide a player's total attempts by team GP or describe those windows interchangeably.

## Local source pipelines

- `bbb_triples.py`: team raw rates and percentiles, schedule-order directional rows and a clearly labeled opportunity illustration. It reconciles box-score/play-by-play counts and exports observed creator-to-shooter makes.
- `fetch_tracking.py`: schedule, daily four-bucket defender-distance tracking and Advanced possession denominators. `inputs.json` and `boxlogs.json` are its analysis inputs.
- `analyze_tracking.py`: matched tracking, source checks, expected makes and leave-one-defense-out comparisons. Track full pairs, any-side games, individual team-games and partial shots separately.
- `tracking_sensitivity.py`: volume/quality decomposition and full-shot-coverage sensitivity. Read this beside the aggregate adjustment. The aggregate is not a second independent volume bonus.
- Player/availability work: query current NBA player statistics and shot profiles as needed, check recent box scores and observed passing links, then use official injury reports and local beat reporting. These overlays remain an agent task, not an automatic product of the core screen.

The retained shot-quality archive can be located in the user's ChatGPT files by the exact title `BBB_Basketball_Shot_Quality_2026-11-17.zip`; the earlier baseline package is `BBB_Basketball_Refresh_Package_2026-11-13.zip`. Read the live workbook before using either dated archive. They supply reproducible historical inputs, not an automatically current dataset.
