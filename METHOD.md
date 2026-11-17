# BBB Basketball Method

Canonical analysis policy. Version 2026-11-17. This file governs interpretation; the Google Sheet Method tab is a generated reading copy. Dated coverage and pick records remain workbook state, not policy.

Evaluate whether this offense can exploit what this defense concedes. The passes refine and test that hypothesis. They do not create a quota of selections or a veto from one percentile.

The `sheet-row` markers preserve the existing workbook layout. Edit the prose here, then export the mirror from the exact Git commit using `export_method.py`. Do not independently maintain another policy copy.

## Source
<!-- sheet-row: 7 -->

NBA team statistics, schedule, live play-by-play and final box scores.

## Priority
<!-- sheet-row: 9 -->

Read this repository's AGENTS.md, METHOD.md and current handoff before analysis. Run passes in order of importance: 1. Volume, shooting and pace. 2. Shot quality and schedule adjustment. 3. Three-point assist creation. 4. Rebounding. Complete availability review before 5. Player selection. Apply the qualification and audit rules in rows 51–53.

## Rebounding
<!-- sheet-row: 10 -->

Use offensive rebounding only to break close calls. Cap its influence at 2.5% of the overall matchup read. Volume, shooting, pace and shot quality drive the shortlist.

## Assists
<!-- sheet-row: 11 -->

Use three-point creation as a supporting layer with a provisional 5% influence. Assess passing-created threes, the opponent's conceded opportunities and the shooters who receive them. Apply this allowance once across team and player analysis.

## Pace
<!-- sheet-row: 12 -->

Use expected game possessions in Pass 1 to convert a per-100 three-point attempt rate to a per-game estimate. Apply pace once.

## Percentiles
<!-- sheet-row: 13 -->

League midranks: 100 × (average ascending rank − 1) / 29. All 30 eligible teams required.

## Ordering
<!-- sheet-row: 14 -->

The Matchups tab counts five non-pace components at or above 75, then breaks ties by weakest component and team. For big-slate Pass 1, rank the volume and pace read separately. This sorter generates research candidates only. Final selection must reflect all completed passes. A high initial rank does not guarantee advancement.

## Windows
<!-- sheet-row: 15 -->

Prior regular season, current season and last 10 current-season games shown separately.

## Overlap
<!-- sheet-row: 16 -->

Last 10 differs from season totals for teams with more than 10 games. The samples still overlap.

## Sample size
<!-- sheet-row: 17 -->

Fewer than 10 team games flagged thin. Research only until several weeks of current-season data.

## OREB link
<!-- sheet-row: 18 -->

Personal offensive rebound to first subsequent FGA before a stopping boundary. Reconstructed from ordered play-by-play; NBA tags audited separately.

## Second chance
<!-- sheet-row: 19 -->

Broader NBA-tagged second-chance 3PA remains separate from immediate personal OREB links.

## Missing data
<!-- sheet-row: 20 -->

Missing is blank, never zero. Failed games suppress affected team-window rates.

## Players
<!-- sheet-row: 22 -->

Shooter exports are observed counts, not projections. Minutes, roles and availability require separate review. Trace three-point opportunities to individual shooters through observed passing connections, shared creator minutes and the opponent's conceded shot types. Check who takes OREB-linked threes.

## Workflow
<!-- sheet-row: 23 -->

Prompt refresh basketball BBB; mark Pick Review checkboxes; prompt triples picks are marked; then request ranges.

## Refresh preservation
<!-- sheet-row: 24 -->

Keep the existing workbook ID in private configuration. Read the canonical Git METHOD.md, the live Method revision and Pick Review before refreshing. Preserve picks and review notes by date + game ID + player ID. Regenerate policy instructions from METHOD.md rather than overwriting them with hardcoded defaults. If the sheet and repository differ, reconcile the approved change before replacing either version.

## Refresh ownership
<!-- sheet-row: 25 -->

Refresh occurs on request. This sheet is a dated snapshot and does not update itself.

## Model scope
<!-- sheet-row: 26 -->

Market-blind. No sportsbook pricing, implied probabilities, stakes or order execution.

## Opponent 3P% allowed
<!-- sheet-row: 31 -->

Context only. Raw opponent 3P% and 3PM allowed never earn a first-pass perimeter boost by themselves.

## Perimeter shot quality
<!-- sheet-row: 32 -->

Trial metric: wide-open opponent 3PA (6+ ft) per 100 tracked possessions. Show open 3PA (4–6 ft) separately.

## Tracking & player fit
<!-- sheet-row: 33 -->

Use matched tracking games and possession counts. League percentiles require coverage for all 30 teams. In player review, check whether the conceded looks match the shooter’s usual threes.

## Tracking fallback
<!-- sheet-row: 34 -->

Exclude games with missing tracking or unmatched possessions. If a defense or its comparison offenses have incomplete coverage, label the estimate partial and show eligible games and possessions. Leave the adjusted grade blank if no matched comparison can be built.

## Big slate · 1. Volume, shooting and pace
<!-- sheet-row: 35 -->

Screen the full slate. Show team 3PA and opponent 3PA allowed per 100, with raw counts and league percentiles. Give credit for the offense’s own 3P%. Show its season and last-10 rates separately and read them alongside attempt volume. Apply expected game possessions once to estimate game-level attempts. Keep team 3PM descriptive and raw opponent 3P% allowed as context only. End the pass with Advance, Watchlist or Reject and explain the evidence for each decision.

## Big slate · 2. Shot quality
<!-- sheet-row: 36 -->

Run the schedule adjustment in rows 39–42 before advancing teams. Show tracked expected 3PM allowed, the opponent baseline and the difference per 100. Show expected make rate per attempt, actual minus expected, and open and wide-open attempt rates separately. Reassess each candidate as Advance, Watchlist or Reject. Later contradictory evidence must change the decision when it weakens the thesis. Apply the core qualification rule in row 51 before advancement.

## Big slate · 3. Assist creation
<!-- sheet-row: 37 -->

Use a three-point-only lens. Compare offense catch-and-shoot 3PA per 100 with opponent catch-and-shoot 3PA allowed when available. Show assisted 3PM per 100 and assisted share of made threes on both sides as supporting context. Use potential assists and drive-and-kick activity as creation context. Trace favorable matchups to likely shooter beneficiaries. Show raw figures, eligible sample and percentiles where supported.

## Big slate · 4. Rebounding
<!-- sheet-row: 38 -->

Check offense OREB%, opponent DREB weakness and how often a personal offensive board leads to a three. Give credit only when the matchup supports more second-chance threes than the offense usually generates. Use this as a tiebreaker, with 2.5% influence at most.

## Pass 2 · Expected threes
<!-- sheet-row: 39 -->

For each defense–offense matchup, multiply tracked 3PA in each defender-distance bucket by that bucket’s league make rate. Sum the four buckets to get expected makes.

## Pass 2 · Opponent baseline
<!-- sheet-row: 40 -->

For each offense faced, calculate expected 3PM per 100 from its tracked games against all other defenses. Exclude every game against the defense being rated. Use the same bucket weights and matched possession counts.

## Pass 2 · Schedule adjustment
<!-- sheet-row: 41 -->

Subtract each offense’s baseline from what the defense allowed per 100 against it, then average the differences weighted by possessions against each offense. Positive means the defense allowed more expected threes than its opponents usually generated.

## Pass 2 · Report coverage
<!-- sheet-row: 42 -->

Use only data available before tip. Show eligible games and possessions, flag gaps, and label early-season estimates as unshrunk when no shrinkage is applied. When coverage is incomplete, report supported matchup comparisons and omit league percentiles.

## Big slate · 5. Player selection
<!-- sheet-row: 43 -->

After the four team passes, shortlist up to three qualifying team-level theses unless the user requests a different maximum, and complete the availability check in rows 46–50 before player review. Top N means up to N qualifying theses; zero survivors is valid. Do not fill vacancies automatically or promote another candidate without evaluating its merits. Provide the final audit required in row 53. Analyze one team at a time, carrying forward each pass's findings. Attractive individual players do not retroactively qualify a rejected team thesis. Player counts are ceilings, not quotas. Use expected rotations to assess role, minutes, three-point volume and makes ranges, including non-stars and bench players. Identify assisted-three dependence, observed creator-to-shooter connections, likely shared minutes and fit with the opponent's conceded shot types. Carry the OREB findings into shooter selection.

## Pass 3 · Evidence and overlap
<!-- sheet-row: 44 -->

Assisted makes depend on shooting accuracy. Potential assists cover both twos and threes. Use both as context alongside supported three-point opportunity measures. Assign passers only from observed assists or tracking. Label missing or partial tracking and use available evidence. Count catch-and-shoot volume and shot quality once across Passes 2 and 3.

## Supporting weights
<!-- sheet-row: 45 -->

Provisional judgment weights are 5% for assist creation and at most 2.5% for OREB. The core volume, shooting, pace and shot-quality read carries 92.5%. Apply the supporting allowances once across team and player selection. Correlation coefficients inform review of the method. Validate predictive value on future games before treating the weights as fitted coefficients. Assist creation and OREB refine an established core thesis within these weights and cannot independently rescue a failed core case. Explain how pace affects expected opportunities and count it once.

## Availability · Timing and scope
<!-- sheet-row: 46 -->

Between the four team passes and player selection, review shortlisted offenses, their opponents and any reserve candidate that independently qualifies. Establish whether tonight's personnel support each thesis. Carry the expected rotations and material alternatives into player analysis. A reserve is optional.

## Availability · Personnel and sample
<!-- sheet-row: 47 -->

Check offensive creators, shooters, likely starters, returning players, minutes restrictions and rotation changes. Check relevant opposing perimeter defenders and rebounders and their replacements. Establish how much of the season and last-10 samples already reflects each absence. Adjust for tonight's differences from the sample.

## Availability · Sources and uncertainty
<!-- sheet-row: 48 -->

Start with the latest official NBA injury report, then team announcements and credible beat reporting for starters, restrictions and likely rotations. Give the report time and cite the evidence behind material assumptions. Make an evidence-based rotation estimate, state confidence and the material alternative, and proceed with that estimate without making confirmed starters a prerequisite. Distinguish confirmed status from expected role. Use conditional player ranges when an unresolved status materially affects minutes, attempts or creator overlap.

## Availability · Required output
<!-- sheet-row: 49 -->

Before player review, provide a compact table with relevant absence or return, expected replacement or rotation change, evidence from comparable rotations, effect on the team thesis and confidence. Identify which unresolved statuses materially affect the candidates.

## Availability · Applying changes
<!-- sheet-row: 50 -->

Keep team-level adjustments proportional to the personnel change. A primary creator's absence can materially change how the offense generates threes and justify revisiting its thesis. Apply substantial role changes directly to individual minutes and attempt ranges. Estimate redistributed opportunities from comparable games, roles and shared minutes while allowing for changes in the whole offense.

## Selection · Core qualification
<!-- sheet-row: 51 -->

State the offense's strength and the opponent's specific conceded opportunities. Evaluate volume and shot quality separately: a defense may limit total threes while conceding favorable looks. Show absolute rates and relevant baselines alongside percentiles. Explain the combined effect of favorable and unfavorable evidence before advancing or rejecting a candidate. No single metric automatically decides qualification. Favorable opportunities must retain a credible path to made threes. Apply the existing own-shooting, schedule-adjustment and coverage rules.

## Selection · Advancement after each pass
<!-- sheet-row: 52 -->

After every team pass, mark candidates Advance, Watchlist or Reject and explain what strengthened or weakened each thesis. Carry the same matchup assessment forward. Later contradictory evidence must change the decision when warranted. Explain each ranking revision using new evidence, a corrected calculation or a corrected interpretation. Only qualifying Advance candidates enter the final shortlist; zero survivors is a complete result.

## Selection · Required final audit
<!-- sheet-row: 53 -->

Before the player pass, provide a compact table: Candidate | Offensive strength | Opponent vulnerability | Strongest contradiction | Decision and reason. Separate volume and shot-quality evidence and explain the combined effect, including absolute magnitude and baseline comparisons. Explain why an unresolved contradiction still allows advancement or requires Watchlist or Reject. List rejected candidates without filling their places automatically. Carry this assessment into player review. A high first-pass rank does not establish final qualification.

