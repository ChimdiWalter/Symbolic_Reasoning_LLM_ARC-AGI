# submission_builder_robust.py
from __future__ import annotations
import os, sys, json, signal, math
from typing import Dict, Any, List, Tuple, Optional, Callable
import numpy as np
from rule_miner_stronger import infer_two_attempts, clamp01_09

# -------------------- tiny grid utils --------------------
def to_np(x): return np.array(x, dtype=np.int8)

def bbox(A):
    nz = np.argwhere(A!=0)
    if nz.size == 0: return (0,0,A.shape[0],A.shape[1])
    r0,c0 = nz.min(0); r1,c1 = nz.max(0)
    return (int(r0),int(c0),int(r1)+1,int(c1)+1)

def center_crop_pad(A,H,W):
    h,w = A.shape
    H=max(1,int(H)); W=max(1,int(W))
    if h==H and w==W: return A.copy()
    ph=max(0,H-h); pw=max(0,W-w)
    if ph>0 or pw>0:
        top=ph//2; left=pw//2
        B=np.zeros((h+ph, w+pw), dtype=A.dtype)
        B[top:top+h, left:left+w]=A
        A=B; h,w=A.shape
    r0=max(0,(h-H)//2); c0=max(0,(w-W)//2)
    return A[r0:r0+H, c0:c0+W].copy()

def bbox_crop_to(A,H,W):
    r0,c0,r1,c1=bbox(A)
    return center_crop_pad(A[r0:r1, c0:c1], H,W)

# -------------------- LLM hints / policy / bandit --------------------
def load_llm_hints(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.isfile(path): return {}
    try: return json.load(open(path))
    except: return {}

def load_policy_npz(path: Optional[str]) -> Dict[str, np.ndarray]:
    if not path or not os.path.isfile(path): return {}
    try:
        dat = np.load(path, allow_pickle=True)
        return {k: dat[k] for k in dat.files}
    except:
        return {}

def load_bandit(path: Optional[str]) -> Dict[str, Any]:
    if not path or not os.path.isfile(path): return {}
    try: return json.load(open(path))
    except: return {}

def save_bandit(path: Optional[str], state: Dict[str, Any]):
    if path:
        try: json.dump(state, open(path,"w"))
        except: pass

def bandit_key(train_pairs):
    dH = int(np.sign(np.mean([y.shape[0]-x.shape[0] for x,y in train_pairs]))) if train_pairs else 0
    dW = int(np.sign(np.mean([y.shape[1]-x.shape[1] for x,y in train_pairs]))) if train_pairs else 0
    pin = len(set(np.concatenate([np.unique(x) for x,y in train_pairs]).tolist())) if train_pairs else 0
    pout= len(set(np.concatenate([np.unique(y) for x,y in train_pairs]).tolist())) if train_pairs else 0
    compish = int(np.mean([int((x!=0).sum()>30) for x,y in train_pairs])) if train_pairs else 0
    return f"dH{dH}_dW{dW}_pin{min(pin,6)}_pout{min(pout,6)}_C{compish}"

def bandit_update(state, key, arm_name, reward):
    tab = state.setdefault(key, {})
    rec = tab.setdefault(arm_name, {"n":0,"r":0.0})
    rec["n"] += 1; rec["r"] += float(reward)

def bandit_order(state, key, candidates):
    tab = state.get(key, {})
    total_n = sum(rec["n"] for rec in tab.values()) + 1e-6
    scored=[]
    for name, fn in candidates:
        rec = tab.get(name, {"n":0,"r":0.0})
        n=rec["n"]; r=rec["r"]
        avg = (r/max(1,n)) if n>0 else 0.0
        ucb = avg + (1.0*math.sqrt(2.0*math.log(total_n+1)/max(1,n)) if n>0 else 10.0)
        scored.append((ucb,name,fn))
    scored.sort(key=lambda t: -t[0])
    return [(name,fn) for _,name,fn in scored]

# -------------------- ShapeModel --------------------
class ShapeModel:
    def __init__(self, train_pairs: List[Tuple[np.ndarray,np.ndarray]], hint: Optional[Dict[str,Any]]=None):
        self.train_pairs = train_pairs
        self.hint = hint or {}
        ts = self.hint.get("target_shape")
        if isinstance(ts,(list,tuple)) and len(ts)==2:
            H,W = int(ts[0]), int(ts[1])
            self.predict_fn = lambda x: (max(1,min(30,H)), max(1,min(30,W)))
        else:
            rule = self.hint.get("shape_rule")
            if isinstance(rule,str):
                fn = self._parse_rule(rule)
                self.predict_fn = fn if fn is not None else self._fit()
            else:
                self.predict_fn = self._fit()

    @staticmethod
    def _clamp(H,W):
        return (int(max(1,min(30, round(H)))), int(max(1,min(30, round(W)))))

    @staticmethod
    def _bbox(A):
        nz = np.argwhere(A!=0)
        if nz.size==0: return (0,0)
        r0,c0 = nz.min(0); r1,c1 = nz.max(0)
        return (int(r1-r0+1), int(c1-c0+1))

    def _fit(self):
        if not self.train_pairs:
            return lambda x: (x.shape[0], x.shape[1])
        Ysh = [(y.shape[0], y.shape[1]) for _,y in self.train_pairs]
        uniq,cnts = np.unique(np.array(Ysh), axis=0, return_counts=True)
        modeH,modeW = [int(v) for v in uniq[np.argmax(cnts)]]

        # ratios / offsets
        RH=[]; RW=[]; dH=[]; dW=[]
        Xs=[x for x,_ in self.train_pairs]
        for (x,(yh,yw)) in zip(Xs, Ysh):
            H,W = x.shape
            if H>0: RH.append(yh/max(1,H))
            if W>0: RW.append(yw/max(1,W))
            dH.append(yh-H); dW.append(yw-W)
        sh_med=float(np.median(RH)) if RH else 1.0
        sw_med=float(np.median(RW)) if RW else 1.0
        bh_med=int(round(np.median(dH))) if dH else 0
        bw_med=int(round(np.median(dW))) if dW else 0

        # simple candidate set
        cands=[]
        cands.append(("const", lambda x,H=modeH,W=modeW: (H,W)))
        cands.append(("id", lambda x: (x.shape[0], x.shape[1])))
        cands.append(("swap", lambda x: (x.shape[1], x.shape[0])))
        for sh in (0.5,2/3,1.0,1.5,2.0,sh_med):
            for sw in (0.5,2/3,1.0,1.5,2.0,sw_med):
                cands.append((f"scale_{sh}_{sw}", lambda x,sh=sh,sw=sw: self._clamp(x.shape[0]*sh, x.shape[1]*sw)))
        for ah,aw in ((bh_med,bw_med),(0,0),(1,0),(0,1),(-1,0),(0,-1)):
            cands.append((f"add_{ah}_{aw}", lambda x,ah=ah,aw=aw: self._clamp(x.shape[0]+ah, x.shape[1]+aw)))

        def loo(fn):
            bad=0; dist=0
            for x,y in self.train_pairs:
                Ht,Wt = fn(x)
                Hy,Wy = y.shape
                if (Ht,Wt)!=(Hy,Wy):
                    bad += 1
                    dist += abs(Ht-Hy)+abs(Wt-Wy)
            return (bad,dist)

        best=(10**9,10**9); best_fn=cands[0][1]
        for _,fn in cands:
            sc=loo(fn)
            if sc<best:
                best=sc; best_fn=fn

        seen = set(Ysh)
        def snapped(x):
            Ht,Wt = best_fn(x)
            # snap to seen if close (≤2 L1)
            if seen:
                cand = min(seen, key=lambda s: abs(s[0]-Ht)+abs(s[1]-Wt))
                if abs(cand[0]-Ht)+abs(cand[1]-Wt) <= 2:
                    return cand
            # local ±2 search
            best_l=(Ht,Wt); best_c=abs(0)
            best_c=10**9
            for dh in (-2,-1,0,1,2):
                for dw in (-2,-1,0,1,2):
                    hh,ww=self._clamp(Ht+dh, Wt+dw)
                    c=abs(hh-Ht)+abs(ww-Wt)
                    if c<best_c:
                        best_c=c; best_l=(hh,ww)
            return best_l
        return snapped

    def _parse_rule(self, rule: str):
        toks = rule.strip().split()
        if not toks: return None
        k = toks[0].lower()
        try:
            if k=="id":   return lambda x: (x.shape[0], x.shape[1])
            if k=="swap": return lambda x: (x.shape[1], x.shape[0])
            if k=="const" and len(toks)==3:
                H,W=int(toks[1]), int(toks[2]); 
                return lambda x,H=H,W=W: (max(1,min(30,H)), max(1,min(30,W)))
            if k=="scale" and len(toks)==3:
                sh,sw=float(toks[1]), float(toks[2])
                return lambda x,sh=sh,sw=sw: self._clamp(x.shape[0]*sh, x.shape[1]*sw)
            if k=="add" and len(toks)==3:
                ah,aw=int(toks[1]), int(toks[2])
                return lambda x,ah=ah,aw=aw: self._clamp(x.shape[0]+ah, x.shape[1]+aw)
        except:
            return None
        return None

    def predict(self, A: np.ndarray) -> Tuple[int,int]:
        return self.predict_fn(A)

# -------------------- orchestration --------------------
def _load_challenges_json(path):
    data = json.load(open(path))
    if isinstance(data,dict) and "challenges" in data and isinstance(data["challenges"], dict):
        return data["challenges"]
    return data

def _ensure_two(preds: List[np.ndarray], H: int, W: int):
    if not preds:
        z = np.zeros((H,W), dtype=np.int8); return z.tolist(), z.tolist()
    if len(preds)==1:
        a = preds[0].astype(int).tolist(); return a,a
    return preds[0].astype(int).tolist(), preds[1].astype(int).tolist()

def family_order_from_hint(hint_family: Optional[str]) -> List[str]:
    if hint_family=="global_geom_palette": return ["G","C"]
    if hint_family=="component_mapping":    return ["C","G"]
    return ["G","C"]

def solve_task(task_id: str,
               train_pairs: List[Tuple[np.ndarray,np.ndarray]],
               test_grids: List[np.ndarray],
               beam: int, depth: int,
               hint: Optional[Dict[str,Any]],
               policy: Optional[Dict[str,np.ndarray]],
               bandit_state: Dict[str,Any],
               timeout_sec: int) -> List[List[np.ndarray]]:
    # guard
    def handler(signum, frame): raise TimeoutError()
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(max(1,int(timeout_sec)))

    try:
        shape_model = ShapeModel(train_pairs, hint or {})
        # Provide per-test shape fn to miner
        shape_fn = shape_model.predict
        miner_outs = infer_two_attempts(
            train_pairs, test_grids,
            policy=None,
            shape_predict_fn=shape_fn,
            family_hint=(hint or {}).get("family"),
            palette_hint=(hint or {}).get("palette_hint"),
            beam=beam, depth=depth
        )
        # Final per-test shape enforcement
        results=[]
        for i, A in enumerate(test_grids):
            Ht,Wt = shape_fn(A)
            cand = miner_outs[i] if i<len(miner_outs) else []
            out=[]
            for y in cand[:2]:
                if y.shape != (Ht,Wt):
                    y = bbox_crop_to(y, Ht, Wt) if (y!=0).any() else center_crop_pad(y, Ht, Wt)
                out.append(clamp01_09(y))
            if len(out)<2:
                z = np.zeros((Ht,Wt), dtype=np.int8)
                out = out + [z]
            results.append(out[:2])
        return results
    except TimeoutError:
        # emit zeros of predicted shapes
        results=[]
        sm = ShapeModel(train_pairs, hint or {})
        for A in test_grids:
            Ht,Wt = sm.predict(A)
            z = np.zeros((Ht,Wt), dtype=np.int8)
            results.append([z.copy(), z.copy()])
        return results
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

def build_from_challenges(ch_path: str,
                          beam: int = 256,
                          depth: int = 2,
                          policy_npz: Optional[str]=None,
                          llm_hints_path: Optional[str]=None,
                          bandit_state_path: Optional[str]=None,
                          timeout_sec: int = 30) -> Dict[str, Any]:
    raw = _load_challenges_json(ch_path)
    llm_hints = load_llm_hints(llm_hints_path)
    policy    = load_policy_npz(policy_npz)
    bandit_state = load_bandit(bandit_state_path)

    submission = {}
    for task_id, spec in raw.items():
        train_pairs = [(to_np(z["input"]), to_np(z["output"])) for z in spec.get("train",[])]
        test_inputs = [to_np(z["input"]) for z in spec.get("test",[])]
        preds = solve_task(task_id, train_pairs, test_inputs,
                           beam=beam, depth=depth,
                           hint=llm_hints.get(task_id),
                           policy=policy,
                           bandit_state=bandit_state,
                           timeout_sec=timeout_sec)
        # pack JSON
        per_task=[]
        sm = ShapeModel(train_pairs, llm_hints.get(task_id) if llm_hints else None)
        for i, x in enumerate(test_inputs):
            Ht,Wt = sm.predict(x)
            cand = preds[i] if i<len(preds) else []
            a1,a2 = _ensure_two(cand, Ht, Wt)
            per_task.append({"attempt_1": a1, "attempt_2": a2})
        submission[task_id] = per_task

    save_bandit(bandit_state_path, bandit_state)
    return submission

# -------------------- CLI --------------------
def _parse_argv(argv: List[str]):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--beam", type=int, default=256)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--timeout_sec", type=int, default=30)
    ap.add_argument("--policy", type=str, default=None)
    ap.add_argument("--llm_hints", type=str, default=None)
    ap.add_argument("--bandit_state", type=str, default="bandit_state.json")
    return ap.parse_args(argv)

def main(argv: List[str]) -> int:
    args = _parse_argv(sys.argv[1:])
    sub = build_from_challenges(args.input,
                                beam=args.beam,
                                depth=args.depth,
                                policy_npz=args.policy,
                                llm_hints_path=args.llm_hints,
                                bandit_state_path=args.bandit_state,
                                timeout_sec=args.timeout_sec)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    json.dump(sub, open(args.output,"w"))
    print(f"Wrote {args.output} with {len(sub)} tasks")
    return 0

if __name__=="__main__":
    raise SystemExit(main(sys.argv))
