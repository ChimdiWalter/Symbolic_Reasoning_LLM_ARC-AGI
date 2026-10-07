import json, sys
R_ = "/deltos/e/lesion_phes/code/python/pipeline/Reasoning_Project_arc2026"
sys.path.insert(0, R_); sys.path.insert(0, R_ + "/scripts")
import numpy as np
from cora_arc2026 import v17_compiler as X
from cora_arc2026 import v19_repair as R
corpus = json.load(open(R_ + "/outputs/tti/v19_dev_corpus.json"))["tasks"]
t = corpus[3]
train = [(np.asarray(p[0]), np.asarray(p[1])) for p in t["train"]]
for k in range(3):
    a = X.run_reasoner(train, ())
    b = R.run_reasoner(train, ())
    print("plain", a["accepted"], a["events"], a["seconds"], "| K*'", b["accepted"], b["events"], b["seconds"], flush=True)
