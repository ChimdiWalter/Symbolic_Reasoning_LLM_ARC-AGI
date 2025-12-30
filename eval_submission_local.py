# eval_submission_local.py
import sys, json, numpy as np
from collections import Counter

def arr(x):
    if isinstance(x,dict) and "output" in x: x=x["output"]
    return np.array(x,int)

def main(sub_path):
    sub   = json.load(open(sub_path))
    chall = json.load(open("data/arc-agi_evaluation_challenges.json"))
    sol   = json.load(open("data/arc-agi_evaluation_solutions.json"))

    fmt = 0; both_zero = 0
    for tests in sub.values():
        for rec in tests:
            for k in ("attempt_1","attempt_2"):
                A = np.array(rec[k], int)
                fmt += int(A.ndim!=2 or A.size==0 or A.min()<0 or A.max()>9)
            a1 = np.array(rec["attempt_1"], int); a2 = np.array(rec["attempt_2"], int)
            both_zero += int((a1!=0).sum()==0 and (a2!=0).sum()==0)

    wrong_shape_both = hit = tot = 0
    for tid, spec in chall.items():
        golds = sol[tid]["test"] if isinstance(sol[tid],dict) else sol[tid]
        golds = [arr(g) for g in golds]
        guesses = sub.get(tid, [])
        if len(guesses) != len(golds): continue
        for g, rec in zip(golds, guesses):
            a1 = np.array(rec["attempt_1"], int)
            a2 = np.array(rec["attempt_2"], int)
            wrong_shape_both += int(a1.shape!=g.shape and a2.shape!=g.shape)
            ok = (a1.shape==g.shape and (a1==g).all()) or (a2.shape==g.shape and (a2==g).all())
            hit += int(ok); tot += 1

    print("format problems:", fmt)
    print("pairs both_attempts_all_zero:", both_zero)
    print("pairs both attempts wrong shape:", wrong_shape_both)
    print(f"approx exact (either attempt): {hit}/{tot} = {hit/max(1,tot):.2%}")

if __name__=="__main__":
    if len(sys.argv)!=2:
        print("usage: python eval_submission_local.py submission_eval.json")
        sys.exit(2)
    main(sys.argv[1])
