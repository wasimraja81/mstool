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
<p>We define two observables from the 1934&minus;638 measurements:</p>
$$\\gamma = \\frac{YY^{ic}}{XX^{ic}} = \\frac{G_y^{ic}}{G_x^{ic}} \\tag{VI}$$
$$dQ = \\frac{Q^{ic}}{I^\\circ} = \\tfrac{1}{2}\\bigl(G_x^{ic} - G_y^{ic}\\bigr) \\tag{VII}$$
<p>We have two unknowns ($G_x^{ic}$, $G_y^{ic}$) and two independent equations &mdash;
the system is uniquely determined. Substituting $G_y^{ic} = \\gamma G_x^{ic}$ from (VI) into (VII):</p>
$$G_x^{ic}\\,(1-\\gamma) = 2\\,dQ$$
$$\\boxed{G_x^{ic} = \\frac{2\\,dQ}{1-\\gamma}, \\qquad G_y^{ic} = \\frac{2\\gamma\\,dQ}{1-\\gamma}} \\tag{VIII}$$
<p>Both gains are fully determined by the two observables $dQ$ and $\\gamma$,
measured directly from the 1934&minus;638 data after interim calibration.</p>
<hr>
<h2>5. Final Calibration Table</h2>
<p>From (III), any raw measurement $XX_{\\rm target}^m$ is related to the true sky by
<em>both</em> $G_x^m$ and $G_x^{ic}$:</p>
$$XX_{\\rm target}^m = G_x^m \\cdot G_x^{ic} \\cdot XX^\\circ$$
<p>We already hold $g_x^m$ (the voltage gain) in the bandpass table, and we have now
derived the correction factor $G_x^{ic}$ from the 1934&minus;638 data above.
The combined voltage gain that removes both factors is:</p>
$$g_x^f = g_x^m \\cdot \\sqrt{G_x^{ic}} = g_x^m \\cdot \\sqrt{\\frac{2\\,dQ}{1-\\gamma}} \\tag{IX}$$
$$g_y^f = g_y^m \\cdot \\sqrt{G_y^{ic}} = g_y^m \\cdot \\sqrt{\\frac{2\\gamma\\,dQ}{1-\\gamma}}$$
<p>The $\\sqrt{\\cdot}$ converts $G_x^{ic}$ from the correlation (power) domain in which
it was derived back to the voltage domain in which bandpass tables operate.
Applying $g^f$ to any new target data gives:</p>
$$\\frac{XX_{\\rm target}^m}{|g_x^f|^2} = \\frac{G_x^m \\cdot G_x^{ic} \\cdot XX^\\circ}{G_x^m \\cdot G_x^{ic}} = XX^\\circ$$
<p>The updated table $g^f$ replaces the interim bandpass table and is applied directly
to uncalibrated data &mdash; no intermediate calibration step is required.</p>
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
