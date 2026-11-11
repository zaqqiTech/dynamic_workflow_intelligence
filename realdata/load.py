"""Load PhysioNet 2019 .psv files into one parquet-like pickle with patient id and hospital."""
import glob, os, sys, numpy as np, pandas as pd
root = sys.argv[1]; out = sys.argv[2]
frames = []
for hosp, sub in (("A", "training_setA/training_setA"), ("B", "training_setB/training_setB")):
    files = sorted(glob.glob(os.path.join(root, sub, "*.psv")))
    for f in files:
        d = pd.read_csv(f, sep="|")
        d.insert(0, "patient", os.path.basename(f)[:-4]); d.insert(1, "hospital", hosp)
        frames.append(d)
df = pd.concat(frames, ignore_index=True)
df.to_pickle(out)
cols = [c for c in df.columns if c not in ("patient", "hospital")]
print("columns:", len(cols), cols[:5], "...", cols[-3:])
g = df.groupby("patient")
sep = g["SepsisLabel"].max()
print("patients:", g.ngroups, "| by hospital:", df.groupby("hospital")["patient"].nunique().to_dict())
print("rows (patient-hours):", len(df), "| septic patients:", int(sep.sum()), f"({sep.mean():.2%})")
print("septic by hospital:", df.groupby("hospital").apply(lambda x: x.groupby("patient")["SepsisLabel"].max().sum()).to_dict())
print("median ICU stay (h):", g.size().median())
