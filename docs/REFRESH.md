# Refresh and verification

1. Ground in `METHOD.md`, this handoff and the live workbook. Record the existing workbook identity privately. Read Method source/revision and Pick Review before any write. Resolve an approved policy difference rather than overwriting it.
2. Determine the requested slate date in America/Chicago and the completed-game cutoff. Gather completed NBA games since the workbook cutoff. Keep prior-season, current-season and recent windows distinct.
3. Run the core/event pipeline. Reconcile box-score and play-by-play attempts, makes, rebounds, assists and second-chance fields. Missing or failed games remain explicit. Preserve valid reconstructed rebound links even when NBA's separate second-chance tag is absent.
4. Run tracking fetch, analysis and sensitivity. Match tracking to games and NBA possession counts; compare tracked attempts and makes with opposing box totals. Report missing and partial coverage, eligible games and possessions. Never publish coverage-dependent league ranks from incomplete comparisons.
5. Inspect generated manifests and dated cutoffs. Data validation confirms source reconciliation; it does not validate a betting model. The core report alone does not complete Pass 2.
6. Update the existing workbook in place through an authorized Sheets connection. Preserve Pick Review choices and notes using date + game ID + player ID, along with user-added fields. Keep coverage notes separate from canonical policy. The repository currently supplies local export pipelines and a method-sync payload generator, not an unattended workbook updater.
7. Mirror committed policy with `export_method.py`, keeping the source commit/hash visible. Read back edited cells and verify cutoffs, row counts, picks and coverage. Stop after refresh when the user requested refresh only.

## Reusing saved inputs

`bbb_triples.py --offline` and `fetch_tracking.py --offline` require every exact request cache entry. Reuse of final event responses is recorded; explicit replay must not be described as fresh ingestion. For source corrections, refresh the affected requests deliberately and record the new fetch times.

Tracking analysis expects `inputs.json` from the tracking fetch and `boxlogs.json` with its `payload` wrapper. Existing compatible archives can be analyzed with `--data-dir` without being copied into Git. Outputs are `analysis.json`, `defense_summary.csv` and `sensitivity.json`.
