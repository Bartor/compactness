"""Start r5py / R5 reproducibly on this machine and build (or load) cached transport networks.

    from pipeline.r5_env import start, network
    r5py = start(xmx="24G")                      # must run before anything imports r5py
    tn = network("wroclaw", "all")               # r5py.TransportNetwork, cached under data/interim/r5/

JVM discovery (Windows): r5py starts the JVM through JPype, and ``jpype.getDefaultJVMPath()`` on Windows looks
at ``JAVA_HOME`` first and the registry second.  The system ``java`` is version 15, which R5 7.x cannot run,
so ``start`` sets ``JAVA_HOME`` to the project JDK 21 (``.tools/jdk21``) in-process before r5py is imported.

r5py reads its options from ``sys.argv`` (configargparse ``parse_known_args``) when it is imported, so
``start`` appends ``--max-memory`` (JVM -Xmx), ``--r5-classpath`` (the R5 jar pinned in ``.tools``; r5py
would otherwise download it into %LOCALAPPDATA%/r5py, whose cache cleaner deletes files older than two
weeks) and ``--temporary-directory``.

Network cache: r5py stores the built network (Kryo) and an OSM MapDB in ``Config().CACHE_DIR`` and makes
"working copies" of the inputs there, keyed by *file name* only (a stale copy with the same name would be
reused).  ``network`` therefore points ``CACHE_DIR`` at ``data/interim/r5/<agg>/net_<variant>/`` and wipes
that directory whenever the signature of the inputs (``pipeline.r5_inputs.inputs_signature``) changes.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import warnings
from pathlib import Path

from pipeline.common import TOOLS
from pipeline.r5_inputs import agg_dir, gtfs_paths, inputs_signature, osm_path

JDK = TOOLS / "jdk21"
R5_JAR = TOOLS / "r5-v7.5.1-r5py-all.jar"
R5_JAR_SHA256 = "d50be106cadd7b636cfc0e209052767d7df570629f79fdf98ecd5cf5d2d89be7"
R5_VERSION = "v7.5.1-r5py"
_r5py = None


def start(xmx: str = "24G", tmp: Path | None = None):
    """Point JPype at JDK 21, configure r5py through sys.argv and import it (once per process)."""
    global _r5py
    if _r5py is not None:
        return _r5py
    if not (JDK / "bin" / "server" / "jvm.dll").exists() and not (JDK / "bin" / "java.exe").exists():
        raise FileNotFoundError(f"JDK 21 not found in {JDK}")
    if not R5_JAR.exists():
        raise FileNotFoundError(f"R5 jar missing: {R5_JAR} (download {R5_VERSION}, sha256 {R5_JAR_SHA256})")
    os.environ["JAVA_HOME"] = str(JDK)
    tmp = Path(tmp) if tmp else agg_dir("_tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    sys.argv += ["--max-memory", xmx, "--r5-classpath", str(R5_JAR), "--temporary-directory", str(tmp)]
    import r5py  # noqa: PLC0415 - must follow the environment set-up above
    _r5py = r5py
    return r5py


def versions() -> dict:
    import importlib.metadata as md
    import jpype
    out = {"r5py": md.version("r5py"), "r5": R5_VERSION, "r5_jar_sha256": R5_JAR_SHA256,
           "jpype1": md.version("JPype1")}
    if jpype.isJVMStarted():
        import java.lang
        out["java"] = str(java.lang.System.getProperty("java.version"))
        out["jvm_max_heap_gb"] = round(java.lang.Runtime.getRuntime().maxMemory() / 1024 ** 3, 2)
    return out


def network_dir(agg: str, variant: str) -> Path:
    return agg_dir(agg) / f"net_{variant}"


def network(agg: str, variant: str, allow_errors: bool = True):
    """Build or load the R5 network of (agg, variant); returns (TransportNetwork, info dict)."""
    r5py = start()
    from r5py.util import Config
    d = network_dir(agg, variant)
    sig = inputs_signature(agg, variant)
    sigf = d / "inputs.sig"
    if d.exists() and (not sigf.exists() or sigf.read_text() != sig):
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    Config().__dict__["CACHE_DIR"] = d          # cached_property override: per-network cache directory
    cached = any(d.glob("*.transport_network"))
    import java.lang
    import psutil
    rt, proc, peak, stop = java.lang.Runtime.getRuntime(), psutil.Process(), {"heap": 0, "rss": 0}, threading.Event()

    def sample():   # peak JVM heap in use and process RSS while building
        while not stop.is_set():
            peak["heap"] = max(peak["heap"], rt.totalMemory() - rt.freeMemory())
            peak["rss"] = max(peak["rss"], proc.memory_info().rss)
            time.sleep(0.5)

    th = threading.Thread(target=sample, daemon=True)
    th.start()
    t0 = time.time()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        tn = r5py.TransportNetwork(osm_path(agg), gtfs_paths(agg, variant), allow_errors=allow_errors)
    dt = time.time() - t0
    stop.set()
    th.join()
    sigf.write_text(sig)
    info = {"agglomeration": agg, "variant": variant, "loaded_from_cache": cached, "seconds": round(dt, 1),
            "heap_peak_gb": round(peak["heap"] / 1024 ** 3, 2), "rss_peak_gb": round(peak["rss"] / 1024 ** 3, 2),
            "cache_bytes": sum(p.stat().st_size for p in d.glob("*") if p.is_file()),
            "network_bytes": sum(p.stat().st_size for p in d.glob("*.transport_network")),
            "mapdb_bytes": sum(p.stat().st_size for p in d.glob("*.mapdb*")),
            "inputs_sig": sig, "r5_warnings": [str(w.message)[:2000] for w in caught]}
    if not cached:
        (d / "build.json").write_text(json.dumps(info, indent=1))
    elif (d / "build.json").exists():
        info["first_build"] = json.loads((d / "build.json").read_text())
    return tn, info


def check_network(tn, agg: str, days: dict[str, str]) -> dict:
    """What R5 actually loaded: trips per feed active on each reference day, stops without street link."""
    import java.time
    tl = tn._transport_network.transitLayer
    out = {"patterns": int(tl.tripPatterns.size()), "stops": int(tl.getStopCount())}
    for code, day in days.items():
        active = tl.getActiveServicesForDate(java.time.LocalDate.parse(day))
        per = {}
        for p in tl.tripPatterns:
            for s in p.tripSchedules:
                if active.get(int(s.serviceCode)):
                    f = str(s.tripId).split(":", 1)[0]
                    per[f] = per.get(f, 0) + 1
        out[f"trips_{code}"] = dict(sorted(per.items()))
    sv = tl.streetVertexForStop
    unlinked = [str(tl.stopIdForIndex.get(i)) for i in range(sv.size()) if sv.get(i) < 0]
    out["stops_unlinked"] = len(unlinked)
    out["stops_unlinked_by_feed"] = dict(sorted(pd_counts(u.split(":", 1)[0] for u in unlinked).items()))
    return out


def pd_counts(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out
