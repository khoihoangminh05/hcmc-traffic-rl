import sys,json,collections,numpy as np
from scipy.stats import spearmanr
sys.argv=[sys.argv[0],"x","cal_meso"]
import importlib.util; sp=importlib.util.spec_from_file_location("c","/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6/cal12b.py"); c=importlib.util.module_from_spec(sp); sp.loader.exec_module(c)
T=c.target(); D=c.D
def ev(d,rid,refid):
    R={r["id"]:r for r in json.load(open(f"{D}/{d}/rows.json"))}; ref=R[refid]["speed"]; s=R[rid]["speed"]
    out=collections.defaultdict(lambda:([],[]))
    for e,t in T.items():
        x=max(ref.get(e,t["vf"])/s[e],1) if e in s else 1.0
        for k in (t["cls"],"all"): out[k][0].append(x); out[k][1].append(t["tti"])
    return {k:(round(spearmanr(a,b)[0],2),len(a)) for k,(a,b) in out.items()}
for rid in ["c20_m3","c4_m3","d14_m3","d3_m3"]: print(rid,ev("cal_meso",rid,"ref_m3"))
