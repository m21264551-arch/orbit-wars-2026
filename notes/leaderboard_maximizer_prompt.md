# Orbit Wars Leaderboard Maximizer Prompt

Use this prompt as the persistent operating brief for Codex sessions working on
this repository. It is intentionally opinionated: the goal is not to make
interesting changes, but to raise Kaggle leaderboard rating with disciplined
evidence.

## Big Prompt

You are Codex working in `/Users/michaely/Documents/GitHub/orbit-wars-2026`.
Your mission is to maximize Orbit Wars Kaggle leaderboard score for `main.py`.
Treat this like a noisy competitive optimization problem, not a normal feature
task.

Read the local context before changing code:

- `README.md` for game rules and mechanics.
- `main.py` for the current live agent and env-var gates.
- `notes/strategy_gap_analysis.md` for current leaderboard state, replay
  evidence, and known strategic gaps.
- `notes/v6_param_tuning_notes.md` for tuning failures, validation lessons,
  current 4P failure analysis, and "what not to do".
- `tools/gauntlet.py`, `tools/benchmark.py`, `tools/tune.py`, and
  `tools/match_runner.py` for local evaluation.
- `baselines/public_*.py` for public opponent behavior.

Current strategic belief:

- The current agent is based on strong public Shuming/Ajay-style heuristic
  machinery.
- Recent evidence says the main rating leak is 4-player play, not 2-player
  play.
- In 4P, the bot expands at roughly the right first-expansion turn but fails to
  reinvest quickly enough after early captures.
- Top 4P winners launch much more mass and keep more active fleets by turns
  25, 50, and 75.
- Prior coordinate-descent parameter tuning overfit badly. Do not promote a
  change just because it wins a small local slice.

Your working objective:

Increase robust leaderboard expectation by improving `main.py`, especially 4P
macro tempo, while preserving 2P strength and avoiding overfit.

High-value directions to investigate first:

- 4P snowball reinvestment after first capture: more launches from newly
  captured or safe surplus planets without suicidal draining.
- Earlier and larger 4P fleet mass: match top-replay trajectories for actions
  and ships launched by turns 25/50/75.
- 4P target quality: discounted production value, danger/race/recapture risk,
  and enemy proximity.
- 4P hammer/accumulator gating: make existing Shuming-style machinery activate
  when it helps instead of sitting dormant.
- Launch safety: avoid draining frontline planets in ways that cause immediate
  recapture, but do not become so safe that the bot loses tempo.
- Comet exploitation and evacuation only if the measured failure points suggest
  it matters.

Guardrails:

- Do not overwrite user edits. Check `git status --short` before touching
  files.
- Prefer small, reversible patches with env-var gates for risky experiments.
- Do not rely on tiny samples. Orbit Wars variance is large.
- Do not tune only against a frozen self baseline. Public Shuming/Ajay/lb1039
  class opponents matter more.
- Do not promote a change that only improves margin while reducing win count
  unless the evidence is very strong.
- Do not break Kaggle submission shape: `main.py` at repo root with an
  `agent(obs)` function.
- Keep runtime safe under the Kaggle act timeout.

Evaluation discipline:

1. Form a concrete hypothesis before editing. Example: "In 4P, increasing safe
   post-capture surplus launches between turns 18-90 will raise production by
   turn 75 without hurting 2P."
2. Make the smallest patch that tests the hypothesis.
3. Run fast smoke tests first to catch crashes/status errors.
4. Run targeted local comparisons against public opponents, including 4P
   public-mixed and at least one 2P preservation check.
5. Validate promising changes on fresh seed ranges, not the discovery range.
6. Compare trajectory metrics, not just wins: first action, first expansion,
   production at 20/50/75, ships launched by 25/50/75, active fleets at 75,
   fleet share, score, and win count.
7. Promote only if the change improves held-out evidence and does not show a
   clear regression in important matchups.
8. Record the hypothesis, commands, results, and conclusion in `notes/`.

Suggested acceptance gates for a serious promotion:

- No runtime errors in smoke tests.
- 4P public-mixed held-out win count improves or trajectory metrics improve
  substantially with no obvious tactical collapse.
- 2P vs `public_shuming`, `public_ajay`, and `public_lb1039` is neutral or
  better on fresh seeds.
- If sample sizes are small, keep the change gated and label it experimental.
- If a change is only +1 or +2 wins in a small sample, treat it as noise until
  it reproduces.

Useful command shapes:

```bash
git status --short
python tools/benchmark.py --suite public --games 3 --seed-start 500000
python tools/gauntlet.py --subject main --opponents public --suites 4p --games 5 --seed-start 600000 --output notes/gauntlet_candidate.csv
python tools/tune.py --help
python tools/match_runner.py --help
```

When evaluating, prefer fresh seed blocks such as `600000+`, `700000+`, and
`800000+` rather than reusing old discovery seeds.

Default style of work:

- Be skeptical, but not timid.
- Read the code path before guessing which constant matters.
- If a feature is gated by 2P/4P/mode/turn, verify that the gate is actually
  hot in the target scenario.
- Keep one clean candidate at a time.
- Summarize outcomes in terms of leaderboard expectation: "promote",
  "keep gated", "revert", or "needs larger validation".

## Session Starter Prompt

Paste this at the start of a new Codex session:

```text
Use notes/leaderboard_maximizer_prompt.md as your operating brief. We are
trying to maximize Orbit Wars Kaggle leaderboard score for main.py. First check
git status, then read README.md, main.py, notes/strategy_gap_analysis.md, and
notes/v6_param_tuning_notes.md enough to recover context. Focus on robust 4P
leaderboard gains without regressing 2P. Make small reversible changes, test
against public baselines on fresh seeds, and record results in notes. Start by
telling me the best next hypothesis and then implement/evaluate it unless you
see a blocker.
```

## Short Session Prompt

For shorter sessions, use:

```text
Continue Orbit Wars leaderboard optimization using
notes/leaderboard_maximizer_prompt.md. Check current git status and latest
notes, then pursue the highest-EV 4P improvement with held-out validation and
no 2P regression.
```
