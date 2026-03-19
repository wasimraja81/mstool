# Leakage Root-Cause Analysis Plan (REF field vs ODC weight)

## 1) Goal

Build a reproducible analysis structure to isolate **why residual leakages on 1934-638 increase** by separating effects from:

1. `REF_FIELDNAME` quality (sky-model mismatch, unmodelled polarized sources), observed through one or more `SB_REF` instances, and
2. `ODC_WEIGHT` changes (weight update side-effects),

while controlling for beam and processing context.

This document is a **planning blueprint only** (no code changes), aligned to existing data/file naming conventions already used by:

- `projects/calibration-updates-2026/scripts/assess_possum_1934s.sh`
- `projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh`
- `mstool/bin/averageMS.py`
- `mstool/bin/combine_beam_outputs.py`

---

## 2) Current data model and where signal lives

## 2.1 Tuple identity already encoded in paths

Your current processing directories encode the key factors:

- `ODC-<id>/`
- `SB_REF-<id>_SB_1934-<id>_SB_HOLO-<id>_AMP_STRATEGY-<...>-insituPreflags/`
- `1934-processing-SB-<target>/assessment_results/`

This is ideal for dimensional analysis because each `assessment_results` directory corresponds to a single tuple run.

## 2.2 Per-beam outputs already generated

Within each `assessment_results/`, you already have per-beam files (00–35):

- `*.beamXX.txt` (bpcal)
- `*.beamXX.lcal.txt` (leakage-calibrated)
- `*.beamXX_stokes.png`
- `*.beamXX_pol-degree.png`
- same for `.lcal` variants

`combine_beam_outputs.py` parses leakage metrics from `.txt` headers:

- `|Q|/I`
- `|U|/I`
- `sqrt(Q^2+U^2)/I` (L/I)
- `|V|/I`

and already produces tuple-level summary plots and media.

## 2.3 Manifest already carries useful semantics

The manifest can provide:

- `SB_REF`, `SB_1934`, `SB_HOLO`, `SB_TARGET_1934`
- `ODC_WEIGHT`
- `AMP_STRATEGY`, `DO_PREFLAG_REFTABLE`
- `REF_FIELDNAME`

This is sufficient to build a rich comparison table without changing acquisition.

---

## 3) Analysis design principles

1. **Beam-first diagnostics**: leakage pathologies are often beam-local.
2. **Paired comparisons** over absolute levels whenever possible:
   - Same ODC, different `REF_FIELDNAME` → isolate sky-field effect.
   - Same `REF_FIELDNAME`, different ODC → isolate ODC effect.
3. **Robust stats over means only**:
   - Median, MAD/robust sigma, and high-percentile tails (e.g., P90/P95).
4. **Use both bpcal and `.lcal` channels**:
   - If issue persists post-lcal, root cause may be stronger/systematic.
5. **Confounders must be explicit**:
   - Keep `AMP_STRATEGY`, `DO_PREFLAG_REFTABLE`, `SB_1934`, `SB_HOLO` visible in all summaries.

---

## 4) Proposed summary dataset (single source of truth)

Create one tabular dataset (CSV/Parquet conceptually) with one row per:

- `(tuple_id, beam, variant)` where `variant ∈ {bpcal, lcal}`

Recommended columns:

### Identity and provenance
- `manifest_index`
- `sb_ref`, `ref_fieldname`
- `sb_1934`, `sb_holo`, `sb_target_1934`
- `odc_weight`
- `amp_strategy`, `do_preflag_reftable`
- `tuple_path`
- `variant` (`bpcal` / `lcal`)
- `beam`

### Leakage metrics
- `q_over_i_pct`
- `u_over_i_pct`
- `l_over_i_pct`
- `v_over_i_pct`

### Derived diagnostics
- `l_minus_median_beam_by_odc` (beam-wise centered residual)
- `l_minus_median_beam_by_ref_fieldname`
- `l_minus_median_beam_by_sb_ref_within_fieldname`
- `rank_within_beam` (across tuples)
- quality flags (`missing_txt`, parse failures)

This dataset is the core that enables all other summaries.

---

## 5) Root-cause isolation framework

## 5.1 REF-field effect (holding ODC fixed)

Primary question (Fix ODC, vary field):

For a fixed `ODC_WEIGHT`, how does leakage distribution across beams vary from `REF_FIELDNAME` to `REF_FIELDNAME`?

Note on identifiers:
- `SB_REF` is an observation-level identifier.
- Multiple `SB_REF` values may map to the same `REF_FIELDNAME`.
- Therefore, REF causality should be evaluated primarily at `REF_FIELDNAME` level, with `SB_REF` used as a secondary within-field consistency check.

Planned summaries:

1. **Beam × REF_FIELDNAME heatmap per ODC**
   - value = median `L/I` for `(beam, ref_fieldname)` at fixed ODC
2. **Within-field SB_REF spread check**
   - For each `(beam, ODC, ref_fieldname)`, compute spread across `SB_REF` instances
   - Large spread flags observation/run-level effects distinct from sky-field effects
3. **REF_FIELDNAME delta-to-ODC baseline**
   - For each beam and ODC, subtract beam median across field names
   - Persistent positive deltas for one field name indicate likely REF-field contamination
4. **REF_FIELDNAME ranking table by ODC**
   - `% beams above threshold` (e.g., L/I > X)
   - `P95(L/I)` and robust z-score

Explicit output tables for 5.1:
- `beam_x_field_at_fixed_odc.csv`
   - keys: `odc_weight`, `beam`, `ref_fieldname`
   - values: `median_l_over_i`, `p90_l_over_i`, `count_sb_ref`, `count_samples`
- `field_effect_scores_at_fixed_odc.csv`
   - keys: `odc_weight`, `ref_fieldname`
   - values: `delta_to_beam_baseline`, `affected_beam_count`, `p95_l_over_i`, `robust_z`

Interpretation rule:
- If one `REF_FIELDNAME` is worse than peers for many beams at the same ODC, likely REF-field model issue.
- If differences are mostly between `SB_REF` values inside the same field name, likely observation/execution variability.

## 5.2 ODC effect (holding REF fixed)

Primary question (Fix field, vary ODC):

For a fixed `REF_FIELDNAME`, how does leakage distribution across beams change from `ODC_WEIGHT` to `ODC_WEIGHT`?

Planned summaries:

1. **Beam × ODC heatmap per REF_FIELDNAME**
2. **ODC delta-to-REF_FIELDNAME baseline**
   - For each beam and field name, subtract beam median across ODCs
3. **ODC consistency score by REF_FIELDNAME**
   - max pairwise ODC spread in `L/I` per beam
   - count of beams with spread > threshold

Explicit output tables for 5.2:
- `beam_x_odc_at_fixed_field.csv`
   - keys: `ref_fieldname`, `beam`, `odc_weight`
   - values: `median_l_over_i`, `p90_l_over_i`, `count_sb_ref`, `count_samples`
- `odc_effect_scores_at_fixed_field.csv`
   - keys: `ref_fieldname`, `odc_weight`
   - values: `delta_to_beam_baseline`, `affected_beam_count`, `p95_l_over_i`, `robust_z`

Interpretation rule:
- If same field name shows materially different leakage for different ODCs in same beams, likely ODC-side issue.

## 5.3 Beam stability lens (cross-cutting)

Some beams are naturally fragile. Add a beam stability profile:

- For each beam, compute across-all-tuples distribution of `L/I`
- Tag beams as:
  - `stable` (low spread),
  - `sensitive` (high spread),
  - `pathological` (high median + high spread)

Use this to avoid over-attributing root cause from inherently unstable beams.

---

## 6) Visualization plan (operator-facing)

## 6.1 Tier-1: Fast triage dashboard (single page)

For each run batch:

1. Top-N worst tuples by `P95(L/I)`
2. Top-N worst REF fields (ODC-normalized)
3. Top-N worst ODC weights (REF-normalized)
4. Beam risk bar chart (beams ranked by instability)

Purpose: quickly identify where to drill down.

## 6.2 Tier-2: Isolation panels

### Panel A: “Is this REF?”
- Facet by ODC
- X=beam, Y=`L/I`, color=`REF_FIELDNAME`, marker/group by `SB_REF`
- plus `REF_FIELDNAME`-vs-baseline deltas

### Panel B: “Is this ODC?”
- Facet by `REF_FIELDNAME`
- X=beam, Y=`L/I`, color=ODC
- plus ODC-vs-baseline deltas

### Panel C: bpcal vs lcal comparison
- scatter of `L/I_bpcal` vs `L/I_lcal` per beam/tuple
- residual issue after lcal indicates deeper problem

## 6.3 Tier-3: Tuple drill-down

For a selected tuple:
- existing combined PDF/movies/stats from `combine_beam_outputs.py`
- plus contextual comparison strips:
   - same ODC, other field names (and same-field other `SB_REF` runs)
   - same field name, other ODCs

---

## 8) Spatial diagnostics extension (RA/Dec + offset grid + PAF clues)

This extension adds the beam-footprint geometry dimension to help detect clustered leakage patterns.

Core idea:
- For each tuple/SB_REF, plot beam-level leakage on sky footprint coordinates.
- If high-leakage beams cluster spatially (especially in neighboring beams), this may indicate shared beamforming/PAF-path effects rather than isolated sky effects.

### 8.0 Metadata source of truth (operational decision)

Decision (agreed for planning):
- Use tuple-generated metadata produced during stage-1 processing under each tuple directory, e.g.
   - `ODC-5241/SB_REF-81185_SB_1934-77045_SB_HOLO-76554_AMP_STRATEGY-multiply-insituPreflags/metadata/`
- Treat this tuple-level `metadata/` as the source of truth for spatial diagnostics.

Implication for pipeline flow:
- Stage-4 (`copy_and_combine_assessment_results.sh`) should copy tuple `metadata/` from remote HPC alongside `assessment_results/` for every selected tuple.
- This is a **deferred implementation item** (recorded here, not implemented yet).

Why this is preferred:
- avoids manual metadata tinkering,
- preserves exact processing-context metadata per tuple,
- keeps provenance tied to the same tuple that produced leakage outputs.

### 8.1 Required metadata inputs

Use tuple-local copied metadata in each tuple path:

- `<LOCAL_BASE>/ODC-.../SB_REF-.../metadata/`

Populate at least:

1. **SB_REF pointing metadata**
   - SB_REF
   - footprint center RA/Dec
   - optional rotation/parallactic context (if needed)

2. **Beam footprint geometry metadata**
   - beam index (0..35)
   - RA/Dec for each beam center, or
   - relative offsets (`delta_ra`, `delta_dec`) from footprint center

3. **Optional PAF/beamforming mapping metadata**
   - beam index to port group/channel map
   - neighboring-beam / shared-port relationships

### 8.2 Spatial plots to produce

1. **Absolute sky plot (RA/Dec)**
   - points at beam centers
   - color = `L/I` (or selected metric)
   - optional labels: beam number

2. **Relative offset footprint plot**
   - X=`delta_ra`, Y=`delta_dec`
   - same color encoding
   - best for cross-SB_REF comparison when center differs

3. **Cluster overlay view**
   - highlight beams above threshold
   - nearest-neighbor links or convex hull around high-leakage subset
   - optional PAF-port overlay when mapping metadata is available

4. **Comparative spatial panels**
   - Fix ODC, vary field (one panel per field)
   - Fix field, vary ODC (one panel per ODC)

### 8.3 Spatial summary outputs

- `spatial_beam_leakage_points.csv`
  - keys: `manifest_index`, `sb_ref`, `ref_fieldname`, `odc_weight`, `beam`, `variant`
  - values: `ra_deg`, `dec_deg`, `delta_ra_deg`, `delta_dec_deg`, `l_over_i_pct`, `q_over_i_pct`, `u_over_i_pct`, `v_over_i_pct`

- `spatial_cluster_summary.csv`
  - keys: `manifest_index`, `sb_ref`, `variant`
  - values: `n_high_beams`, `largest_cluster_size`, `mean_neighbor_distance_high`, `cluster_compactness`

### 8.4 Animation products

Generate animated spatial sequences to reveal stable vs changing patterns:

1. **By SB_REF (fixed metric, fixed variant)**
   - frame = one SB_REF tuple
   - useful for identifying repeated hotspot regions

2. **By ODC for fixed field**
   - frame = one ODC
   - isolates ODC-driven footprint changes

3. **By field for fixed ODC**
   - frame = one field name
   - isolates field-driven footprint changes

Recommended outputs:
- `spatial_footprint_by_sbref.gif` / `.mp4`
- `spatial_footprint_by_odc_<field>.gif` / `.mp4`
- `spatial_footprint_by_field_<odc>.gif` / `.mp4`

### 8.5 Interpretation guidance

- **Localized contiguous hotspots** in neighboring beams: suspect common beamforming/PAF pathway.
- **Same sky-region pattern across multiple SB_REF instances**: supports REF-field (sky/model) hypothesis.
- **Pattern shifts with ODC while field fixed**: supports ODC-side hypothesis.
- **No clear spatial coherence**: may indicate non-spatial/systematic noise or metadata mismatch.

### 8.6 Deferred implementation notes for stage-4 metadata fetch

Additions to `copy_and_combine_assessment_results.sh` (future work):

1. Copy behavior
   - Current: copy `assessment_results/`
   - Future: also copy sibling `metadata/` directory for each tuple

2. CLI controls (proposed)
   - `--copy-metadata` (default: enabled)
   - `--metadata-only` (optional utility mode)

3. Local layout (proposed)
   - Keep copied metadata adjacent to assessment outputs under same tuple tree:
     - `.../SB_REF-.../metadata/`

4. Validation checks (proposed)
   - Warn/error if `assessment_results/` exists but tuple `metadata/` missing
   - Record per-tuple metadata completeness in a summary report

This keeps spatial diagnostics reproducible and tied to the exact processed tuple context.

---

## 9) Quantitative decision rules (initial proposal)

Use robust thresholds (tunable):

- **REF suspect** if, for fixed ODC:
  - median beam-delta > `T_ref` and
  - affected beams count > `N_ref`
- **ODC suspect** if, for fixed REF:
  - ODC beam spread > `T_odc` for > `N_odc` beams
- **Inconclusive** if only unstable beams are affected

Start with empirical thresholds from historical baseline:
- `T_ref = 2 * MAD_beam`
- `T_odc = 2 * MAD_beam`

Then refine after first batch.

---

## 10) Execution phases (no-code planning)

Status legend:
- [x] Completed
- [ ] Planned / not started

## [x] Stage-0 — Stage-4 metadata copy plumbing

- [x] Added a metadata-copy switch in stage-4 copy/combine flow.
- [x] Behavior: when switch is ON, copy tuple sibling `metadata/` from remote HPC.
- [x] Optimization: if local tuple `metadata/` already exists, skip remote metadata fetch even when switch is ON.
- [x] Path derivation uses manifest-driven tuple paths (same source as `assessment_results/`).

Stage-0 outcome:
- Metadata ingestion path is now available for phased implementation on selected index ranges.

## [x] Phase 0 — Data inventory and completeness (MVP subset)

- Enumerate all `assessment_results/` directories copied locally.
- Enumerate all tuple `metadata/` directories copied locally (same tuple set as assessment outputs).
- Validate expected beam coverage (0–35) for bpcal + lcal text files.
- Validate metadata presence/completeness per tuple and record missing fields.
- Report missingness matrix by tuple and beam.

Deliverable: completeness report.

Phase-0 MVP status:
- Completed for subset indices `14-35` excluding `24-29`.
- Artifact: `projects/calibration-updates-2026/reports/phase0_mvp_completeness_14-35_excl_24-29.md`
- Artifact: `projects/calibration-updates-2026/reports/phase0_mvp_completeness_14-35_excl_24-29.csv`
- Summary: `16/16` tuple directories present, `16/16` metadata directories present, `16/16` tuples with >=36 bpcal beam txt, `16/16` tuples with >=36 lcal beam txt.

Full-scope Phase-0 status:
- [ ] Pending for non-MVP indices outside the initial rollout subset.

## [x] Phase 1 — Canonical extraction table (MVP subset)

- Parse tuple metadata from directory names + manifest.
- Parse footprint/beam geometry metadata from each tuple `metadata/` directory.
- Do **not** hardcode footprint pitch; read per-tuple pitch from `schedblock-info-<SB_REF>.txt` (`common.target.src%d.footprint.pitch` or `weights.footprint_pitch`).
- Perform a per-tuple sanity check by comparing pitch-derived expected nearest-neighbour spacing with footprint offset geometry; record pass/fail and residual.
- Parse leakage metrics from text headers.
- Emit canonical row-per-beam dataset.

Deliverable: analysis-ready table.

Phase-1 MVP status:
- Completed for subset indices `14-35` excluding `24-29`.
- Artifact: `/Users/raj030/DATA/reffield-average/leakage_master_table.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase1_mvp_extraction_summary.md`
- Summary: `1152/1152` rows parsed (`16 tuples × 36 beams × 2 variants`), dynamic pitch parsed for `16/16` tuples, pitch sanity pass `16/16`.
- Implementation: `projects/calibration-updates-2026/scripts/build_phase1_master_table.py`

Full-scope Phase-1 status:
- [ ] Pending for non-MVP indices outside the initial rollout subset.

## [x] Phase 2 — REF/ODC isolation summaries (MVP subset)

- Generate REF-held-ODC and ODC-held-REF comparison outputs.
- Compute robust scores and suspect rankings.

Deliverable: root-cause summary pack.

Phase-2 MVP status:
- Completed for subset indices `14-35` excluding `24-29`.
- Artifact: `/Users/raj030/DATA/reffield-average/phase2/beam_x_field_at_fixed_odc.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase2/field_effect_scores_at_fixed_odc.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase2/beam_x_odc_at_fixed_field.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase2/odc_effect_scores_at_fixed_field.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase2/phase2_mvp_summary.md`
- Summary: generated fixed-ODC/fixed-field beam tables and score tables for both `bpcal` and `lcal` variants.
- Implementation: `projects/calibration-updates-2026/scripts/build_phase2_isolation_tables.py`

Full-scope Phase-2 status:
- [ ] Pending for non-MVP indices outside the initial rollout subset.

## [x] Phase 3 — Operator dashboard + review loop (MVP subset)

- Produce triage dashboard and drill-down shortlist.
- Review flagged cases with science team.
- Tune thresholds and scoring.

Deliverable: validated operational workflow.

Phase-3 MVP status:
- Completed initial HTML-first operator report for subset indices `14-35` excluding `24-29`.
- Artifact: `/Users/raj030/DATA/reffield-average/phase3/index.html`
- Artifact: `/Users/raj030/DATA/reffield-average/phase3/tables/beam_x_field_at_fixed_odc.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase3/tables/field_effect_scores_at_fixed_odc.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase3/tables/beam_x_odc_at_fixed_field.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase3/tables/odc_effect_scores_at_fixed_field.csv`
- Artifact: `/Users/raj030/DATA/reffield-average/phase3/tables/phase2_mvp_summary.md`
- Summary: single-page report with relative links and top-N REF/ODC effect previews for `bpcal` and `lcal`.
- Implementation: `projects/calibration-updates-2026/scripts/build_phase3_html_report.py`

Full-scope Phase-3 status:
- [ ] Pending for non-MVP indices and additional plot/media embedding.

## 10.1 MVP rollout scope (already processed HPC subset)

Implement first on these manifest index blocks only:

- `14-18` (ODC-5229)
- `19-23` (ODC-5231)
- `30-35` (ODC-5241)

Execution checklist:

1. **Subset copy stage**
   - Copy `assessment_results/` and tuple `metadata/` for the three index blocks.
   - Produce a tuple-level completeness table (`assessment + metadata`).

2. **MVP extraction stage**
   - Build `leakage_master_table.csv` for only those tuples.
   - Validate row counts: expected `n_tuple × n_beam × n_variant` (minus documented missing files).

3. **MVP comparison stage**
   - Run 5.1 (Fix ODC, vary field) and 5.2 (Fix field, vary ODC) on subset only.
   - Emit fixed-ODC/fixed-field comparison tables and score tables.

4. **MVP spatial stage**
   - Produce static RA/Dec and offset-grid plots.
   - Add one GIF/MP4 sweep (start with `by SB_REF`).

5. **MVP sign-off stage**
   - Confirm at least one interpretable REF-field pattern and one ODC pattern (or explicit inconclusive result with reasons).
   - Freeze plot conventions before scaling to all indices.

## 10.2 HTML-first deliverable requirement

All analysis outputs must be browsable from a single HTML entry page with clickable links and embedded previews.

Proposed output layout:

- `analysis_results/`
  - `index.html` (entry page)
  - `tables/` (CSV summary tables)
  - `figures/` (PNG/PDF plots)
  - `animations/` (GIF/MP4)

HTML requirements:

1. `index.html` uses **relative paths only** (no absolute local paths).
2. Every generated figure/table has a clickable link from the index.
3. Key PNG/GIF visuals are embedded inline for quick inspection.
4. Broken-link check is part of generation validation.
5. If output folder is moved/copied as a whole, links remain valid.

Minimum HTML sections:

- Run scope summary (indices, tuple count, ODC groups, field names)
- Data completeness summary
- 5.1 results (fixed ODC, vary field)
- 5.2 results (fixed field, vary ODC)
- Spatial diagnostics gallery
- Animations section
- Known caveats/missing-data notes

---

## 11) Suggested output artifacts

1. `leakage_master_table.csv`
2. `summary_ref_effect.csv`
3. `summary_odc_effect.csv`
4. `beam_stability_profile.csv`
5. `triage_dashboard.pdf`
6. `casebook/` with top suspect tuple comparisons
7. `spatial_beam_leakage_points.csv`
8. `spatial_cluster_summary.csv`
9. spatial GIF/MP4 products for SB_REF/ODC/field sweeps
10. `analysis_results/index.html` (single entry-point report with relative links)

---

## 12) Risks and mitigations

1. **Incomplete tuples/beam files**
   - Mitigate with explicit completeness scoring and NA-aware stats.
2. **Confounding by strategy changes** (`AMP_STRATEGY`, `DO_PREFLAG_REFTABLE`)
   - Always stratify or include as grouping keys.
3. **Small sample counts for certain ODC/REF combinations**
   - Require minimum sample thresholds before ranking.
4. **Overreacting to known unstable beams**
   - Beam stability weighting before root-cause attribution.
5. **Incorrect footprint/metadata alignment**
   - Validate beam-index mapping and coordinate reference conventions before spatial interpretation.

---

## 13) Review checklist before implementation

- [ ] Confirm primary KPI is `L/I` (with `Q/I`, `U/I`, `V/I` as secondary diagnostics).
- [ ] Confirm thresholds and minimum sample sizes.
- [ ] Confirm preferred outputs (CSV only vs dashboard PDFs).
- [ ] Confirm whether `.lcal` should be used for ranking or only diagnostic cross-check.
- [ ] Confirm whether to include historical runs outside current manifest.
- [ ] Confirm coordinate convention and sign for RA/Dec offsets used in footprint plots.
- [ ] Confirm available PAF-port mapping metadata scope (beam-level vs sub-beam detail).
- [ ] Confirm HTML report style (embedded previews vs links-only for heavy media).

---

## 14) Minimal first pilot (recommended)

Start with manifest indices that already have broad ODC/REF coverage.

Pilot objective:
- prove the framework can clearly separate at least one REF-driven and one ODC-driven anomaly pattern.

Pilot success criteria:
- same anomaly flagged by both numerical ranking and visual comparison,
- and interpretable by beam-level evidence.

---

## 15) Why this will work for your specific setup

- Your naming scheme already encodes the exact causal dimensions needed.
- Your text headers already provide the leakage metrics needed for robust comparison.
- Your current combine products already provide per-tuple visual context.
- The missing piece is a **cross-tuple, beam-aware comparative layer**, which this plan structures explicitly.
