# DWI: reference implementation, software tests, real-data evaluation, manuscript build

Software tests (no patient data):
    pip install hypothesis numpy pandas scikit-learn matplotlib
    python conformance.py      # 18 groups, 14,949 cases -> conformance_results.json
    python mutation.py         # 16 mutants -> mutation_results.json

Real-data evaluation (PhysioNet/Computing in Cardiology Challenge 2019, v1.0.0, CC BY 4.0):
    Download training_setA/ and training_setB/ from https://physionet.org/content/challenge-2019/1.0.0/
    python realdata/load.py <data_dir> physionet2019.pkl   # 40,336 patients, 1,552,210 patient-hours
    python realdata/detector.py physionet2019.pkl          # train on 70% of hospital A, calibrate on 30% of A, score B
    python realdata/realdata_eval.py                       # couplings, dwell sweep, ordering -> realdata_results.json
    python realdata/realdata_extra.py                      # earlier thresholds, theta_K reachability, trace selection
    python realdata/figures_real.py                        # Figures 3-4
    # Reverse direction (Table 6): train/calibrate on hospital B, evaluate on hospital A
    mkdir rev && cd rev && python ../realdata/detector_dir.py ../physionet2019.pkl B A && python ../realdata/realdata_eval_dir.py

Manuscript (Word with native equations and Mendeley citation fields):
    node build_ieee.js tmp.docx
    python mathconv.py tmp.docx tmp_math.docx math.json
    python citeconv.py tmp_math.docx DWI_Artikel1_IEEEAccess.docx cite/library.json
