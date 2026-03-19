"""
Generates gain_calibration_strategy.html — a self-contained KaTeX document
explaining the bandpass gain calibration strategy.

Can be run standalone:
    python3 write_gain_calibration_strategy.py [output_path]

Or imported and called from the report builder:
    from write_gain_calibration_strategy import generate
    generate(output_dir / "gain_calibration_strategy.html")
"""

from pathlib import Path
import sys

HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Gain Calibration Strategy</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"
  onload="renderMathInElement(document.body,{delimiters:[
    {left:'$$',right:'$$',display:true},
    {left:'$',right:'$',display:false}]})">
</script>
<style>
body{font-family:Georgia,serif;max-width:800px;margin:60px auto;padding:0 20px;line-height:1.7;color:#222}
h1{font-size:1.6em;border-bottom:2px solid #444;padding-bottom:8px}
h2{font-size:1.2em;margin-top:2em;color:#333;border-left:4px solid #888;padding-left:10px}
hr{border:none;border-top:1px solid #ccc;margin:2em 0}
.obj{background:#eef4fb;border-left:3px solid #5a8fc4;padding:10px 16px;font-size:.92em;color:#1a3050;margin:1.2em 0}
ul{margin-top:.3em} p{margin:.6em 0}
</style>
</head>
<body>
<h1>Gain Calibration Strategy</h1>
<div class="obj">
<strong>Objective.</strong>
During bandpass calibration we derive <em>voltage</em> gains
$g_x$ and $g_y$ that are stored in the bandpass table.
The corresponding <em>correlation-space</em> gains are
$$G_x^m = g_x \\, g_x^* = |g_x|^2, \\qquad G_y^m = g_y \\, g_y^* = |g_y|^2.$$
After applying these gains, the corrected parallel-hand correlations of the
unpolarised source 1934&minus;638 should satisfy
$$Q = XX^{ic} - YY^{ic} = 0.$$
If $Q \\neq 0$, the initial gain derivation contains errors. We model and quantify
these using 1934&minus;638 measurements, and use them to update $g_x$, $g_y$ in
the bandpass table. Note: $G$ operates on <em>correlations</em>; $g$ operates on <em>voltages</em>.
</div>
<hr>
<h2>1. Initial Measurement Stage</h2>
<p>The measured parallel-hand correlations are related to the true (ideal, superscript $\\circ$)
values by the correlation-space measurement gains $G_x^m$ and $G_y^m$:</p>
$$XX^m = G_x^m \\, XX^\\circ \\tag{I}$$
$$YY^m = G_y^m \\, YY^\\circ \\tag{II}$$
<p>where $G_x^m = g_x g_x^* = |g_x|^2$ and $G_y^m = g_y g_y^* = |g_y|^2$
($g$ acts on voltages; $G$ acts on correlations).</p>
<hr>
<h2>2. Interim Calibration Stage</h2>
<p>We attempt to correct the measured data by dividing out the measurement gain,
producing the <em>interim-calibrated</em> visibility $XX^{ic}$:</p>
$$XX^{ic} = \\frac{1}{G_x^m} \\cdot XX^m = G_x^{ic} \\cdot XX^\\circ \\tag{III}$$
$$YY^{ic} = \\frac{1}{G_y^m} \\cdot YY^m = G_y^{ic} \\cdot YY^\\circ$$
<p>The residual $G_x^{ic}$ captures how imperfect the correction was.
If the correction were perfect, $G_x^{ic} = 1$ and $XX^{ic} = XX^\\circ$ exactly.
The goal is to measure and remove $G_x^{ic}$ and $G_y^{ic}$.</p>
<hr>
<h2>3. Analysis of Source 1934&minus;638</h2>
<p>1934&minus;638 is unpolarised, so $Q^\\circ = XX^\\circ - YY^\\circ = 0$ and each
polarisation carries half the total intensity: $XX^\\circ = YY^\\circ = \\tfrac{1}{2}I^\\circ$.
Substituting into (III):</p>
$$XX^{ic} = G_x^{ic} \\cdot \\tfrac{1}{2}I^\\circ \\tag{IV}$$
$$YY^{ic} = G_y^{ic} \\cdot \\tfrac{1}{2}I^\\circ \\tag{V}$$
<p>Adding and subtracting:</p>
$$I^{ic} = XX^{ic} + YY^{ic} = \\tfrac{1}{2}\\bigl(G_x^{ic} + G_y^{ic}\\bigr)\\,I^\\circ$$
$$Q^{ic} = XX^{ic} - YY^{ic} = \\tfrac{1}{2}\\bigl(G_x^{ic} - G_y^{ic}\\bigr)\\,I^\\circ$$
<hr>
<h2>4. Solving for $G_x^{ic}$ and $G_y^{ic}$</h2>
<p>The two equations at the end of &sect;3 have two unknowns. Adding and subtracting them directly:</p>
$$G_x^{ic} = \\frac{I^{ic} + Q^{ic}}{I^\\circ} \\tag{VI}$$
$$G_y^{ic} = \\frac{I^{ic} - Q^{ic}}{I^\\circ} \\tag{VII}$$
<p>This is the exact, assumption-free result. Both gains are fully determined by
three measurables: $I^{ic}$, $Q^{ic}$ (from 1934&minus;638 after interim calibration),
and $I^\circ$ (the known true flux of 1934&minus;638).
Defining $dQ = Q^{ic}/I^{ic}$, these can be written:</p>
$$G_x^{ic} = \\frac{I^{ic}}{I^\\circ}\\,(1 + dQ), \\qquad G_y^{ic} = \\frac{I^{ic}}{I^\\circ}\\,(1 - dQ) \\tag{VIII}$$
<p>The prefactor $I^{ic}/I^\circ$ is the flux-scale accuracy of the interim calibration.
If total-intensity has been correctly calibrated so that $I^{ic} = I^\circ$, this
prefactor is unity and (VIII) simplifies to:</p>
$$G_x^{ic} = 1 + dQ, \\qquad G_y^{ic} = 1 - dQ \\qquad \\text{(when } I^{ic}/I^\\circ = 1\\text{)} \\tag{IX}$$
<p>In this case $dQ$ alone determines both gain errors. If $I^{ic}/I^\\circ \\neq 1$,
using (IX) would absorb a flux-scale error into the bandpass table; the full
form (VIII) must be used instead, requiring an independent measurement of
$I^\circ$ (e.g. a flux model of 1934&minus;638).</p>
<hr>
<h2>5. Final Calibration Table</h2>
<p>From (III), any raw measurement $XX_{\\rm target}^m$ is related to the true sky by
<em>both</em> $G_x^m$ and $G_x^{ic}$:</p>
$$XX_{\\rm target}^m = G_x^m \\cdot G_x^{ic} \\cdot XX^\\circ$$
<p>We already hold $g_x^m$ (the voltage gain) in the bandpass table, and we have now
derived the correction factor $G_x^{ic}$ from the 1934&minus;638 data above.
The combined voltage gain that removes both factors is:</p>
$$g_x^f = g_x^m \\cdot \\sqrt{G_x^{ic}} = g_x^m \\cdot \\sqrt{\\frac{I^{ic}}{I^\\circ}\\,(1+dQ)} \\tag{X}$$
$$g_y^f = g_y^m \\cdot \\sqrt{G_y^{ic}} = g_y^m \\cdot \\sqrt{\\frac{I^{ic}}{I^\\circ}\\,(1-dQ)}$$
<p>When $I^{ic}/I^\\circ = 1$, these simplify to $g_x^f = g_x^m\\sqrt{1+dQ}$,
$g_y^f = g_y^m\\sqrt{1-dQ}$.
The $\\sqrt{\\cdot}$ converts $G_x^{ic}$ from the correlation (power) domain in which
it was derived back to the voltage domain in which bandpass tables operate.
Applying $g^f$ to any new target data gives:</p>
$$\\frac{XX_{\\rm target}^m}{|g_x^f|^2} = \\frac{G_x^m \\cdot G_x^{ic} \\cdot XX^\\circ}{G_x^m \\cdot G_x^{ic}} = XX^\\circ$$
<p>The updated table $g^f$ replaces the interim bandpass table and is applied directly
to uncalibrated data &mdash; no intermediate calibration step is required.</p>
<hr>
<h2>6. Accessing the correction factors</h2>
<p>The pipeline produces two files alongside the per-field line plots in
<code>&lt;data-root&gt;/phase3/plots/</code>:</p>
<ul>
  <li><code>dq_du_correction_factors.csv</code> &mdash; machine-readable, one row per
      (field, variant, beam) triple; suitable for pandas/numpy consumption by
      downstream processing scripts.</li>
  <li><code>dq_du_correction_factors.txt</code> &mdash; fixed-width ASCII companion;
      human-readable and greppable without Python.</li>
</ul>
<h3>6.1 Column schema</h3>
<table>
  <thead><tr><th>Column</th><th>Type</th><th>Description</th></tr></thead>
  <tbody>
    <tr><td><code>field</code></td><td>str</td><td>Reference field name, e.g. <code>REF_1324-28</code></td></tr>
    <tr><td><code>variant</code></td><td>str</td><td><code>bpcal</code> (bandpass-cal measurement) or <code>lcal</code> (leakage-cal measurement)</td></tr>
    <tr><td><code>beam</code></td><td>int</td><td>ASKAP beam index, 0-based (0&ndash;35 for closepack36)</td></tr>
    <tr><td><code>mean_dQ</code></td><td>float, %</td><td>Mean signed $dQ/I$ leakage averaged across all SB_REF &times; ODC observations</td></tr>
    <tr><td><code>std_dQ</code></td><td>float, %</td><td>Standard deviation of $dQ/I$ across observations &mdash; indicates repeatability</td></tr>
    <tr><td><code>mean_dU</code></td><td>float, %</td><td>Mean signed $dU/I$ (present when <code>--dU</code> was passed to <code>plot_dQ_vs_beam.py</code>)</td></tr>
    <tr><td><code>std_dU</code></td><td>float, %</td><td>Standard deviation of $dU/I$</td></tr>
    <tr><td><code>n_obs</code></td><td>int</td><td>Number of (SB_REF, ODC) rows averaged for this beam</td></tr>
  </tbody>
</table>
<p>The CSV begins with <code>#</code>-prefixed comment lines that document the schema and
usage pattern; these are skipped automatically by pandas when
<code>comment='#'</code> is passed.</p>
<h3>6.2 Reading the table</h3>
<pre><code class="language-python">import pandas as pd

df = pd.read_csv("phase3/plots/dq_du_correction_factors.csv", comment="#")

# Per-beam lookup for a specific field, variant and beam
row = df[
    (df.field   == "REF_1324-28") &
    (df.variant == "bpcal") &
    (df.beam    == 12)
].iloc[0]
dq, dq_std = row.mean_dQ, row.std_dQ   # fractional Stokes-Q leakage, %
du, du_std = row.mean_dU, row.std_dU   # fractional Stokes-U leakage, %

# All 36 beams as a numpy array (for vectorised correction)
sub = df[
    (df.field   == "REF_1324-28") &
    (df.variant == "bpcal")
].sort_values("beam")
dq_array = sub.mean_dQ.to_numpy()   # shape (36,)
</code></pre>
<h3>6.3 Applying the correction</h3>
<p>From equation&nbsp;(X), the corrected bandpass voltage gain for beam $b$ is:</p>
$$g_x^f[b] = g_x^m[b]\,\sqrt{1 + dQ[b]/100}$$
$$g_y^f[b] = g_y^m[b]\,\sqrt{1 - dQ[b]/100}$$
<p>where $dQ[b]$ is <code>mean_dQ</code> for that beam (in percent, so the division by 100
converts to a fractional correction).  The $\sqrt{\cdot}$ converts from the
correlation (power) domain back to the voltage domain required by the bandpass
table.</p>
<p>The <code>std_dQ</code> and <code>n_obs</code> columns allow a downstream script to propagate
uncertainty or to apply a beam-quality threshold (e.g. reject beams with
$\\sigma_{dQ} \\gt 1\\%$ or $n_{\\mathrm{obs}} \\lt 3$) before applying the correction.</p>
</body>
</html>
"""


def generate(output_path: Path) -> None:
    """Write the gain calibration strategy HTML to *output_path*."""
    Path(output_path).write_text(HTML)


if __name__ == "__main__":
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/Users/raj030/Downloads/gain_calibration_strategy.html")
    generate(dest)
    print(f"Written: {dest}")
