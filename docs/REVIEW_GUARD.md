# Evidence guard and adversarial acceptance

Use this contract with LEAN_DAILY_WORKFLOW.md. It adds evidence and review requirements; METHOD.md and the 92.5/5/max2.5 provisional judgment hierarchy remain unchanged. No new agents, fitted scoring model or data service are needed.

## Run sequence

1. Worker appends the pass ledger after each pass, before proceeding. Do not manufacture a complete ledger retrospectively from a frozen shortlist. Decision changes are optional; actual reassessment is mandatory.
2. Worker builds private `review.json` with the declared slate directions, finalists, player fit and range evidence below. Use scripts to calculate participation comparisons from the saved box evidence. Run the draft guard.
3. The one Auditor independently checks the source figures AND reasoning, argues the strongest rejection case for each finalist, and argues the strongest promotion case for one Watchlist alternative if any exists. Supply evidence and a response in the review manifest. Auditing is not permission to fill a shortlist.
4. Run the final guard after the audit. Within the existing single correction/confirmation allowance, repair material deficiencies or remove unsupported claims/candidates. If a gate remains failed, deliver the supported report explicitly as draft/qualified/incomplete with the failed checks. Never label it fully approved. Report delivery must not wait for another agent chain or documentation polish.

```bash
python review_guard.py --ledger /PRIVATE/pass_ledger.json --review /PRIVATE/review.json --root /PRIVATE --phase draft
python review_guard.py --ledger /PRIVATE/pass_ledger.json --review /PRIVATE/review.json --root /PRIVATE --phase final
```

Both commands are read-only. Exit 0 means structural checks passed; exit 2 returns actionable issue codes. This is not proof of source truth, calibrated ranges, independent authorship, prose quality or how much attention an agent gave a pass. Auditor must open the hashed references, verify identities/windows/denominators, and compare actual report claims to them. Paraphrasing boilerplate does not satisfy the contract.

## Ledger fields

Keep the existing `stage` (1–4), `candidate` (`OFF -> DEF`), `cutoff`, `execution`, `decision`, `reason`, `figures`, `offense_strength` and `strongest_contradiction`. Add `defensive_concession` and `source_refs`. Each source reference is `{"path":"relative/file.json","sha256":"actual file SHA256"}` inside the evidence root. Raw and derived sources must be distinguishable in the report/evidence index; a matched hash is not factual validation.

Use `completed`, `partial` or `blocked`; partial/blocked rows require `missing` describing both the gap and consequence. A core already rejected in a previous pass can use `not_applicable` and a specific skip reason, staying Reject. An Advance or Watchlist candidate cannot silently skip supporting passes.

For every Advance/Watchlist row in passes 3 and 4, include:

- `comparison`: numeric `offense_baseline`, numeric `defense_concession`, `units`, `window`, and `incremental_effect` explaining magnitude and limitations. Keep assist/rebound source counts, eligible samples and separate immediate/tagged definitions in `figures`.
- `decision_review`: `previous`, `current`, `effect` (`strengthens`, `weakens`, `neutral`, `unresolved`) and candidate-specific `rationale`. An unchanged decision can be correct; copying the old status is not a review.

Exact repeated reasoning among live candidates is rejected mechanically. The Auditor must also reject vacuous unique wording, mismatched units/samples and invented incremental opportunities. No mechanical promotion or demotion is introduced.

## Review manifest

Required top-level fields:

- `slate_date`, `cutoff`, `weights: {"core":92.5,"creation":5,"oreb_max":2.5}`.
- `expected_candidates`: unique official slate directions. Auditor checks them against the fresh official schedule, not the ledger alone.
- `final_decisions`: every direction's post-availability Advance/Watchlist/Reject. `finalists`: zero to three selected Advance directions. `players`: selected player/scenario entries; no player can rescue an unqualified team.
- `exploited_dimensions`: each finalist's explicitly claimed defensive dimensions, e.g. `{"OFF -> DEF":["defender_distance","catch_and_shoot"]}`. Avoid claiming dimensions that were not actually analyzed.
- Final phase: `countercases` mapping each finalist to `reject_case`, `response`, `source_refs`; `watchlist_challenge` with `candidate`, `promotion_case`, `response`, `source_refs` when Watchlist candidates exist. These are the Auditor's substantive challenges, not a Worker-written ceremonial approval.
- Final phase `audit`: separate `data` and `reasoning` verdicts (`accepted` required for approved output), `publication` and `visual` (`verified`, `not_checked`, `blocked`), and hashed `source_refs` to the actual audit record. Worker readback alone must not be described as independent publication review. A failed/inaccessible visual check does not invalidate verified numeric data, but stays disclosed.

## Shooter fit

Every selected player/scenario has `candidate`, integer `player_id`, and `fits` covering each dimension in that candidate's `exploited_dimensions`.

- `status: verified` requires `coverage: matched`, distinct hashed offensive and defensive raw source files, numeric `offense_value`/`defense_value`, `units`, `window` and actual unique matched `game_ids`. Source parameters/headers must actually contain the declared dimension. Auditor must check player/team identity, dates and game coverage; the code cannot establish those facts from a header alone.
- `status: partial` or `unverified` requires `boost_claimed: false` and an explicit `limitation`, visible in the report. Retain useful partial counts as context, without advertising a measured fit advantage. Missing fit is not a one-metric veto; justify any surviving core thesis independently and lower confidence appropriately.

Catch-and-shoot counts do not establish defender distance or corner/location fit. A query with `GeneralRange=Catch and Shoot` and blank distance/location parameters cannot verify those dimensions. An aggregate GP match alone does not prove a matched opportunity/possession join. Keep the claim provisional unless actual coverage supports it.

## Rotation and range evidence

Each player/scenario entry includes `rotation_comparables`, a list with:

- `source_ref` to the hashed full saved `player_evidence.json`, `team`, optional integer `present` and `absent` condition-player IDs.
- `summary` equal to `review_guard.comparable(...)` on that evidence and cutoff. It returns matching team games, actual target appearances, unobserved target games, IDs, minutes/attempt means and a confounding caveat. Compute joint conditions (e.g. both a missing big and returning wing) rather than a misleading single absence split.
- `sample_caveat` and `chosen_adjustment`: disclose the actual n, participation-versus-availability limitations, other roster changes, and why proposed minutes/attempts differ from observed means. Tiny groups are not robust causal estimates. Never divide target totals by team GP or silently turn unobserved targets into zero/DNPs.

The helper accepts the existing saved rotation schema, requires known integer IDs, rejects duplicate games/players, and excludes games after cutoff. Example API (substitute actual IDs from the source):

```python
from review_guard import load, comparable
data = load('/PRIVATE/player_evidence.json')
summary = comparable(data, team='TEAM', player_id=123, cutoff='YYYY-MM-DD', present=[456], absent=[789])
```

Also declare `conversion_baseline`: actual `made`, `attempts`, `window`, `selection_reason`, hashed `source_refs`. Explain whether a broader sample or other justified baseline tempers recent hot shooting. Do not invent a fitted shrinkage coefficient. Provide numeric `[low,high]` `minutes_band`, `attempts_band`, `conservative_makes_band`, `stretch_makes_band`, `range_label: judgment_band`, and `range_reason` connecting minutes, shot frequency and conversion to those bands. Use separate entries for material role scenarios. Label judgment bands honestly; they are not calibrated hit probabilities or guaranteed lower bounds.

## Regression evidence

Tests exercise the observed shortcuts: generic supporting-pass carry-forward, catch-and-shoot mislabelled as distance fit, missing comparable samples, wrong appearance denominators, unsupported boosts, absent adversarial cases and arithmetic approval presented as full review. They also allow genuine unchanged decisions, honest unverified fit, rejected-core skips, zero finalists, and draft creation before the Auditor has accepted anything. No personal workbook or pick data belongs in test fixtures or public Git.
