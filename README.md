# BBB Basketball

NBA three-point matchup research: identify offensive strengths that can exploit specific defensive concessions, then examine individual shooters one team at a time.

## Start here

1. Read [agent grounding](AGENTS.md), the [canonical method](METHOD.md), and the [handoff](docs/HANDOFF.md).
2. Locate the existing workbook using [the data map](docs/DATA_MAP.md), then check its actual cutoff and coverage. Repository policy does not refresh data automatically.
3. Run volume / own shooting / pace, schedule-adjusted shot quality, three-point assist creation, and OREB in that order. Complete availability review before player selection.
4. Apply Advance / Watchlist / Reject to the combined evidence. A shortlist has a maximum length, not a minimum. Zero survivors is valid.

The core carries 92.5% of the judgment, assists a provisional 5%, and OREB at most 2.5%. These are agreed priorities, not fitted predictive coefficients. Raw opponent 3P% does not establish perimeter weakness. Read [worked examples](docs/examples/2026-11-17.md) before interpreting conflicting metrics.

## Run locally

Python 3.10+ and the standard library are sufficient for the scripts in this repository.

```bash
python -m unittest -v
python bbb_triples.py --date 2026-11-17 --out output/2026-11-17
python fetch_tracking.py --date 2026-11-17 --out tracking/2026-11-17
python analyze_tracking.py --data-dir tracking/2026-11-17
python tracking_sensitivity.py --data-dir tracking/2026-11-17
```

Dates above are examples. `--date` defaults to today in America/Chicago; each run excludes results on the slate date. NBA can reject hosted requests; failures and missing coverage must stay explicit. Offline replay requires exact saved requests. Large request caches and generated data are local, ignored files.

`bbb_triples.py` gathers the traditional/advanced/opponent screen and reconciles box scores and play-by-play. It shows schedule-order directional comparisons with raw figures and percentiles. The retired component-count sorter is no longer calculated. `fetch_tracking.py` gathers current-season daily defender-distance buckets and matched possessions. `analyze_tracking.py` computes opponent-adjusted expected threes. `tracking_sensitivity.py` separates volume from quality and checks fully tracked team-games.

These commands produce local data, audits and reports. They do not automatically select final candidates, research availability, project player roles, or edit the Google Sheet. Follow [the refresh procedure](docs/REFRESH.md) to complete those steps and preserve workbook state.

## One authoritative method

Edit `METHOD.md` in Git. From the committed checkout, configure the existing workbook privately and export the exact mirror payload:

```bash
export BBB_SPREADSHEET_ID='your-existing-workbook-id'
export BBB_METHOD_SHEET_ID='your-existing-method-tab-id'
python export_method.py --out output/method_update.json
```

Apply the generated `requests` to the configured existing workbook with an authorized Sheets connection, then read back the changed cells. Export also records the exact commit and METHOD.md SHA-256. It preserves dated snapshot rows and never includes Pick Review. A downloaded source copy may supply the known commit through `BBB_METHOD_COMMIT`; the exporter then retrieves METHOD.md from that pinned public commit and requires an exact byte-hash match. A declared commit alone remains unverified and cannot authorize an export. If remote source verification is unavailable, use a clean Git checkout or restore source access.

This public repo contains reusable policy, code and public-statistic examples. The private workbook, picks, credentials and generated account data are supplied through local configuration. No license grant for NBA data or third-party transcripts is implied.

## Sources

- [NBA team statistics](https://www.nba.com/stats/teams/traditional)
- [NBA tracking](https://www.nba.com/stats/teams/opponent-shooting)
- [NBA official injury reports](https://official.nba.com/)
