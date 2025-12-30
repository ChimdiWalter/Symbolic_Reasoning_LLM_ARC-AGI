import json, argparse, numpy as np

def np_arr(x): return np.array(x, dtype=np.int8)
def palette(a): return [int(v) for v in np.unique(a)]

def comp_count(a: np.ndarray) -> int:
    H,W = a.shape
    vis = np.zeros((H,W), bool)
    def dfs(sr,sc,color):
        stack=[(sr,sc)]; vis[sr,sc]=True
        while stack:
            r,c = stack.pop()
            for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                rr,cc=r+dr,c+dc
                if 0<=rr<H and 0<=cc<W and not vis[rr,cc] and a[rr,cc]==color:
                    vis[rr,cc]=True; stack.append((rr,cc))
    cnt=0
    for color in np.unique(a):
        if color==0: continue
        for (r,c) in zip(*np.where((a==color) & (~vis))):
            if not vis[r,c]:
                dfs(r,c,color); cnt+=1
    return int(cnt)

def centroid(a):
    rs,cs = np.nonzero(a!=0)
    if rs.size==0: return None
    return [float(rs.mean()), float(cs.mean())]

def pair_features(x,y):
    fx={"in_size":[int(x.shape[0]),int(x.shape[1])],
        "in_palette":palette(x),
        "in_components":comp_count(x),
        "in_centroid":centroid(x)}
    fy={"out_size":[int(y.shape[0]),int(y.shape[1])],
        "out_palette":palette(y),
        "out_components":comp_count(y),
        "out_centroid":centroid(y)}
    return {**fx, **fy}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--challenges", required=True)
    ap.add_argument("--out", default="task_features.json")
    args=ap.parse_args()
    data=json.load(open(args.challenges))
    if "challenges" in data: data=data["challenges"]
    out={}
    for tid,spec in data.items():
        pairs=[]
        for tr in spec.get("train",[]):
            pairs.append(pair_features(np_arr(tr["input"]), np_arr(tr["output"])))
        out[tid]=pairs
    json.dump(out, open(args.out,"w"))
    print(f"Wrote {args.out} with {len(out)} tasks.")
if __name__=="__main__": main()
