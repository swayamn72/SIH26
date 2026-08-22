# MuleGuard Local — Post-Build Audit Report

Audited: 2026-08-05 · Target: `E:\CodeAmble\muleguard-local` · Host: Windows, Python 3.14.0, pytest 9.1.1, Docker 29.2.1 (daemon live), Ollama live (localhost:11434)

Method: live code reads + executed verification scripts + end-to-end API run on a synthetic fixture. Every claim below cites `file:line`.

Legend: ✅ verified correct · ⚠️ partial / data-dependent · ❌ broken / not implemented

---

## Section 1 — Algorithm-by-Algorithm Formula Verification

### 1.1 Multi-Debit Round-Trip Cycle (subject→A→subject)
✅ **Detected.** `graph_builder.py:19-29` adds edges `ACCT→cpty` (debit) and `cpty→ACCT` (credit) on a `MultiDiGraph`; `cycle_detector.py:88` runs `nx.strongly_connected_components`, then `simple_cycles` (Johnson) per component `cycle_detector.py:113`. Verified live: 3 two-hop cycles found on the synthetic fixture (`CYCLE nodes ['2','ACCT_1'] risk 0.725`, etc.).

❌ **Multi-hop (>2 parties) is impossible with the current graph model.** `build_transaction_graph` only ever links the subject account to counterparties (star topology). There is no `A→B` edge, so the only cycles are 2-node round trips. A genuine 3-hop layering (`subject→A→B→subject`) cannot be represented or detected. README "Limitations" acknowledges this in words, but the master-prompt claim of "3+ hop circular flow detection" is not achievable on a single statement.

### 1.2 Amount Conservation (CV-based)
✅ **Formula matches spec.** `cycle_detector.py:49-55`: `cv = stdev/mean`, `amount_conservation = max(0, 1 - cv)` over the cycle's edge amounts; weight `amount_conservation: 0.35` (`cycle_detector.py:22`, `thresholds.yaml:75`). Bug-fix #3 (`G.get_edge_data(u, v)` iterating `edge_dict.items()`) present at `cycle_detector.py:37-41`. Verified: equal amounts → conservation = 1.0.

### 1.3 Velocity Compression
❌ **Effectively inert.** `cycle_detector.py:43-47` reads `first_seen`/`last_seen` from node attributes, but `graph_builder.py` never sets them (only `label`, `flow`). Therefore `min_ts=∞`, `max_ts=-∞`, `cycle_span_days` falls back to `0.1` (`:57`), `velocity_compression = hop_count/0.1 = 20`, normalized to `1.0` (`:60`). Every cycle scores the maximum velocity regardless of real time span. Weight `velocity_compression: 0.30` is effectively a constant.

### 1.4 Cycle Composite Risk + Recurrence
⚠️ **Formula runs but drops one term.** `cycle_detector.py:63-67` computes `0.35·conservation + 0.30·velocity + 0.15·inverse_hops`. The weight `cycle_recurrence: 0.20` is loaded (`:24`) but **never used** in the sum; only 0.80 of the configured weights actually contribute. Max achievable risk = 0.80 (not 1.0). For any conserved 2-cycle the score is exactly `0.35 + 0.30 + 0.075 = 0.725`. `min_cycle_risk_score: 0.6` (`thresholds.yaml:71`) is trivially exceeded.

### 1.5 Robust MAD Z-Score
✅ **Formula correct.** `anomaly_scorer.py:9-16`: `0.6745·(x−median)/MAD`, `MAD==0 → zeros`. Live check on `[1,2,3,4,100]` → `[-1.349, -0.6745, 0.0, 0.6745, 65.4265]`. Threshold `3.5` (`thresholds.yaml:126`). Deterministic across runs (byte-identical).

### 1.6 Isolation Forest
✅ **Correctly parameterized and deterministic.** `anomaly_scorer.py:19-49` uses `n_estimators=200, random_state=42, contamination="auto"`; returns `anomaly_frac` = fraction of `−1` labels + top-5 contributing features. Two runs on identical input produced identical output (`anomaly_frac 0.5`, same feature list).
❌ **Not called in the pipeline.** `routes_review.py:25` imports `compute_isolation_forest_anomaly` but the confirm flow (`:300-307`) calls only `compute_mad_anomaly`; `anomaly_detail["isolation_forest_score"]` is hardcoded `None` (`:304`). The anomaly score actually used is `mad_flagged_count / feature_count`.

### 1.7 Benford Leading-Digit (Chi-Square)
⚠️ **Formula correct, gated behind data.** `structuring_features.py:57-82`: expected `log10(1+1/d)`, `chi_sq = Σ(obs−exp)²/exp`, uses hardcoded critical value `15.507` via `rule_scorer.py:77`. Requires ≥10 nonzero amounts (`:66`), else `None`. On the 6-row fixture → `None`. Fine as a data guard, but the README claim "every magic number in config" is violated by the hardcoded `critical_value_95 = 15.507` (`rule_scorer.py:77`).

### 1.8 Header Classification / Template Matching
❌ **Template matching is dead — path bug.** `template_matcher.py:11` resolves the template dir as `Path(__file__).parents[2]/config/bank_templates`. Because this module sits 3 levels deep (`backend/app/understanding/`), `parents[2]` = `backend/`, so it looks for `backend/config/bank_templates/` which **does not exist** (config lives at repo root `config/`; Docker copies to `/app/config`). Live check: `_load_templates()` returns 0 templates (dir contains `sbi_savings_v1.json` etc.). `routes_upload.py:93-94` therefore always falls through to the heuristic `classify_columns`. Same bug affects `manual_mapping_api.py:11` (`user_learned` dir). Note `config_loader.py:13` is unaffected because it sits only 2 levels deep → resolves to repo root; this inconsistency is the root cause.

### 1.9 Balance Reconciliation
✅ **Decimal arithmetic, tolerance applied.** `reconciliation.py:15` `Decimal(str(cfg.tolerance))` (0.01); running-balance check `expected = prev − debit + credit`, `diff ≤ tolerance` (`:41-43`). Live: perfect chain → 1.0; off-by-0.005 within tolerance → reconciled; no-balance path uses net-delta rate (`:20-30`); empty list → 1.0. Extraction-confidence bands `≥0.98 high / ≥0.85 medium` (`quality_score.py:37-42`) match `thresholds.yaml:22-23`.

### 1.10 Rule Engine (YAML)
✅ **Parser matches spec** (`rule_scorer.py:7-83`): `AND`/`OR`/`> >= < <= ==`, values or `pNN` percentiles, and the `critical_value_95` symbol.
❌ **3 of 6 rules are non-functional.**
- `R5_circular_flow_detected` (`thresholds.yaml:94-96`) conditions on `max_cycle_risk_score > 0.6`, but no feature named `max_cycle_risk_score` is ever produced by `compute_all_features` (REGISTRY has 17 features, none matching) → **R5 can never trigger**.
- `R1_low_retention_high_turnover` requires `turnover_ratio > 8`; `turnover_ratio` is always `None` (see Section 2) → **R1 can never trigger**.
- `R4_benford_anomaly` requires `benford_deviation_score`; that feature is `None` on statements with <10 amounts and frequently unavailable → **R4 is usually inert** (works only on datasets with ≥10 nonzero amounts).
- Working: `R2_dormancy_then_burst`, `R3_structuring_near_threshold`, `R6_fan_in_fan_out`.
✅ Rule score caps at 100 (`rule_scorer.py:111`).

### 1.11 Supervised Calibration
⚠️ **Code correct, never invoked.** `calibration.py` implements Isotonic vs Platt selection by Brier score and `apply_calibration`; `supervised_scorer.py` exposes `supervised_model_available` (label gate from config `supervised.min_labeled_accounts=200`) and a `SupervisedScorer` (live check: gate `199→False`, `200→True`; `predict_proba` hardcodes `0.5`). Neither module is imported by `routes_review.py` or any other module (grep confirms zero call sites). The "optional supervised layer" advertised in README is dead code in this build.

### 1.12 Weighted Score Fusion
✅ **Formula matches config.** `fusion.py:17-38`: availability is inferred from `supervised_probability is not None`. Live: unsupervised `0.65·rule + 0.35·anomaly` → 18.0; supervised `0.4·rule + 0.25·anomaly + 0.35·supervised`. Formula string is carried into the evidence bundle. Because the supervised layer is never wired, only the unsupervised branch is reachable in practice.

### 1.13 Three-Tier Decision Policy
✅ **Matches spec exactly.** `decision_policy.py:20-25`: `CONFIRMED_SUSPICIOUS` iff `fused ≥ 75 AND rules_triggered AND confidence != "low"`; `LIKELY_LEGITIMATE` iff `fused ≤ 25 AND (anomaly is None or < 0.3) AND confidence == "high"`; else `REVIEW_REQUIRED`. Live-tested all 5 branch combinations.

### 1.14 Supervised 200-Label Gate
✅ Gate function verified (`supervised_scorer.py`), ✅ configured (`thresholds.yaml:117-118`). ❌ **Not enforced anywhere in the pipeline** — no call site; the gate only exists as a utility function (same dead-code status as 1.11).

### 1.15 Ollama Determinism
✅ **Parameters match spec.** `ollama_client.py:22-27`: `temperature=0.0, top_p=1.0, seed=42, num_predict=max_tokens`, `seed=42` default. Live: server reachable (`is_available=True`).
❌ **Default model not provisioned.** Client defaults to `qwen2.5:7b-instruct` (`ollama_client.py:9`); installed models on the running instance are `moondream, llama3, llava, llama3.2:1b, nomic-embed-text`. Live AI narrative request returned `source: "template"` (silent fallback, `narrative_generator.py:24-25`/`:36-37`). No model-pull step exists in `setup.sh`/`setup.ps1`/`docker-compose.yml`, and the model name is not configurable via env.

### 1.16 LLM Fact-Checker
✅ **Works.** `fact_checker.py`: number regex `\d+(?:\.\d+)?%?`, `_numbers_in_json` normalizes %↔fraction (live: `10%` matches `0.1`), banned-term list `["guilty","money laundering confirmed","criminal","arrest","convicted"]`. Live: invented number rejected, valid pass, banned term caught. ⚠️ `_numbers_in_json` also emits spurious tokens (e.g. `100` → `"10000%"`), so a statement citing "10000%" could match an evidence value of 100 — minor over-permissive edge.

---

## Section 2 — Feature Formula Spot-Check (hand-computed vs. code)

Fixture: `backend/tests/fixtures/sample_statements/sbi_circular_flow.csv` (6 txns, credit 10k + debits 9500/9000/10000 + credits 9500/9000).

| Feature | Hand-computed | Code output | Verdict |
|---|---|---|---|
| `net_retention_ratio` | `1 − 9500/28500 = 0.6667` | `0.6667` | ✅ (but see note) |
| `average_daily_balance` | trapezoid over 6 daily balances = 133,900 | `133900.0` | ✅ |
| `median_holding_time_hours` | 24h (only matched credit→debit pair) | `24.0` | ✅ |
| `fan_in_score` | 3 distinct credit counterparties / 3 = 1.0 | `1.0` | ✅ |
| `fan_out_score` | 3 distinct debit counterparties / 3 = 1.0 | `1.0` | ✅ |
| `weekend_night_activity_ratio` | 2 weekend days / 6 = 0.3333 | `0.3333` | ✅ (night branch dead — `velocity_features.py:43` `has_time=False` constant) |
| `round_number_ratio` | 4 round / 6 nonzero = **0.6667** | `0.3333` | ❌ denominator bug |
| `turnover_ratio` | 57000/133900 = 0.4257 (with ADB) | `None` | ❌ ordering bug |
| `inflow_outflow_velocity` | 2 (peak daily count) | `None` | ❌ runtime error |
| `benford_deviation_score` | — (<10 amounts) | `None` | ⚠️ data-gated, by design |
| `name_consistency_flag` | — (no account holder) | `None` | ❌ never computable |

**`round_number_ratio` denominator bug.** `structuring_features.py:46-54` counts round among nonzero amounts but divides by `len(amounts)`; because `routes_review.py:111-112` fills missing debit/credit with `0.0` (not NaN), both columns are all-non-null → denominator doubled (12 instead of 6). True ratio 0.6667, reported 0.3333.

**`turnover_ratio` ordering bug.** `feature_registry.py:43-63` registers `turnover_ratio` (index 6) **before** `average_daily_balance` (index 7). At `feature_registry.py:142-144` it reads `results.get("average_daily_balance")`, which is not yet computed → passes `avg_daily_balance=None` → `behavior_features.py:67-68` returns `None`. **`turnover_ratio` can never be non-None**, which also kills rule R1.

**`inflow_outflow_velocity` runtime error.** `velocity_features.py:20`: `int((dates >= window_start) & (dates <= window_end)).sum()` — `int()` on a multi-element boolean Series raises `TypeError`; caught at `feature_registry.py:155-156`, so the feature is always `None` on real multi-row data.

**Count discrepancy.** REGISTRY holds **17** features, not the 18 claimed in the spec; the pipeline reports `feature_count: 17`, and 4 of the 17 are `None` on this fixture.

**`net_retention_ratio` spec deviation.** `behavior_features.py:15-28` selects *all* debits after each credit (no 24h filter despite the name) and takes `iloc[0]` — the "matched_24h_outflow" is actually "next debit after each credit, whenever it occurs".

---

## Section 3 — Guardrail Verification

| Guardrail | Status | Evidence |
|---|---|---|
| G1 Network isolation | ⚠️ static-only | Grep across `backend/`: the only URLs are `http://ollama:11434` and `http://localhost:11434` (`ollama_client.py:11`). Compose binds both services to `127.0.0.1` (`docker-compose.yml:8,34`). `routes_health.py:19-28` self-test present. **Caveat:** containers run on the default bridge with normal egress — there is no outbound-egress blocking; "isolation" is by code discipline, not enforcement. No live egress test performed. |
| G2 Determinism | ✅ | `determinism_guard.assert_deterministic` (`determinism_guard.py:16-23`); test `test_scoring_determinism.py`; IsolationForest fixed `random_state=42`; two live runs byte-identical. |
| G3 Privacy / PII | ❌ | `privacy_guard.py` is **never imported** (grep: only self-references). `PIIRedactionMiddleware.dispatch` is a no-op passthrough (`privacy_guard.py:25-27`). Raw rows including PII are stored in `Statement.raw_rows`/`raw_headers` (`routes_upload.py:111-112`) and original files persist on disk (`:68-70`). |
| G4 OOD hard-reject | ⚠️ label only | `classify_ood_tier` returns `hard_reject` below 0.40 (`ood_detector.py:159-170`), but `routes_upload.py` never rejects — the statement is stored and transactions parsed regardless of tier. Downstream `confirm` only sets `ood_check_passed = ood_score >= 0.5` (`routes_review.py:321`) and continues. No hard block exists. |
| G5 Fact-checker hallucination | ✅ | Unit + live verified (see 1.16). Adversarial end-to-end (LLM producing a fabricated number) not exercised because the default model is absent; the `fact_check_output` gate itself is correct. |
| G6 Row-id traceability | ✅ | Cycles carry `contributing_row_ids` (`cycle_detector.py:75`); evidence bundle preserves them (`evidence_bundle.py:64-75`); transactions persist `tagged_cycles` (`routes_review.py:289-295`). Rules' `contributing_row_ids` is wired through the schema but the rule scorer never populates it (`rule_scorer.py:103-109`) — traceability for rules is empty by default. |

---

## Section 4 — Test Coverage Review

**Baseline: 22 tests pass** (`pytest -q` → `22 passed in 4.17s`) across 8 files + conftest.

| File | Tests | Notes |
|---|---|---|
| `test_csv_extraction.py` | basic_csv, csv_with_preamble | ✅ covered |
| `test_cycle_detection.py` | 3-node cycle, linear, empty | ⚠️ "three-node" fixture actually only exercises 2-node cycles (star topology); no dense-cap or risk-threshold path |
| `test_fact_checker.py` | valid, invented, banned | ✅ unit-level |
| `test_features.py` | account_age, dormancy, empty | ⚠️ does not touch turnover/velocity/benford/name-consistency → the 4 `None` bugs went undetected |
| `test_ood_detector.py` | high-conf, low-row-count, signals | ✅ |
| `test_pdf_extraction.py` | csv-classified, unsupported ext, empty | ✅ file_router level |
| `test_reconciliation.py` | perfect, no-balance, empty | ✅ |
| `test_scoring_determinism.py` | rule scorer, repeatable | ✅ |

**Coverage gaps (untested):** OCR path (pytesseract), XLSX/XLS path, non-UTF8 encoding + footer stripping, multi-parallel-edge cycles, rule-per-fixture (R1–R6), isolation-forest determinism in-process, supervised gate 199/200, fusion branch selection, decision-policy all branches, `PUT /config` persistence, `name_consistency_flag`, `turnover_ratio` ordering, `inflow_outflow_velocity`, network-egress static guard, adversarial (banned-term) fact-check, template-matcher loading. The fixture directories `backend/tests/fixtures/sample_statements/` and `synthetic_mule_cases/` were empty before this audit; a single fixture was added (`sbi_circular_flow.csv`).

---

## Section 5 — Golden-Path End-to-End Trace

Fixture: `sbi_circular_flow.csv` (6 rows, 3 two-hop round-trips, perfectly reconciling balances). All calls executed against the real FastAPI app (`TestClient`, fresh SQLite).

| Step | Endpoint | Result |
|---|---|---|
| Upload | `POST /api/statements/upload` | 200; 6 txns; `ood_tier: auto_proceed`, `ood_score: 0.7357`; errors `[]` |
| Preview | `GET /api/statements/1/preview` | 200; 6 txns ❌ `detected_column_mapping` = OOD signals dict (`routes_review.py:126-128` populates from `stmt.ood_signals`) |
| Confirm | `POST /api/statements/1/confirm` | 200; `analyzed`; tier `REVIEW_REQUIRED`; fused `10.8` (`0.65*rule_score + 0.35*anomaly_score`); rec `1.0`; conf `high`; rules `[]`; features `17`; cycles `3` |
| Graph | `GET /api/statements/1/graph` | 200; 4 nodes, 6 edges, 3 cycles (all risk 0.725) |
| Transactions | `GET /api/statements/1/transactions` | 200; `total: 6`, `items: 6` |
| Evidence | `GET /api/statements/1/evidence` | 200; full bundle incl. MAD flags |
| Narrative (AI) | `GET /api/statements/1/narrative?use_ai=true` | 200; `source: template` (default model missing → silent fallback) |
| Export | `POST /api/statements/1/export` | 200; returns JSON fallback (WeasyPrint import fails on host; `routes_report.py:160-165`) |

The pipeline is **functional end-to-end and deterministic**, but produces low-signal output on a textbook mule pattern: fused score 10.8 (no rules fire, because R1/R5 are dead and R3/R4/R6 are inactive on this data), tier REVIEW_REQUIRED, and the 3 "cycles" are merely subject↔counterparty round-trips.

---

## Section 6 — Bug-Fix Regression Checks

| # | Fix | Status | Evidence |
|---|---|---|---|
| 1 | Remove `backend.app`/`from backend` import prefixes | ✅ | Repo-wide grep: zero occurrences |
| 2 | CSV preamble + multi-line header sniffing | ✅ | `csv_extractor.py:43-56` preamble scan + Sniffer; `test_csv_with_preamble` passes |
| 3 | `MultiDiGraph` parallel-edge handling (`get_edge_data`) | ✅ | `cycle_detector.py:37-41` iterates `edge_dict.items()`; live multi-edge run returned correct 2-edge cycles |
| 4 | Decimal/float reconciliation precision | ✅ | `reconciliation.py` uses `Decimal` throughout; live tolerance edge (0.005 vs 0.01) reconciled |
| 5 | OOD on blank/sparse columns | ✅ | `ood_detector.py:44-55` skips empty columns and counts only filled values |
| 6 | CV-based conservation in both call sites (reconciliation + cycle) | ⚠️ | `cycle_detector.py:49-53` uses CV correctly; reconciliation uses running-balance diff (not CV) — the two were never conflated. No duplicate call-site drift observed |
| 7 | txt-not-CSV minimum columns | ✅ | `file_router.py:47-50` requires `≥2 columns` and `≥2 rows`; live: single-column `.txt` → `None` (rejected), two-column → `csv` |

---

## Section 7 — Deployment / Docker Review

- ✅ Docker 29.2.1 daemon live; `docker compose config -q` valid.
- ✅ Two-service compose: `ollama` + `muleguard` (`docker-compose.yml`), healthcheck `ollama list`, both ports bound to `127.0.0.1`. `setup.sh`/`setup.ps1` create data dirs, copy `.env`, and `docker compose up --build`.
- ❌ **`DATA_DIR`/`HOST`/`PORT`/`LOG_LEVEL` env vars are decorative.** `db/session.py:5-8` hardcodes `Path(__file__).parents[3]/"data"` and never reads `DATA_DIR`; `routes_upload.py:24` hardcodes the upload dir the same way; `main.py` and the Docker CMD ignore `HOST`/`PORT`/`LOG_LEVEL`.
- ❌ **Data volume mismatch.** Compose mounts `./data:/data` and sets `DATA_DIR=/data`, but inside the container the modules resolve paths to `/app/data` (`db/session.py`, `routes_upload.py`) because `parents[n]` walks up from `/app/backend/app/...`. Result: the SQLite DB and uploads land in `/app/data` (ephemeral, lost on `docker compose down`), while the mounted `./data` volume stays unused.
- ❌ **`template_matcher` path bug reproduces in Docker too** (`/app/backend/config/bank_templates` missing; templates copied to `/app/config`), so template matching is equally dead in the container.
- ❌ **Ollama model not provisioned** — no `ollama pull` in compose/setup; default model `qwen2.5:7b-instruct` absent.
- ⚠️ `Dockerfile` builds with `python:3.11-slim`; local dev runs 3.14.0. `tesseract-ocr`, `libgl1`, `libglib2.0-0` installed for PDF/OCR; WeasyPrint's Pango/GTK deps are **not** installed (`libpango-1.0-0` etc.), so PDF export fails in the container too (falls back to JSON).

---

## Section 8 — Frontend–Backend Wiring

The frontend `dist/` is served by `main.py:39-41`. **Every page has at least one broken integration** (verified by reading both sides and citing lines):

| # | Contract | Status | Consequence |
|---|---|---|---|
| 1 | `getTransactions` sends `?page=&page_size=` but backend expects `offset=&limit=`; type `{rows,total,page,page_size}` vs backend `{total,offset,limit,items}` (`api.ts:55-60,88-89` vs `routes_analysis.py:37-41,73-74`) | ❌ | Dashboard **crashes**: `transactions.rows.map` undefined (`TransactionTable.tsx:42`); pagination dead |
| 2 | `getPreview` expects `row_count`/`detected_columns`; backend returns `transaction_count`/`detected_column_mapping` (populated from OOD signals!) (`api.ts:34-35` vs `routes_review.py:126-140`) | ❌ | Mapping editor never renders; "undefined rows detected" (`ExtractionReviewPage.tsx:66-68`) |
| 3 | `updateMapping` posts raw mapping; backend expects `{column_mapping, save_as_template, headers, raw_rows}` (`api.ts:77-81` vs `routes_review.py:35-39`) | ⚠️ latent | Never called from any page; would 422 if used |
| 4 | `upload` expects `statement_ids[]`; backend returns only `{results, errors}`; file field `filename` vs `original_filename` (`api.ts:69` vs `routes_upload.py:36-48,152`) | ❌ | "Review Extraction" button never appears (`UploadPage.tsx:132`); filename blank (`:117`) |
| 5 | `getNarrative` expects `{text, source}`; backend returns `{statement_id, narrative, source}` (`api.ts:93` vs `routes_analysis.py:44-47`) | ❌ | Narrative panel blank (`DashboardPage.tsx:120`, `NarrativePanel.tsx:29`) |
| 6 | `getGraph` expects `cycles[{cycle_id, node_ids, risk_score}]`; backend returns `{cycle_id, nodes, hop_count, cycle_risk_score, ...}` (`api.ts:52` vs `routes_graph.py:57-77`, `cycle_detector.py:70-75`) | ❌ | ProofGraph **crashes** when ≥1 cycle exists (`c.node_ids.join` `ProofGraphPage.tsx:100`; `cycles.flatMap` `ProofGraphCanvas.tsx:37`) |
| 7 | `exportReport` expects `{download_url}` via `res.json()`; backend streams raw PDF/JSON bytes (`api.ts:101-102` vs `routes_report.py:153-165`) | ❌ | PDF never downloads; JSON case downloads nothing |
| 8 | `updateConfig` PUTs full config; backend expects `{key, value}` (`api.ts:106-110` vs `routes_config.py:14-16`) | ⚠️ latent | Never called; would 422 |
| 9 | `batchMerge` expects `{status, merged_graph}`; backend returns `GraphOut` (`api.ts:95-99` vs `routes_graph.py:25-29,80-121`) | ⚠️ latent | Never called; would break |

Working: `getEvidence`/bundle rendering (Dashboard + EvidenceExplorer use `cycle_id/hop_count/cycle_risk_score/nodes`, which match the evidence schema).

---

## Section 9 — Config Integrity

- ✅ `config/thresholds.yaml` (132 lines) is the single source of truth and is loaded via cache (`config_loader.py:9-17`); `reload_config` clears cache.
- ❌ **`PUT /api/config/thresholds` is a no-op that lies.** `routes_config.py:19-29` mutates the cached dict in place, then calls `reload_config`, which re-reads the **unchanged file**, discarding the mutation. Live verification: `BEFORE 75 → PUT 200 {"status":"updated"} → AFTER 75`. The YAML file is never written.
- ❌ **`ConfigAuditLog` is never written.** Table exists (`db/models.py` — `config_audit_log`); live check: 0 rows after a PUT. No audit trail for config changes.
- ⚠️ `hard_reject: 0.40` key (`thresholds.yaml:9`) is unused — `classify_ood_tier` uses `low_confidence_lower` instead (`ood_detector.py:162-170`).
- ⚠️ Hardcoded `critical_value_95 = 15.507` in `rule_scorer.py:77` contradicts README's "no hardcoded values in code" claim.
- ⚠️ README documents `/api/batch/merge` and `/api/config/thresholds` as usable endpoints; the wiring gaps above make both effectively unusable from the UI.

---

## Section 10 — Dependency Sanity

- ✅ Verified importable + versions: networkx 3.6.1, scikit-learn 1.8.0, pandas 2.3.3, rapidfuzz 3.14.5, pdfplumber 0.11.10, pytesseract 0.3.13, camelot 2.0.0, ollama (reachable), chardet 7.4.3, charset_normalizer 3.4.6, yaml, openpyxl.
- ⚠️ `pyproject.toml` uses `>=` ranges, **not pinned**; there is **no lockfile** for the backend. Reproducibility risk for the "fully reproducible offline" claim (frontend has `package-lock.json`, backend does not).
- ❌ **WeasyPrint** import fails on this host (`WeasyPrint could not import some external libraries` — missing Pango/GTK). Dockerfile also omits the Pango/GTK apt packages, so PDF export fails there too; `routes_report.py` gracefully falls back to JSON (verified live).
- ✅ Ollama chat client works against the server; ❌ default model absent (Section 1.15).
- ⚠️ `pypdfium2` present; OCR path not live-tested (no image PDF fixture available; would need `pytesseract` + tesseract binary on PATH on this host).
- ⚠️ Runtime warning: `requests 2.xx` vs `urllib3 2.6.3`/`chardet 7.4.3` mismatch prints on stderr in tests (non-fatal).

---

## Section 11 — Limitations Disclosure

README `## Limitations` (lines 133-138) contains 4 required statements:
1. ✅ Single-statement mode cannot prove multi-hop external cycles across unrelated accounts (this is true — and correctly aligns with the star-topology finding in 1.1).
2. ✅ Decision-support tool; human review required.
3. ✅ Local performance metrics meaningless until sufficient labeled data; tool reports "not enough data".
4. ✅ No external database/watchlist/network resource accessed unless the user supplies a local file.

**Not disclosed:** the LLM layer silently degrades to template summaries when the default Ollama model is missing; 4 of 17 features routinely return `None`; rules R1/R4/R5 are non-functional; and config changes via the UI are silently discarded. These are runtime-behavior gaps the README does not mention.

---

## Section 12 — Summary & Verdict

**Counts:** 16/16 algorithm items examined · 6 guardrails examined (2 ✅, 2 ⚠️, 2 ❌) · 22 baseline tests (all pass, with 7 documented coverage gaps) · golden path runs end-to-end · 7/7 regression fixes verified (1 partial) · compose valid + Docker live · 9 wiring contracts examined (6 broken live, 3 latent) · config PUT broken + no audit log · dependencies load (WeasyPrint excepted) · README limitations present but incomplete.

**Verdict: ⚠️ FUNCTIONAL BUT NOT SHIP-READY — DO NOT PASS in current state.**

The deterministic core that exists (reconciliation, MAD, fusion, decision policy, fact-checker, cycle scoring) is correctly implemented and reproducible, and the API pipeline runs end-to-end. However the following must be fixed before acceptance:

1. **Critical — dead scoring paths:** `turnover_ratio` ordering bug (`feature_registry.py`), `inflow_outflow_velocity` type error (`velocity_features.py:20`), R5's impossible `max_cycle_risk_score` condition, supervised layer + calibration never wired, IsolationForest never called.
2. **Critical — template matching path bug** (`template_matcher.py:11` / `manual_mapping_api.py:11`), dead in both local and Docker layouts.
3. **Critical — config PUT is a silent no-op** with no file write and no audit log (`routes_config.py`).
4. **High — frontend contracts:** 6 live breaks including two crashes (Dashboard transactions, ProofGraph cycles) and non-functional Upload/Preview/Narrative/Export.
5. **High — deployment:** data lands in ephemeral `/app/data` not the mounted volume; `DATA_DIR` ignored; WeasyPrint Pango deps missing; Ollama default model not provisioned.
6. **High — guardrails:** privacy/PII module dead and never imported; OOD `hard_reject` is label-only.
7. **Medium — formula deviations:** `round_number_ratio` denominator inflation; `net_retention_ratio` missing the 24h window; `cycle_recurrence` weight unused; velocity effectively constant.

Priority order for remediation: (1) feature/rule wiring → (2) config write-back + audit → (3) frontend contract alignment → (4) template-matcher path → (5) deployment data paths + model provisioning → (6) privacy guardrail enforcement → (7) re-run full test suite with new coverage for the previously-None features.
