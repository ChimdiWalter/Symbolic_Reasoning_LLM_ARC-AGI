"""Structural summary of the downloaded datasets (counts only; no measured value is printed)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from t5.data import Dataset, Midas, preprocess  # noqa: E402
R = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
sets = [("Toy", "ToyPKNMMB.sif", "ToyDataMMB.csv"), ("LiverDREAM", "LiverPKNDREAM.sif", "LiverDataDREAMMIDAS.csv")]
for d in ["LiverMSB2009", "ExtLiverPCB", "HepG2CancerRes2011", "ExtLiverPriHuMCP2010", "TCellPCB2007", "EGFR-ErbB_PCB2009"]:
    sets.append((d, f"cno_datasets/{d}/PKN-{d}.sif", f"cno_datasets/{d}/MD-{d}.csv"))
for name, sif, md in sets:
    try:
        m = Midas(os.path.join(R, md))
        ds = Dataset(name, os.path.join(R, sif), os.path.join(R, md))
        e, h = preprocess(ds)
        nodes = {u for u, _, _ in e} | {v for _, _, v in e}
        print(f"{name}: times={m.times} rows={len(m.rows)} t1={ds.t1} conds={len(ds.conditions)} stim={len(ds.stimuli)} "
              f"inh={len(ds.inhibitors)} readouts={len(ds.readouts)} pkn_edges={len(ds.pkn)} -> nodes={len(nodes)} "
              f"edges={len(e)} hyperedges={len(h)} t0_matched={sum(c['t0'] is not None for c in ds.conditions)}")
    except Exception as ex:
        print(f"{name}: ERROR {type(ex).__name__}: {str(ex)[:150]}")
