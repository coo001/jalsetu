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

## Impact

No field users or remediation outcomes yet (solo builder, no local partner). The numbers below are reproducible checks on real government records, not impact.

## Quick start

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn app.main:app
# or
make test   # pytest
make eval   # writes eval/results/<date>.json and latest.json, eval/public_sample_30.csv
make run    # uvicorn on port 8080
docker build -t jalsetu . && docker run -p 8080:8080 jalsetu
```

Pages: `/` overview, `/queue` AP sample queue, `/sample/{record_id}` packet (printable), `/sources`, `/eval`.
JSON: `/api/samples`, `/api/packet/{sample_id or record_id}`, `/api/eval/latest`, `/api/sources`, `/api/overview`.

Optional: set `GEMINI_API_KEY` to let `gemini-2.0-flash` reword the letter on the sample page. The reworded
letter is used only if `fact_guard` passes; any error, timeout or guard failure falls back to the template.
Tests never call the network.

## Data provenance

Snapshot `data/snapshots/2026-11-09/`, retrieved `2026-11-09T01:53:38Z` from public WQMIS pages.
`manifest.json` records the sha256 and row count of every file; the app and `make eval` refuse to run if a
hash differs (`jalsetu/snapshot.py`, tested in `tests/test_snapshot.py`).

| File | Rows | Source |
|---|---|---|
| `wq6_AP_2024-2025_samples.csv` | 283 | WQ6 contaminant-wise report, Andhra Pradesh, FY 2024-25 (Fluoride 224, Nitrate 52, E. coli 7; Total arsenic 0) — https://ejalshakti.gov.in/WQMIS/Report/Contaminantwise |
| `wq6_states_2024-2025.csv`, `wq6_states_2025-2026.csv` | 34 each | WQ6 state summary (villages with ≥1 contaminated sample, by parameter) |
| `wq_labs_AP_L10.csv` | 138 | L10 lab/parameter list, AP — https://ejalshakti.gov.in/WQMIS/Main/lab_parameterlist |
| `wq_labs_BR_L10.csv` | 123 | L10 lab/parameter list, Bihar (kept for token tests; not routed) |
| `probe_log.json` | – | collection log |

Collector: `python -m collector.wqmis --date YYYY-MM-DD` (`collector/wqmis.py`, refactored from
`collector/legacy/`). It writes a new dated snapshot directory plus manifest, refuses to overwrite an existing
snapshot, retries with exponential backoff and a timeout, and appends failures to `collector/runs.jsonl`.

## Pinned sources

`jalsetu/guidance/sources.json` and `jalsetu/guidance/advice_table.json`. The code outputs only these strings.

| ID | Edition | sha256 (first 16) |
|---|---|---|
| BIS-10500 | IS 10500:2012 Drinking Water — Specification (Second Revision), BIS, May 2012 ([pdf](https://cpcb.nic.in/wqm/BIS_Drinking_Water_Specification.pdf); [amendment copy](https://www.consumerhelpline.gov.in/bis/IS10500-2012.pdf), Amendment No. 2, Sep 2018, does not change F, NO3, As, E. coli rows) | 9b8999c29ce264aa |
| WHO-GDWQ | WHO Guidelines for drinking-water quality, 4th ed. incl. 1st and 2nd addenda, 2022 (ISBN 9789240045064) | a0ac96fa5eac13e4 |
| WHO-BOIL | WHO Technical brief: Boil water, WHO/FWC/WSH/15.02, 2015 | 136d2e2bc676c981 |
| WHO-AS | WHO fact sheet: Arsenic (web page, accessed 2026-11-09) | web page |
| JJM-HB | Concise Handbook for Monitoring Water Quality of Piped Drinking Water Supply to Rural Households, DDWS / NJJM (no edition printed; content refers to 2024) | 19da7f395364ee6d |
| JJM-FW | Drinking Water Quality Monitoring & Surveillance Framework, NJJM (no edition printed; latest date in text Oct 2022) | 27356d402f6a3ae4 |
| PIB-2022 | PIB, Ministry of Jal Shakti, "Monitoring of Contamination of Ground Water", 21 Jul 2022 | web page |

Limits: fluoride 1.0/1.5 mg/l; nitrate 45/45 mg/l (no relaxation); arsenic 0.01/0.01 mg/l (decision value, see
limitations); E. coli 0 CFU/100 ml. Chemical exceeds if value > permissible; E. coli exceeds if count > 0.

## Evaluation (measured, run 2026-11-09, `make eval`)

Full output: `eval/results/2026-11-09.json`. Reproducibility and safety checks only.

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

Notes on what these numbers mean:
- E1 only shows the code agrees with the government listing; every record in the input was already listed as
  contaminated, so it is not an accuracy measure.
- E3/E4 mutations are written by the same author as the validator and guard, so they test known failure modes,
  not unknown ones.
- E2b: 32 packets (districts ALLURI SITHARAMA RAJU, SRI SATHYA SAI, Y.S.R.) have no lab whose name or address
  contains the WQMIS district spelling (e.g. L10 spells "Sri Satya Sai", WQ6 spells "SRI SATHYA SAI"); no fuzzy
  matching is done.

## Design choices made without asking

- **Duplicate rule is per (sample_id, parameter).** 7 sample ids appear twice in the AP data, each time once for
  Fluoride and once for Nitrate (same sample, two contaminants). These are not flagged. Record ids in the UI are
  `<sample_id>-<param>`; `/api/packet/<sample_id>` returns 409 with both options when ambiguous.
- `TEST_DATE_INVALID` also fires when the test date is after the snapshot date.
- `no_candidate_lab` packets show no advice either (advice is built only for `ready`, as specified).
- The lab that did the original test is not excluded from candidates; it is marked "this is the lab that did the
  original test". In the AP data it is the top candidate in 98 of 283 packets.
- In AP L10 only three WTP in-house labs list Total Arsenic; the State Level lab does not. A real arsenic record
  would be routed to those three.
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
- **Arsenic amendment text not seen.** The BIS 2012 table prints 0.05 mg/l permissible; PIB-2022 quotes BIS as
  "No relaxation"; 0.01 mg/l is used as the decision value. There are no arsenic records in the AP 2024-25
  snapshot; arsenic paths are tested with synthetic records only.
- **JJM documents have no printed edition**; they are pinned by URL and sha256 prefix.
- Only Andhra Pradesh FY 2024-25 sample-level data is loaded.
- Advice is in English only.

## License

MIT, see `LICENSE`. Data are public WQMIS records; guidance text is quoted from the cited official sources.
