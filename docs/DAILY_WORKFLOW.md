# Daily NBA launch and four-role bootstrap

This is a local stdlib planner and a hosted-team bootstrap protocol. These files create **no deployed scheduling, automation task, Sheets writer, external model API service or infrastructure**. Root owns real scheduling, private task IDs and publication. Routine public NBA ingestion, refresh of the existing workbook and analysis are standing authorized under the user's current instruction; there is no repeated human launch hold. Actual writes require verified capabilities and bounded Supervisor orders. A refresh-only request still stops after refresh, as METHOD.md requires.

## Plan an explicit Chicago slate

```bash
python daily_plan.py --date 2026-11-20 --fetch
python daily_plan.py --date 2026-11-20 --schedule-json /PRIVATE/schedule.json --source-label 'Root-fetched snapshot'
python -m unittest -v
```

Replace the date and private path. The planner validates `daily_roles.json` on each invocation. It fetches only the official `scheduleLeagueV2_1.json` URL using the existing NBA request headers, or reads an official JSON payload / existing exact-URL `get_json` cache envelope. It does not fetch statistics, write a cache or create a task. Save plan output and raw input privately for reproduction. A saved file is a read, even if its envelope records a previous live fetch. JSON includes the source URL, read/fetch times, raw input SHA256, canonical payload SHA256 and hash format. The schedule snapshot is separate from statistical freshness.

The required `--date` is `YYYY-MM-DD` in `America/Chicago`. Output is JSON: `state`, `first_tip_at`, `launch_at`, `results_cutoff` (the preceding Chicago calendar date), all active eligible game IDs, exclusions, unresolved IDs, provenance and errors. `ready` means an exact schedule plan, **not** a fresh-data/report receipt or permission to treat an already-started game as pregame. Tips are aware UTC instants from `gameDateTimeUTC`, converted to Chicago. Subtract 120 elapsed minutes in UTC before converting launch time, including across DST and midnight. Never use the time-only `1900` fields or nominal Eastern date as a tip.

The supported schema requires league `00`, matching `seasonYear`, unique nominal Eastern date buckets and unique ten-digit NBA IDs with matching season digits. Regular-season IDs start `002`, as in the core pipeline; cup group/knockout games in that family count. Preseason `001`, All-Star `003`, postseason `004`/`005` and cup-final `006` do not. Labels such as “NBA Cup” do not decide eligibility. UTC dates, nominal Eastern date, game code and team identity must agree. Unknown schema, phase, status, date or identity fails visibly; new schemas require review, not a guess.

Known `gameStatus` values are 1 scheduled, 2 live and 3 final; live/final retain their original tip for missed-launch recovery. Cancelled/Canceled or Postponed/PPD scheduled games, or scheduled games with `postponedStatus=Y`, are excluded with a reason. A rescheduled game becomes eligible at its new tip when the source restores active status (`N`). Contradictory inactive/live-final status is an error. Unknown status codes/flags are errors. A TBD/TBA/missing time or explicit `gameTimeTBD=true` blocks an exact plan if its nominal Eastern date is the requested Chicago date **or the next day**. Placeholder times cannot silently remove a potentially relevant game. Unresolved teams/code also block relevant active games.

`no_games` (exit 0) requires an explicit date bucket and no eligible or potentially relevant games; an empty bucket or all excluded/nonregular games qualifies. An absent date is `error`, not proof of an empty slate. This conservative behavior also handles incomplete/truncated saved schedules. `error` exits 2, emits no exact tip/launch and must be retried or investigated. CLI usage errors are ordinary argparse errors. Plan fields are deterministic for a given payload/date/profile; observation timestamps naturally vary. The planner makes no completeness claim about an upstream schedule beyond its validated input.

## Dispatcher and exact per-day launcher

Root configures an external dispatcher to re-read the official schedule regularly and again before launch; no fixed season-long clock substitutes for tip changes. For each explicit Chicago slate date, Root maintains a private date key `NBA:YYYY-MM-DD:America/Chicago` and an atomic exclusive launch claim (or equivalent verified scheduler deduplication), plus one exact per-day launch task. Private state and artifacts live outside public Git in a durable location. Record actual save receipts; `/tmp` and this workspace alone are not durable recovery guarantees.

| Observed state | Root/Admin action and durable receipt |
| --- | --- |
| `ready`, future launch | Record plan/hash/revision and privately bind one per-day task to the exact launch instant; replace that task on a changed plan, cancelling/verifying the old task first. |
| `no_games` | Record dated no-games result and source; launch no team. Recheck schedule changes; adding a game may reopen planning before any launch claim exists. |
| `error` / unknown | Keep pending/error, retain evidence, retry with a fresh source or correct the schema; never mark daily completion or create an exact-time task. |
| Launch missed but first tip still future | Claim/resume this date once and run immediately, recording actual lateness. |
| First tip already passed | Resume the same run, identify already-started games, and disclose unavailable pregame coverage. Never backdate evidence. Review only still-eligible future games with genuine pre-tip evidence and finish a truthful report. |
| Tip/cancellation changes after launch | Replan under the same date key and role bindings; update affected stages/candidates and evidence, not a second daily quartet. |

The exact per-day launcher receives the date, checkout revision, current plan/source hashes and private state reference. It re-fetches/revalidates schedule, reconciles changed launch/task state, and atomically claims the date before spawning. Existing active or completed claims prevent duplicate launches. An accepted spawn with uncertain response remains pending: reconcile actual role existence before retrying. Completion is date-keyed and records actual report delivery plus verified required stages. A blocked writer or unknown schedule is not successful refresh/completion. Record a delivered partial report separately from outstanding required stages. Recover at the last read-back-verified stage, keeping prior attempts/evidence; never reset the run just to rerun all writes. If a role is lost, Root explicitly supersedes its binding and records recovery; reconcile outstanding writes/sends first.

Suggested private record fields: date key, generation/claim owner, lifecycle status, planned/actual launch, source URL/hash/fetch/read times, first tip/cutoff, Git HEAD and METHOD hash, task binding, each actual role ID and accepted spawn controls, current work-order/reference hash, pending sends, stage attempts/checkpoints, workbook identity, read-back receipts, coverage/limitations and report delivery. IDs, credentials, private workbook data and picks never enter this repository.

## Fresh hosted team startup

Root creates **Admin**, then Admin creates the other three roles: exactly four roles total, no parallel implementers. Validate the public profiles with `daily_plan.validate_profiles` before dispatch. Use actual `collaboration.spawn_agent` calls with these arguments; replace task names and complete `message` seeds for the actual date. These are tool-call bodies, not a local Python orchestration API:

```json
{"task_name":"bbb_admin_YYYYMMDD","model":"gpt-6.1-sol","reasoning_effort":"medium","fork_turns":"none","message":"<complete Admin seed>"}
{"task_name":"supervisor","model":"gpt-6.1-sol","reasoning_effort":"high","fork_turns":"none","message":"<complete Supervisor seed>"}
{"task_name":"codex","model":"gpt-6.1-sol","reasoning_effort":"medium","fork_turns":"none","message":"<complete Codex seed>"}
{"task_name":"bridge","model":"gpt-6-luna","reasoning_effort":"low","fork_turns":"none","message":"<complete Bridge seed>"}
```

Register the **actual returned role IDs**, then distribute the current endpoint map to all roles and get their actual recipient acknowledgments. Setup/test endpoints are ephemeral; never reuse them as a future daily binding. A successful spawn receipt establishes accepted requested controls. Record independently observed runtime model/effort metadata separately if available; if absent say unavailable. Self-identification is not runtime evidence. Reject silent model/effort/fork substitutions; if exact controls are unavailable, preserve pending state and report the precise capability gap to Root.

Each complete seed must include: role/sole responsibilities, explicit date and Chicago timezone, canonical repository checkout and expected HEAD, current request scope and standing authorization, private plan/run-state/artifact references and fingerprints, METHOD authority, workbook-preservation rules, no spending/market/secret/publication actions, endpoint registration and stop/escalation route. No inherited history is assumed. Every role reads AGENTS.md, METHOD.md, docs/HANDOFF.md, docs/DATA_MAP.md and the relevant dated example. Before technical work, verify actual execution, checkout root/branch/HEAD/dirty state/remote; report any gap rather than mistaking a label or downloaded tree for a Git checkout.

| Role | Role-specific seed and first dispatch |
| --- | --- |
| Admin | Own lifecycle, schedule/source/cutoff receipts, private state and the date claim. Verify capability receipts; spawn/register the exact three remaining roles; assign the daily objective to Supervisor; reconcile pending sends/task state and receive the one daily report. No file or Sheets implementation. |
| Supervisor | Independently check source freshness, statistical cutoff/coverage and canonical method; inspect current code/data and run analysis/review evidence. Alone author completed bounded work orders with base revision, allowed writes, exact scope, validation and stop boundary; send through Bridge. After each checkpoint independently review before authoring further orders. Carry team decisions and final audit into player review. No implementation writes. |
| Codex | Sole script/file/Sheets writer. Read and fingerprint completed Supervisor orders received through Bridge, acknowledge endpoint/hash and execute only their bounded scope. Preserve unrelated work, use focused revisions, proportionate tests and read-back verification. Return checkpoint artifact with stage/results/limitations; do not infer approval from Bridge text. No extra agents. |
| Bridge | Transport completed Supervisor/Codex text or immutable reference envelopes only. No authoring, grammar edits, script execution for diagnosis, implementation, new scope or private-ID publication. Deliver to registered actual endpoint, preserve pending uncertainty, obtain actual recipient receipts, and return them to the author. |

Once a role becomes idle/completed, `collaboration.send_message` alone only queues text. Use `collaboration.followup_task` to deliver a reference envelope and activate that role, or use another independently verified wake mechanism. For a running recipient, send the envelope with `send_message` and await a receipt. A positively accepted queued message followed by an idle `followup_task` referencing its work-order ID/hash activates the already-delivered message; it is not an uncertain resend and must not duplicate the payload. Inspect actual role status when needed. Tool send acceptance alone is not proof that the recipient read or verified content.

## Exact artifact relay

Supervisor alone authors a work-order file; Codex authors checkpoint files. Use immutable UTF-8 files outside public Git. Canonical artifacts preserve entities (`&amp;`), Unicode, CRLF/LF and any trailing newline exactly. No normalization. The helper supports exclusive creation from already completed bytes and independent verification:

```bash
python relay_artifact.py create /PRIVATE/orders/ORDER_ID.txt --from-file /PRIVATE/completed-order.txt
python relay_artifact.py verify /PRIVATE/orders/ORDER_ID.txt --bytes BYTE_COUNT --sha256 SHA256
```

`create` exclusively creates with mode 0600 from the first byte and sets the completed file to 0400 before returning its fingerprint receipt. It refuses overwrite; a correction gets a new ID/file and supersedes the old one. These are privacy/read-only guards, not irreversible OS immutability or durable storage. Do not dispatch a reference until complete write/fingerprint success; a partial failed artifact stays undispatched for reconciliation. Helper success means byte verification, not recipient identity, scope approval, delivery or durable saving. Shared current-run filesystem references are valid only when the recipient can actually read them. For later recovery, save canonical bytes to a private durable location and record its actual saved identifier/receipt. Missing files, UTF-8 failure, count/hash mismatch or inaccessible capabilities pause dependent work; report the exact gap through Bridge without fabrication.

Bridge copies a short completed envelope containing work-order/checkpoint ID, actual source/target registered role IDs, actual artifact path/identifier, UTF-8 byte count and SHA256. Public examples use placeholders; real envelopes are private. Recipient verifies the target equals its real task endpoint, reads **all canonical bytes**, independently computes count/SHA256, reads the decoded text, and sends its own endpoint/fingerprint receipt before acting. Return checkpoints the same way to the actual Supervisor, including Supervisor's actual receipt. Record pending -> accepted -> recipient-verified separately. Preserve uncertain sends pending, reconcile known outcomes, and never blindly resend. An unresolved mismatch pauses work until Supervisor explicitly reconciles the exact recipient echo or supplies a new bounded artifact.

Transport history: the synthetic 178-byte test passed exactly. The initial 6035-byte implementation order was normalized by relay into 6037 bytes; the recipient detected it and paused, and Supervisor explicitly accepted the grammar change by addendum. **That original implementation-order transport was not byte-exact.** This is why reference artifacts and independent read receipts are required.

## Daily data, analysis and completion

Before writes, discover the **existing** native Sheet by exact title **BBB Basketball — 2026–27** and tabs **Method, Pick Review, Teams, Connections, Shooters, Matchups, Sources, Tracking Coverage**, as specified in DATA_MAP.md. Verify season and method source/revision/hash. Use the authorized discovery route before asking about ambiguity; never create a replacement workbook. Keep the returned workbook/tab IDs private. Read current headers, Method, Pick Review, actual cutoff and coverage; preserve date + game ID + player ID choices/notes and dated metadata. Reconcile approved policy changes before mirroring. A source commit or schedule fetch does not advance the workbook cutoff.

Supervisor orders a bounded refresh with explicit slate/cutoff and private paths; Codex verifies execution and actual authorized Sheets read/write capability. A connector label is insufficient. If missing, report the precise missing stage and preserve prepared outputs; do not claim an upload or invent a writer. When available, make bounded authorized writes to the existing workbook and read back changed ranges, cutoff, coverage, row counts and preserved picks. Uncertain writes require read-back reconciliation before retrying.

Use existing commands with explicit dates and outputs outside public Git (paths here are placeholders):

```bash
python bbb_triples.py --date YYYY-MM-DD --out /PRIVATE/run/core
python fetch_tracking.py --date YYYY-MM-DD --out /PRIVATE/run/tracking
python analyze_tracking.py --data-dir /PRIVATE/run/tracking
python tracking_sensitivity.py --data-dir /PRIVATE/run/tracking
python export_method.py --out /PRIVATE/run/method_update.json
```

The exporter requires private `BBB_SPREADSHEET_ID` and `BBB_METHOD_SHEET_ID` configuration and verified committed METHOD source; it generates a payload, not a Sheets write. Core/tracking `--offline` requires every exact saved request and records reuse. Analysis expects tracking `inputs.json` and wrapped `boxlogs.json`; sensitivity binds to the analysis hash. See REFRESH.md for validation and read-back details. Do not call a core screen completed tracking, availability, player selection or Sheets refresh.

Supervisor independently checks receipts, sources and limitations, then performs passes 1–4 in canonical order: volume/own shooting/pace, schedule-adjusted shot quality, three-point assist creation, OREB. Separate volume from quality, display absolute baselines beside percentiles, and carry Advance/Watchlist/Reject plus strongest contradictions and ranking reasons. No quotas or single-metric veto. Perform availability research before player analysis, using official reports and credible local evidence, estimated rotations/confidence and conditional alternatives. Then analyze players **one team at a time** and provide METHOD's complete final audit. Missing data remains explicit; rejected theses are not rescued by attractive players. No market/pricing/stakes or betting interaction.

Deliver one completed daily report to Admin with schedule and actual launch receipts, Git/METHOD revisions, source fetch/reuse times, results cutoff, each stage actually executed/verified, core and tracking coverage (paired/any-side/team-games/partial shots and matched possessions), pass decisions/audit, availability evidence, player ranges and limitations. Report partial/failed stages truthfully while continuing independent supported work. Do not require next-pass prompts. Close the date claim only when required stages and actual report delivery are verified; otherwise record the report and the remaining blocked stage for safe resume. Root handles publication and real scheduling separately.
