# Project Trident synthetic demo

A fixed, **synthetic** three-statement package for a multi-hop investigation
replay. It uses the existing single-account statement CSV template, has no
scoring labels, and does not alter backend rules or configuration.

## Files

- `project_trident_a_hdfc.csv` — Asha Verma at HDFC; salary/merchant controls,
  two deposits just below ₹50,000, and A→B / C→A observations.
- `project_trident_b_sbi.csv` — Blue Dune Trading LLP at SBI; mirrored A→B and
  B→C observations plus an ordinary operating expense.
- `project_trident_c_icici.csv` — Cobalt Route Solutions Pvt Ltd at ICICI;
  mirrored B→C / C→A observations, a partial VASP exit, and a utility control.
- `manifest.json` — expected source evidence, reconciled balances, the ring,
  controls, and the same-name non-merge test condition. `transaction_count`
  excludes each opening-balance row, matching application ingestion. It is
  verification metadata only; application ingestion and scoring do not read it.

## Verify or load

```bash
# From the repository root: deterministic bytes, balances, ring, and controls.
python3 scripts/verify_project_trident.py

# Upload all three through the normal single-statement flow, then confirm each.
curl -F 'files=@test_data/demo/project_trident/project_trident_a_hdfc.csv' \
     -F 'files=@test_data/demo/project_trident/project_trident_b_sbi.csv' \
     -F 'files=@test_data/demo/project_trident/project_trident_c_icici.csv' \
     http://127.0.0.1:8000/api/statements/upload

# Or use the idempotent demo loader. It resets only records registered under
# the `project-trident` demo tag, uploads and confirms the fixtures through the
# normal services, creates/analyzes the case, and verifies the A→B→C→A finding.
curl -X POST http://127.0.0.1:8000/api/demo/project-trident/load

# Remove only the tagged demo records when finished.
curl -X POST http://127.0.0.1:8000/api/demo/project-trident/reset
```

Use the mirrored `TRI-RING-AB`, `TRI-RING-BC`, and `TRI-RING-CA` references to
trace A→B→C→A. The two `Nikhil Shah` observations intentionally reference
separate associated institutions (HDFC and ICICI); do not auto-merge on the
name alone.
