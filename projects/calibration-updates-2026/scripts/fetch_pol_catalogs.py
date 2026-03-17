"""
fetch_pol_catalogs.py
=====================
Fetch polarised-source and pulsar catalogs for a given sky field and cache
them as CSV files.  Called by plot_paf_beam_overlay.py and
plot_paf_beam_movie.py via --pol-sources.

Catalog priority
----------------
Extragalactic sources (first that returns data wins):

  1. POSSUM AS203 – selavy polarisation VOTable downloaded via CASDA obscore
     (``collection = 'POSSUM'``, file pattern ``selavy*polarisation.xml``).
     Requires CASDA credentials (see "CASDA credentials" below).
     Best available data – use this where released tiles overlap the field.

  2. POSSUM pilot (AS103) – CASDA TAP table
     ``AS103.combined_medfilt_rmtable_catalogue_v01``
     (unauthenticated, public).  Covers only RA ~329-335°, Dec ~-52 to -49°.

  3. Taylor, Stil & Sunstrum 2009 – VizieR J/ApJ/702/1230/catalog
     (NVSS RM catalogue, Dec > -40°, ~37 000 sources – covers all ref fields).
     Used as the fallback when no POSSUM data is available.

Pulsars (always attempted, unauthenticated):
  ATNF Pulsar Catalogue via VizieR B/psr/psr.  Only pulsars with a measured
  RM are kept.

CASDA credentials
-----------------
The POSSUM AS203 fetch (priority 1) needs a CASDA account.  Provide your
credentials in *one* of these ways – the code checks in this order:

  a) Environment variables (recommended for scripts / automation)::

       export CASDA_USER="firstname.lastname@institution.edu"
       export CASDA_PASSWORD="your_casda_password"

  b) ~/.netrc entry (persistent, never need to set env again)::

       machine casda.csiro.au
           login firstname.lastname@institution.edu
           password your_casda_password

     Add those three lines to ``~/.netrc`` and set permissions::

       chmod 600 ~/.netrc

  c) If neither is set the AS203 fetch is silently skipped and the code
     falls back to AS103 pilot / Taylor 2009.

To force-refresh the cache after setting credentials (so AS203 replaces the
previously cached Taylor 2009 data)::

  python plot_paf_beam_overlay.py ... --pol-sources --refresh-catalogs

Standardised output columns (both DataFrames)
---------------------------------------------
  ra_deg      float  Right Ascension [deg, ICRS]
  dec_deg     float  Declination [deg, ICRS]
  rm          float  Rotation measure [rad m⁻²]
  rm_err      float  Uncertainty in RM [rad m⁻²]
  flux_mjy    float  Stokes I flux density [mJy]   (NaN if unavailable)
  frac_pol    float  Fractional linear polarisation [0–1] (NaN if unavailable)
  name        str    Source name / identifier

Caching
-------
Results written to <catalog_dir>/<field_name>_extgal.csv and _pulsar.csv.
Re-used on subsequent runs unless --refresh-catalogs is passed.
"""

import re
import warnings
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Helpers – parse schedblock field_direction
# ---------------------------------------------------------------------------

def parse_field_direction(field_dir_str: str) -> Tuple[float, float]:
    """
    Convert  '[HH:MM:SS.ss,±DD:MM:SS.ss,J2000]'  to (ra_deg, dec_deg).

    Handles optional spaces around the comma.
    """
    # Strip brackets and the J2000 epoch
    s = field_dir_str.strip().lstrip("[").rstrip("]")
    parts = [p.strip() for p in s.split(",")]
    ra_str, dec_str = parts[0], parts[1]

    def hms2deg(h, m, s_):
        return (h + m / 60.0 + s_ / 3600.0) * 15.0

    def dms2deg(sign, d, m, s_):
        return sign * (d + m / 60.0 + s_ / 3600.0)

    # RA
    ra_match = re.match(r"(\d+):(\d+):([\d.]+)", ra_str)
    if not ra_match:
        raise ValueError(f"Cannot parse RA from '{ra_str}'")
    ra_deg = hms2deg(int(ra_match.group(1)),
                     int(ra_match.group(2)),
                     float(ra_match.group(3)))

    # Dec
    dec_match = re.match(r"([+-]?)(\d+):(\d+):([\d.]+)", dec_str)
    if not dec_match:
        raise ValueError(f"Cannot parse Dec from '{dec_str}'")
    sign    = -1.0 if dec_match.group(1) == "-" else 1.0
    dec_deg = dms2deg(sign,
                      int(dec_match.group(2)),
                      int(dec_match.group(3)),
                      float(dec_match.group(4)))

    return ra_deg, dec_deg


def read_field_direction(schedblock_path: str) -> Optional[Tuple[float, float]]:
    """
    Read  common.target.src1.field_direction  from a schedblock-info file
    and return (ra_deg, dec_deg).  Returns None if not found.
    """
    path = Path(schedblock_path)
    if not path.exists():
        return None
    pat = re.compile(r"common\.target\.src1\.field_direction\s*=\s*(.+)")
    with open(path) as fh:
        for line in fh:
            m = pat.match(line.strip())
            if m:
                try:
                    return parse_field_direction(m.group(1))
                except ValueError:
                    return None
    return None


# ---------------------------------------------------------------------------
# Extragalactic catalog fetch
# ---------------------------------------------------------------------------

_CASDA_TAP = "https://casda.csiro.au/casda_vo_tools/tap/sync"
_CASDA_TAP_ASYNC = "https://casda.csiro.au/casda_vo_tools/tap"
_CASDA_TABLE = "AS103.combined_medfilt_rmtable_catalogue_v01"
_VIZIER_TAP = "https://TAPVizieR.cds.unistra.fr/TAPVizieR/tap/sync"
_TAYLOR_TABLE = '"J/ApJ/702/1230/catalog"'

# Flexible column name map for selavy polarisation VOTable
# Keys are our standard names, values are a priority-order list of possible
# column names found in POSSUM / ASKAP selavy polarisation catalogs.
_SELAVY_COL_MAP = {
    "ra_deg"   : ["col_ra_deg_cont", "ra_deg_cont", "ra", "RA"],
    "dec_deg"  : ["col_dec_deg_cont", "dec_deg_cont", "dec", "Dec"],
    "rm"       : ["col_rm", "rm", "RM", "rotation_measure"],
    "rm_err"   : ["col_rm_err", "rm_err", "e_RM", "rm_error"],
    "flux_mjy" : ["col_flux_int", "col_flux_peak", "stokesI",
                   "flux_int", "flux_peak", "col_stokesI_ref_freq"],
    "frac_pol" : ["col_fracpol", "col_frac_pol", "fracpol",
                   "frac_pol", "fractional_pol"],
    "name"     : ["col_component_id", "component_id", "col_source_id",
                   "source_id", "catalogue_id", "island_id"],
}


def _resolve_col(df_cols: list, candidates: list) -> Optional[str]:
    """Return the first candidate name that exists in df_cols, else None."""
    for c in candidates:
        if c in df_cols:
            return c
    return None


def _fetch_possum_as203_obscore(
    ra_deg: float, dec_deg: float, radius_deg: float
) -> Optional[pd.DataFrame]:
    """
    Fetch POSSUM AS203 selavy polarisation catalog for the nearest tile via
    CASDA obscore + astroquery.casda.

    Requires CASDA credentials – read from environment variables
    ``CASDA_USER`` and ``CASDA_PASSWORD``, or from ``~/.netrc`` (machine
    casda.csiro.au).

    Returns a standardised DataFrame, or None on any error / missing creds.
    """
    import os, io, netrc as _netrc_mod, tempfile, shutil
    try:
        from astroquery.utils.tap.core import Tap
        from astroquery.casda import Casda
        from astropy.io.votable import parse
    except ImportError as exc:
        warnings.warn(f"_fetch_possum_as203_obscore: missing dependency: {exc}")
        return None

    # --- credentials ---
    user = os.environ.get("CASDA_USER", "")
    pwd  = os.environ.get("CASDA_PASSWORD", "")
    if not user or not pwd:
        try:
            info = _netrc_mod.netrc()
            host_creds = info.authenticators("casda.csiro.au")
            if host_creds:
                user, _, pwd = host_creds
        except Exception:
            pass
    if not user or not pwd:
        warnings.warn(
            "POSSUM AS203 catalog: no CASDA credentials found. "
            "Set CASDA_USER and CASDA_PASSWORD env vars or add casda.csiro.au "
            "to ~/.netrc.  Skipping AS203 lookup."
        )
        return None

    # --- find selavy polarisation XML in obscore ---
    try:
        casda_tap = Tap(url=_CASDA_TAP_ASYNC)
        job = casda_tap.launch_job_async(
            "SELECT obs_id, filename, access_url, content_length "
            "FROM ivoa.obscore "
            "WHERE obs_collection = 'POSSUM' "
            "AND filename LIKE 'selavy%%polarisation.xml' "
            f"AND 1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
            f"CIRCLE('ICRS', {ra_deg:.4f}, {dec_deg:.4f}, {radius_deg:.2f}))"
        )
        obscore_rows = job.get_results()
    except Exception as exc:
        warnings.warn(f"POSSUM obscore query failed: {exc}")
        return None

    if not obscore_rows or len(obscore_rows) == 0:
        return None

    print(f"    POSSUM AS203: found {len(obscore_rows)} selavy-pol tile(s)")
    for row in obscore_rows:
        print(f"      {row['obs_id']}  {row['filename']}")

    # --- stage and download each matching file ---
    try:
        casda = Casda(username=user, password=pwd)
        staged_urls = casda.stage_data(obscore_rows, verbose=False)
    except Exception as exc:
        warnings.warn(f"POSSUM AS203 stage_data failed: {exc}")
        return None

    all_dfs = []
    for url in staged_urls:
        if not url or "checksum" in str(url):
            continue
        try:
            import urllib.request
            tmpdir = tempfile.mkdtemp(prefix="possum_as203_")
            fname  = os.path.join(tmpdir, "pol.xml")
            urllib.request.urlretrieve(str(url), fname)
            # parse VOTable
            vot  = parse(fname)
            tbl  = vot.get_first_table().to_table()
            df   = tbl.to_pandas()
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception as exc:
            warnings.warn(f"POSSUM AS203 download/parse failed: {exc}")
            continue

        cols = list(df.columns)

        def _get(key):
            c = _resolve_col(cols, _SELAVY_COL_MAP[key])
            return pd.to_numeric(df[c], errors="coerce").values if c else np.full(len(df), np.nan)

        rm_vals = _get("rm")
        # keep only rows with a measured RM
        mask = np.isfinite(rm_vals)
        if not np.any(mask):
            continue

        name_c = _resolve_col(cols, _SELAVY_COL_MAP["name"])
        names  = df[name_c].astype(str).values if name_c else np.full(len(df), "")

        out = pd.DataFrame({
            "ra_deg"   : _get("ra_deg")[mask],
            "dec_deg"  : _get("dec_deg")[mask],
            "rm"       : rm_vals[mask],
            "rm_err"   : _get("rm_err")[mask],
            "flux_mjy" : _get("flux_mjy")[mask],
            "frac_pol" : _get("frac_pol")[mask],
            "name"     : names[mask],
        })
        out["source"] = "POSSUM_AS203"
        all_dfs.append(out)

    if not all_dfs:
        return None
    result = pd.concat(all_dfs, ignore_index=True)
    return result if len(result) else None


def _fetch_possum_casda(ra_deg: float, dec_deg: float, radius_deg: float) -> Optional[pd.DataFrame]:
    """
    Cone-search the public POSSUM pilot RM table on CASDA TAP.
    Returns a standardised DataFrame, or None if no sources / network error.
    """
    adql = (
        f"SELECT ra, dec, rm, rm_err, stokesi, fracpol, catalogue_id "
        f"FROM {_CASDA_TABLE} "
        f"WHERE 1=CONTAINS(POINT('ICRS', ra, dec), "
        f"CIRCLE('ICRS', {ra_deg:.6f}, {dec_deg:.6f}, {radius_deg:.3f}))"
    )
    try:
        r = requests.post(
            _CASDA_TAP,
            data={"REQUEST": "doQuery", "LANG": "ADQL",
                  "FORMAT": "csv", "QUERY": adql},
            timeout=30,
        )
        r.raise_for_status()
    except Exception as exc:
        warnings.warn(f"CASDA TAP query failed: {exc}")
        return None

    try:
        import io
        df = pd.read_csv(io.StringIO(r.text))
    except Exception:
        return None

    if df.empty or "ra" not in df.columns or "rm" not in df.columns:
        return None

    out = pd.DataFrame({
        "ra_deg"   : df["ra"].values.astype(float),
        "dec_deg"  : df["dec"].values.astype(float),
        "rm"       : df["rm"].values.astype(float),
        "rm_err"   : df["rm_err"].values.astype(float),
        "flux_mjy" : df["stokesi"].values.astype(float) if "stokesi" in df.columns else np.full(len(df), np.nan),
        "frac_pol" : df["fracpol"].values.astype(float) if "fracpol" in df.columns else np.full(len(df), np.nan),
        "name"     : df["catalogue_id"].astype(str) if "catalogue_id" in df.columns else [""] * len(df),
    })
    out["source"] = "POSSUM_AS103"
    return out if len(out) else None


def _hms_to_deg(hms_str: str) -> float:
    """Convert 'HH MM SS.ss' or 'HH:MM:SS.ss' to decimal degrees (RA)."""
    parts = re.split(r"[\s:]+", str(hms_str).strip())
    h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
    return (h + m / 60.0 + s / 3600.0) * 15.0


def _dms_to_deg(dms_str: str) -> float:
    """Convert '+DD MM SS.ss' or '±DD:MM:SS.ss' to decimal degrees (Dec)."""
    s = str(dms_str).strip()
    sign = -1.0 if s.startswith("-") else 1.0
    s = s.lstrip("+-")
    parts = re.split(r"[\s:]+", s)
    d, m, sec = float(parts[0]), float(parts[1]), float(parts[2])
    return sign * (d + m / 60.0 + sec / 3600.0)


def _fetch_taylor_vizier(ra_deg: float, dec_deg: float, radius_deg: float) -> Optional[pd.DataFrame]:
    """
    Cone-search Taylor, Stil & Sunstrum 2009 (J/ApJ/702/1230) via astroquery.
    Returns standardised DataFrame or None.
    """
    try:
        from astropy.coordinates import SkyCoord
        import astropy.units as u
        from astroquery.vizier import Vizier

        coord = SkyCoord(ra=ra_deg, dec=dec_deg, unit="deg")
        viz = Vizier(columns=["**"], row_limit=-1)
        tables = viz.query_region(coord, radius=radius_deg * u.deg,
                                  catalog="J/ApJ/702/1230")
    except Exception as exc:
        warnings.warn(f"VizieR (Taylor) query failed: {exc}")
        return None

    if not tables:
        return None

    tbl = tables[0]
    if len(tbl) == 0:
        return None

    try:
        df = tbl.to_pandas()
    except Exception as exc:
        warnings.warn(f"Taylor table conversion failed: {exc}")
        return None

    # RAJ2000 / DEJ2000 arrive as sexagesimal strings from astroquery VizieR
    try:
        ra_vals  = df["RAJ2000"].apply(_hms_to_deg).values.astype(float)
        dec_vals = df["DEJ2000"].apply(_dms_to_deg).values.astype(float)
    except Exception:
        return None

    out = pd.DataFrame({
        "ra_deg"   : ra_vals,
        "dec_deg"  : dec_vals,
        "rm"       : pd.to_numeric(df["RM"],   errors="coerce").values,
        "rm_err"   : pd.to_numeric(df["e_RM"], errors="coerce").values,
        "flux_mjy" : pd.to_numeric(df["Si"],   errors="coerce").values if "Si" in df.columns else np.full(len(df), np.nan),
        "frac_pol" : pd.to_numeric(df["m"],    errors="coerce").values / 100.0 if "m" in df.columns else np.full(len(df), np.nan),
        "name"     : [""] * len(df),
    })
    out["source"] = "Taylor2009"
    return out if len(out) else None


def fetch_extgal(ra_deg: float, dec_deg: float, radius_deg: float = 3.5) -> Optional[pd.DataFrame]:
    """
    Fetch extragalactic polarised sources.  Priority order:
      1. POSSUM AS203 – selavy polarisation catalog via CASDA obscore (requires creds)
      2. POSSUM AS103 pilot – CASDA TAP
      3. Taylor et al. 2009 – VizieR fallback
    Returns None if all fail.
    """
    df = _fetch_possum_as203_obscore(ra_deg, dec_deg, radius_deg)
    if df is not None and len(df) > 0:
        print(f"    POSSUM AS203 selavy: {len(df)} sources")
        return df

    df = _fetch_possum_casda(ra_deg, dec_deg, radius_deg)
    if df is not None and len(df) > 0:
        print(f"    POSSUM CASDA (AS103): {len(df)} sources")
        return df

    df = _fetch_taylor_vizier(ra_deg, dec_deg, radius_deg)
    if df is not None and len(df) > 0:
        print(f"    Taylor 2009:  {len(df)} sources")
        return df

    warnings.warn("No extragalactic RM sources found from any catalog.")
    return None


# ---------------------------------------------------------------------------
# Pulsar catalog fetch
# ---------------------------------------------------------------------------

_PSR_TABLE = '"B/psr/psr"'


def fetch_pulsars(ra_deg: float, dec_deg: float, radius_deg: float = 3.5) -> Optional[pd.DataFrame]:
    """
    Fetch ATNF pulsars with measured RM via astroquery VizieR (B/psr).
    Returns standardised DataFrame (may be empty) or None on network error.
    """
    _empty = pd.DataFrame(columns=["ra_deg","dec_deg","rm","rm_err",
                                    "flux_mjy","frac_pol","name","source"])
    try:
        from astropy.coordinates import SkyCoord
        import astropy.units as u
        from astroquery.vizier import Vizier

        coord = SkyCoord(ra=ra_deg, dec=dec_deg, unit="deg")
        psr_cols = ["PSRJ","RAJ2000","DEJ2000","RM","e_RM","DM","P0","S1400"]
        viz = Vizier(columns=psr_cols, row_limit=-1)
        tables = viz.query_region(coord, radius=radius_deg * u.deg, catalog="B/psr/psr")
    except Exception as exc:
        warnings.warn(f"VizieR (pulsars) query failed: {exc}")
        return None

    if not tables:
        print("    ATNF pulsars: 0 with RM")
        return _empty

    df = tables[0].to_pandas()

    # Filter to those with a measured RM
    if "RM" not in df.columns:
        print("    ATNF pulsars: 0 with RM")
        return _empty

    df = df[df["RM"].notna()].reset_index(drop=True)

    if df.empty:
        print("    ATNF pulsars: 0 with RM")
        return _empty

    try:
        ra_vals  = df["RAJ2000"].apply(_hms_to_deg).values.astype(float)
        dec_vals = df["DEJ2000"].apply(_dms_to_deg).values.astype(float)
    except Exception:
        return None

    out = pd.DataFrame({
        "ra_deg"   : ra_vals,
        "dec_deg"  : dec_vals,
        "rm"       : pd.to_numeric(df["RM"],   errors="coerce").values,
        "rm_err"   : pd.to_numeric(df["e_RM"], errors="coerce").values,
        "flux_mjy" : pd.to_numeric(df["S1400"], errors="coerce").values if "S1400" in df.columns else np.full(len(df), np.nan),
        "frac_pol" : np.full(len(df), np.nan),
        "name"     : df["PSRJ"].astype(str).values if "PSRJ" in df.columns else [""] * len(df),
    })
    out["source"] = "ATNF"
    print(f"    ATNF pulsars: {len(out)} with RM")
    return out


# ---------------------------------------------------------------------------
# Main orchestrator – with CSV caching
# ---------------------------------------------------------------------------

def get_pol_sources(
    field_name: str,
    ra_deg: float,
    dec_deg: float,
    catalog_dir: Path,
    radius_deg: float = 3.5,
    refresh: bool = False,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Return (extgal_df, pulsar_df) for the given field.

    Results are cached as  <catalog_dir>/<field_name>_{extgal,pulsar}.csv.
    Pass refresh=True to ignore the cache and re-download.

    extgal_df / pulsar_df have columns:
        ra_deg, dec_deg, rm, rm_err, flux_mjy, frac_pol, name, source
    Either may be None (on network error) or empty (no sources in field).
    """
    catalog_dir = Path(catalog_dir)
    catalog_dir.mkdir(parents=True, exist_ok=True)

    extgal_csv = catalog_dir / f"{field_name}_extgal.csv"
    pulsar_csv = catalog_dir / f"{field_name}_pulsar.csv"

    # --- extgalactic ---
    if not refresh and extgal_csv.exists():
        extgal_df = pd.read_csv(extgal_csv)
        print(f"    Extgal cache: {len(extgal_df)} sources ({extgal_csv.name})")
    else:
        extgal_df = fetch_extgal(ra_deg, dec_deg, radius_deg)
        if extgal_df is not None:
            extgal_df.to_csv(extgal_csv, index=False)

    # --- pulsars ---
    if not refresh and pulsar_csv.exists():
        pulsar_df = pd.read_csv(pulsar_csv)
        print(f"    Pulsar cache: {len(pulsar_df)} sources ({pulsar_csv.name})")
    else:
        pulsar_df = fetch_pulsars(ra_deg, dec_deg, radius_deg)
        if pulsar_df is not None:
            pulsar_df.to_csv(pulsar_csv, index=False)

    return extgal_df, pulsar_df
