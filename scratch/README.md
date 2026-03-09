# scratch workspace

Use this directory as the working launch location for ad-hoc runs, temporary manifests, logs, and helper outputs.

Examples (from this directory):

```bash
# Create a one-row local manifest for idx=2
../projects/calibration-updates-2026/scripts/make_single_index_manifest.sh \
  --index 2 \
  --output /tmp/mstool_manifest_idx2.txt

# Run stage-3 locally using that manifest
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest /tmp/mstool_manifest_idx2.txt
```

All additional files created under `scratch/` are intentionally ignored by git.
