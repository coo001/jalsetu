# JalSetu: next-action packets for contaminated drinking-water samples

JalSetu is a decision-support tool for district water-quality officers in India. It reads real government
(WQMIS) records of contaminated drinking-water samples and builds a **next-action packet** for each one:

1. **Verdict** against pinned BIS IS 10500 limits (value, limit, ratio, limit basis).
2. **Candidate re-test labs** from the state's WQMIS lab list (L10), with the reason each lab is listed.
3. **Officer actions and interim household advice**, taken *only* from a pinned table of official sources
   (JJM handbook/framework, BIS, WHO). Every line shows its source id and section.
4. **A re-test request letter draft**, checked by `fact_guard` against the record.

If a record is ambiguous (missing value, unit mismatch, limit mismatch, duplicate id, bad date, ...) the
packet stops with `needs_review` and the reasons, and produces **no advice and no letter**.

All decisions are deterministic code. An LLM is optional and may only reword the letter; the app works fully
without any API key.

Live demo: https://jalsetu-5ftx.onrender.com (Render free tier; the first request after idle can take about a minute)  
Source: https://github.com/coo001/jalsetu

## Impact

No field users or remediation outcomes yet (solo builder, no local partner). The numbers below are reproducible checks on real government records, not impact.

### Wording limits

- JalSetu produces next-action packets and letter drafts; it does not deliver them or fix contamination.
- E1 reproduces the government's contaminated list (283 AP + 592 BR records); it is not independent accuracy and
  not a count of people affected.
- Labs are "candidate labs listed in L10", not recommended, available or accredited labs.
- Page counters are page-visit counts, not users or impact.
- AgentFoundry was used to open the project and run tests/evals; most code was written outside it.

## Quick start

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn app.main:app
# or
make test   # pytest
make eval   # writes eval/results/<date>.json and latest.json, eval/public_sample_30.csv, eval/public_sample_30_BR.csv
make run    # uvicorn on port 8080
docker build -t jalsetu . && docker run -p 8080:8080 jalsetu
```

Pages: `/` overview (per-state counts), `/queue` sample queue (state filter, default All), `/sample/{record_id}` packet (printable), `/sources`, `/eval`.
JSON: `/api/samples`, `/api/packet/{sample_id or record_id}`, `/api/eval/latest`, `/api/sources`, `/api/overview`.

Optional: set `GEMINI_API_KEY` to let `gemini-2.0-flash` reword the letter on the sample page. The reworded
letter is used only if `fact_guard` passes; any error, timeout or guard failure falls back to the template.
Tests never call the network.

## Deploy (Render free)

`render.yaml` is a Render Blueprint: one free web service `jalsetu` (Docker, region singapore, health check `/healthz`,
auto-deploy on push). No paid resources.

1. Push this repo to GitHub.
2. In Render: **New → Blueprint**, select the repo; Render reads `render.yaml`.
3. Optionally enter `GEMINI_API_KEY` when prompted (`sync: false`, so it is never stored in the repo). Leave it empty to
   use the template letter only.
4. Open `https://<service>.onrender.com/healthz` and expect `{"ok": true}`. Free instances sleep when idle; the first
   request after sleep is slow.

## Data provenance

Snapshot `data/snapshots/2026-11-09/` from public WQMIS pages. Andhra Pradesh files were retrieved
`2026-11-09T01:53:38Z`; Bihar arsenic files `2026-11-09T06:35:29Z` (per-file `retrieved_utc` in the manifest).
`manifest.json` records the sha256, row count and retrieval time of every file; the app and `make eval` refuse to run if a
hash differs (`jalsetu/snapshot.py`, tested in `tests/test_snapshot.py`).

| File | Rows | Source |
|---|---|---|
| `wq6_AP_2024-2025_samples.csv` | 283 | WQ6 contaminant-wise report, Andhra Pradesh, FY 2024-25 (Fluoride 224, Nitrate 52, E. coli 7; Total arsenic 0) — https://ejalshakti.gov.in/WQMIS/Report/Contaminantwise |
| `wq6_states_2024-2025.csv`, `wq6_states_2025-2026.csv` | 34 each | WQ6 state summary (villages with ≥1 contaminated sample, by parameter) |
| `wq_labs_AP_L10.csv` | 138 | L10 lab/parameter list, AP — https://ejalshakti.gov.in/WQMIS/Main/lab_parameterlist |
| `wq6_BR_2024-2025_arsenic_samples.csv` | 592 | WQ6 contaminant-wise report, Bihar (WQMIS state id 5), FY 2024-25, Total arsenic only; 178 villages in Bhagalpur 332, Begusarai 183, Khagaria 77 records. Collected by `collector/legacy/collect_br_arsenic.py` |
| `wq_labs_BR_L10.csv` | 123 | L10 lab/parameter list, Bihar (routes the BR records) |
| `probe_log.json`, `br_arsenic_log.json` | – | collection logs (BR: 178 villages, 0 failed, 626.6 s) |

Each record carries `state` (AP / BR) from its file, and is routed only to that state's L10 labs. Record ids stay
`<sample_id>-<param>`; AP and BR sample ids do not overlap (checked in `tests/test_snapshot.py`).

Collector: `python -m collector.wqmis --date YYYY-MM-DD` (`collector/wqmis.py`, refactored from
`collector/legacy/`). It writes a new dated snapshot directory plus manifest, refuses to overwrite an existing
snapshot, retries with exponential backoff and a timeout, and appends failures to `collector/runs.jsonl`.

## Pinned sources

`jalsetu/guidance/sources.json` and `jalsetu/guidance/advice_table.json`. The code outputs only these strings.

| ID | Edition | sha256 (first 16) |
|---|---|---|
| BIS-10500 | IS 10500:2012 Drinking Water — Specification (Second Revision), BIS, May 2012 ([pdf](https://cpcb.nic.in/wqm/BIS_Drinking_Water_Specification.pdf); [amendment copy](https://www.consumerhelpline.gov.in/bis/IS10500-2012.pdf), Amendment No. 2, Sep 2018, does not change F, NO3, As, E. coli rows; [consolidated copy incl. Amendments 1–4](https://www.civilapps.in/files/Codes/Materials/General/IS-10500-2012-2023-Water%20Quality.pdf), third-party host of BIS file, sha256_16 `54348d5f9036b6d1`) | 9b8999c29ce264aa |
| WHO-GDWQ | WHO Guidelines for drinking-water quality, 4th ed. incl. 1st and 2nd addenda, 2022 (ISBN 9789240045064) | a0ac96fa5eac13e4 |
| WHO-BOIL | WHO Technical brief: Boil water, WHO/FWC/WSH/15.02, 2015 | 136d2e2bc676c981 |
| WHO-AS | WHO fact sheet: Arsenic (web page, accessed 2026-11-09) | web page |
| JJM-HB | Concise Handbook for Monitoring Water Quality of Piped Drinking Water Supply to Rural Households, DDWS / NJJM (no edition printed; content refers to 2024) | 19da7f395364ee6d |
| JJM-FW | Drinking Water Quality Monitoring & Surveillance Framework, NJJM (no edition printed; latest date in text Oct 2022) | 27356d402f6a3ae4 |
| PIB-2022 | PIB, Ministry of Jal Shakti, "Monitoring of Contamination of Ground Water", 21 Jul 2022 | web page |

Limits: fluoride 1.0/1.5 mg/l; nitrate 45/45 mg/l (no relaxation); arsenic 0.01 mg/l / No relaxation (IS 10500:2012
Amendment No.1, 2015); E. coli 0 CFU/100 ml. Chemical exceeds if value > permissible; E. coli exceeds if count > 0.

## Evaluation (measured, run 2026-11-09, `make eval`)

Full output: `eval/results/2026-11-09.json`. Reproducibility and safety checks only.
`latest.json`'s `git_commit` is the code commit the eval ran on; the results are committed in the next commit.

| ID | Check | Target | Measured |
|---|---|---|---|
| E1 | Government verdict reproduction (reproduction, not independent accuracy) | all numeric records exceed | 283/283 |
| E2a | Candidate lab slots whose L10 list lacks the parameter | 0 | 0 of 1,415 |
| E2b | Ready packets with a same-district candidate | report | 251 with / 32 without |
| E2c | Synthetic arsenic record on AP L10 | ready, 3 labs | ready, 3 labs |
| E2d | Synthetic parameter with zero labs | no_candidate_lab, no letter | no_candidate_lab, no letter |
| E2e | Lab order stable under input shuffles (3 per packet) | 0 unstable | 0 / 283 |
| E2f | Sample lab names not in L10 (before → after whitespace normalization) | report | 3/17 names (19 records) → 0/17 |
| E3 | Error injection, 10 records × 10 reason types (seed 20261109) | 10/10 each | 10/10 for every type (100/100) |
| E3.FP | False positives on the 283 original records | 0 | 0 |
| E4a | Template letters passing fact_guard | 283/283 | 283/283 |
| E4b | Injected wrong numbers / ids / labs / villages / dates rejected | 45/45 | 45/45 (9 kinds × 5) |
| E5 | Boundary / unit tests (`tests/test_boundaries.py`) | all pass | 28 passed, 0 failed |
| E6a | Advice lines with an existing source id (and verbatim from table) | 1,788/1,788 | 1,788/1,788 |
| E6b | needs_review packets with any advice or letter | 0 | 0 of 100 |
| E6c | "boil" text in chemical packets (except nitrate H_N2) | 0 | 0 |
| E7 | Public sample: first 30 records by sha256(sample_id) | 30 rows | 30 rows, all ready (`eval/public_sample_30.csv`) |

Bihar, 592 real Total arsenic records (same checks, keys with suffix `_BR`):

| ID | Check | Target | Measured |
|---|---|---|---|
| E1_BR | Government verdict reproduction (reproduction, not independent accuracy) | all numeric records exceed | 592/592 |
| E2a_BR | Candidate lab slots whose BR L10 list lacks arsenic | 0 | 0 of 2,960 |
| E2b_BR | Ready packets with a same-district candidate | report | 592 with / 0 without |
| E2e_BR | Lab order stable under input shuffles (3 per packet) | 0 unstable | 0 / 592 |
| E2f_BR | Sample lab names not in BR L10 | report | 0/6 names |
| E3.FP_BR | False positives on the 592 original records | 0 | 0 |
| E4a_BR | Template letters passing fact_guard | 592/592 | 592/592 |
| E6a_BR | Advice lines with an existing source id (and verbatim from table) | 4,144/4,144 | 4,144/4,144 |
| E6b_BR / E6c_BR | needs_review with advice / "boil" in arsenic packets | 0 / 0 | 0 of 0 / 0 |
| VALUE_EXTREME_BR | Records with value ≥ 100 × permissible (warning only) | report | 2 (228.000 and 1.880 mg/l) |
| E7_BR | Public sample: first 30 BR records by sha256(sample_id) | 30 rows | 30 rows, all ready (`eval/public_sample_30_BR.csv`) |

Notes on what these numbers mean:
- E1 only shows the code agrees with the government listing; every record in the input was already listed as
  contaminated, so it is not an accuracy measure.
- E3/E4 mutations are written by the same author as the validator and guard, so they test known failure modes,
  not unknown ones.
- All 123 labs in the Bihar L10 list report arsenic testing, so E2a_BR/E2b_BR are easy targets; they show the routing
  uses the BR list, not that Bihar lab capacity was checked.
- VALUE_EXTREME: a chemical value ≥ 100 × permissible adds a warning (it does not stop the packet; the verdict still
  says it exceeds). The UI shows "Very high value: check the unit entry with the testing lab. Ratio not verified." next
  to the ratio, and the letter adds "Please confirm the reported value and unit." (fact_guard requires that line when the
  warning is present). The 228.000 mg/l record is almost certainly a unit entry error.
- E2b: 32 packets (districts ALLURI SITHARAMA RAJU, SRI SATHYA SAI, Y.S.R.) have no lab whose name or address
  contains the WQMIS district spelling (e.g. L10 spells "Sri Satya Sai", WQ6 spells "SRI SATHYA SAI"); no fuzzy
  matching is done.

### Same-author second-implementation check of the public samples
`python eval/independent_check.py AP` and `... BR` re-derive selection, verdict, ratio, lab capability, same-district flag and advice ids for `eval/public_sample_30.csv` and `eval/public_sample_30_BR.csv` from the raw CSVs without importing `jalsetu`. Result 2026-11-09: AP 300/300 checks, BR 300/300 checks, 0 mismatching rows (`eval/results/independent_check_30*.json`). This is a same-author second implementation (not independent verification), and not an external or field validation. Five AP rows were also checked by hand (value ÷ limit, lab parameter list, district match): no discrepancy.

### AI-assisted re-comparison against live WQMIS (10 records)
`python eval/recheck_live.py` takes the first 5 AP and the first 5 BR records of the public samples, re-fetches each record's village from WQMIS, and compares value, limits (against the stored row and against the pinned IS 10500 table values), lab and test date. Result (`eval/results/recheck_live_10.json`, run 2026-11-10T01:37:00Z): 10 records compared, 0 mismatching records. This is AI-assisted, not a human check; it uses the same author/tooling as the collector; it covers 10 of the 60 public-sample records (30 per state sample), out of 875 stored records (283 AP + 592 BR).

## Design choices made without asking

- **Duplicate rule is per (sample_id, parameter).** 7 sample ids appear twice in the AP data, each time once for
  Fluoride and once for Nitrate (same sample, two contaminants). These are not flagged. Record ids in the UI are
  `<sample_id>-<param>`; `/api/packet/<sample_id>` returns 409 with both options when ambiguous.
- `TEST_DATE_INVALID` also fires when the test date is after the snapshot date.
- `no_candidate_lab` packets show no advice either (advice is built only for `ready`, as specified).
- The lab that did the original test is not excluded from candidates; it is marked "this is the lab that did the
  original test". In the AP data it is the top candidate in 98 of 283 packets.
- In AP L10 only three WTP in-house labs list Total Arsenic; the State Level lab does not. An AP arsenic record
  would be routed to those three (synthetic test E2c). Bihar arsenic records are routed to Bihar L10 labs only.
- Digits inside verbatim place names (e.g. village "Rani 3", GP "Samasa-1" in Bihar) are allowed by `fact_guard`, the
  same way digits in the source text are.
- `fact_guard` compares numbers after float normalization (2.000 = 2); it allows only the record's value,
  acceptable and permissible limits and ratio, plus digits inside fixed template phrases (IS 10500:2012, WQMIS
  L10, JJM-HB 2.6, CFU/100 ml) and inside verbatim record text (source text, lab name/address, limit ref).
  A letter that fails the guard is never shown; the packet becomes `needs_review`.
- `collector/legacy/` keeps the original probe scripts for provenance; they are not used.

## Limitations

- **No distance.** WQ6 sample records have no coordinates, so labs are not ranked by distance; same-district is a
  name/address text match only.
- **L10 capability only.** A lab is a candidate because L10 says it tests the parameter. Availability, current
  accreditation, cost, transport and turnaround are not checked (stated on every packet).
- **WQ2 remedial-action records are not collectable** from the public pages, so the tool cannot see whether any
  action was already taken.
- **Arsenic limit basis is third-party copies only.** The original 2012 table prints 0.05 mg/l permissible;
  Amendment No.1 (June 2015) substitutes "No relaxation" for 0.05 in Table 3 (x), so 0.01 mg/l is the permissible
  limit. Limit basis = a third-party consolidated BIS copy "Incorporating Amendments 1 (2015), 2 (2018), 3&4(2021)"
  (read 2026-11-09; sha256_16 `54348d5f9036b6d1`; F, NO3 and E. coli rows unchanged) and a scan of the
  Amendment No.1 sheet inside third-party course slides (OCR). The official BIS portal text was not obtained; this is
  not a confirmation from the official BIS portal, and a human has not re-read it against official text. Records still carrying 0.05 go to `needs_review` (LIMIT_MISMATCH). There are no arsenic records in
  the AP 2024-25 snapshot. Real arsenic records come from Bihar (592, all carrying WQMIS's own 0.01/0.01 "No relaxation"
  limits, so none hit LIMIT_MISMATCH); the synthetic AP arsenic tests are kept.
- **Deployment counters are not impact.** `/api/stats` and the Evaluation page show anonymous in-memory page
  counters since the last restart (bots and `/healthz` excluded, no IP/UA/cookies/query/sample ids stored; snapshot
  logged to stdout every 50 events and on shutdown; `JALSETU_DISABLE_USAGE=1` turns it off). Not users, not
  outcomes, not impact.
- **JJM documents have no printed edition**; they are pinned by URL and sha256 prefix.
- Sample-level data loaded: Andhra Pradesh FY 2024-25 (all parameters) and Bihar FY 2024-25 (Total arsenic only).
- Advice is in English only.

## How AgentFoundry was used

Stated plainly so judges can weigh it:

- Most of the code in this repo was written with Claude Code CLI outside AgentFoundry.
- The project was opened in the AgentFoundry 0.1.80 desktop IDE (macOS, signed in), and the test suite and the evaluation harness were run from the AgentFoundry terminal on 2026-11-09 and 2026-11-10: `make test` (115 passed) and `make eval` (all targets met).
- Evidence: `docs/agentfoundry/af_ide_make_test_eval_20261110.png` (IDE screenshot) and `docs/agentfoundry/af_terminal_20261109.txt` (terminal transcript).

## License

MIT, see `LICENSE`. Data are public WQMIS records; guidance text is quoted from the cited official sources.
