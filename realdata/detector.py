"""Sepsis risk detector for the real-data validation (PhysioNet/CinC 2019).

Hospital A patients are split 70/30 by patient: the detector is trained on the 70 % part, the DWI
thresholds are calibrated (quantiles P93/P98/P99.9, fixed in advance from the synthetic study) on the
30 % part, and hospital B is held out entirely for the evaluation.
Outputs one hourly anomaly score sigma per patient-hour.
"""
import json, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score

df = pd.read_pickle(sys.argv[1])
VITALS = ["HR", "O2Sat", "Temp", "SBP", "MAP", "DBP", "Resp"]
LABS = ["BaseExcess", "HCO3", "FiO2", "pH", "PaCO2", "SaO2", "AST", "BUN", "Alkalinephos", "Calcium",
        "Chloride", "Creatinine", "Bilirubin_direct", "Glucose", "Lactate", "Magnesium", "Phosphate", "Potassium",
        "Bilirubin_total", "TroponinI", "Hct", "Hgb", "PTT", "WBC", "Fibrinogen", "Platelets"]
STATIC = ["Age", "Gender", "HospAdmTime", "ICULOS"]

df = df.sort_values(["patient", "ICULOS"]).reset_index(drop=True)
g = df.groupby("patient", sort=False)
X = pd.DataFrame(index=df.index)
for c in VITALS + LABS:
    X[c] = g[c].ffill()                                   # last observation carried forward (past only)
    X[c + "_obs"] = df[c].notna().astype(np.int8)          # measured this hour
for c in VITALS:
    X[c + "_d6"] = X[c] - X.groupby(df["patient"])[c].shift(6)              # change over 6 h
    X[c + "_m6"] = X.groupby(df["patient"])[c].transform(lambda s: s.rolling(6, min_periods=1).mean())
for c in STATIC:
    X[c] = df[c]
X = X.astype(np.float64)
y = df["SepsisLabel"].values

rng = np.random.default_rng(2026)
pa = np.array(sorted(df.loc[df.hospital == "A", "patient"].unique()), dtype=object)
rng.shuffle(pa)
train_p = set(pa[: int(0.7 * len(pa))])
cal_p = set(pa[int(0.7 * len(pa)):])
assert len(train_p) + len(cal_p) == len(set(pa)) == 20336 and not (train_p & cal_p)
tr = df.patient.isin(train_p).values
ca = df.patient.isin(cal_p).values
te = (df.hospital == "B").values

clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                     l2_regularization=1.0, random_state=2026)
clf.fit(X[tr], y[tr])
sigma = clf.predict_proba(X)[:, 1]
df["sigma"] = sigma

qs = np.quantile(sigma[ca], [0.93, 0.98, 0.999])
res = {
    "patients": {"A_train": len(train_p), "A_calibration": len(cal_p), "B_test": int(df[te].patient.nunique())},
    "hours": {"A_train": int(tr.sum()), "A_calibration": int(ca.sum()), "B_test": int(te.sum())},
    "auroc_hourly": {"A_calibration": float(roc_auc_score(y[ca], sigma[ca])), "B_test": float(roc_auc_score(y[te], sigma[te]))},
    "auprc_hourly": {"A_calibration": float(average_precision_score(y[ca], sigma[ca])),
                     "B_test": float(average_precision_score(y[te], sigma[te]))},
    "prevalence_hourly_B": float(y[te].mean()),
    "thresholds": {"thM_P93": float(qs[0]), "thC_P98": float(qs[1]), "thK_P99_9": float(qs[2])},
    "n_features": X.shape[1],
}
print(json.dumps(res, indent=1))
json.dump(res, open("detector_results.json", "w"), indent=1)
df[["patient", "hospital", "ICULOS", "SepsisLabel", "sigma"]].to_pickle("scores.pkl")
