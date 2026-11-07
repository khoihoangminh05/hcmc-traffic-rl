# Is Mapbox per-link TTI spatially coherent? Correlate each target link with the next link of the same class it flows into.
import sys,json,numpy as np
from scipy.stats import spearmanr
sys.argv=[sys.argv[0],"x","cal_meso"]
import importlib.util; sp=importlib.util.spec_from_file_location("c","/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6/cal12b.py"); c=importlib.util.module_from_spec(sp); sp.loader.exec_module(c)
T=c.target(); D=c.D; G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]
uv={e["alley_id"]:(str(e["u"]),str(e["v"])) for e in G["edge_list"]}
out={}
for e,(u,v) in uv.items(): out.setdefault(u,[]).append(e)
for cls in ["primary","secondary","tertiary","residential"]:
    x,y,xs,ys=[],[],[],[]
    for e,t in T.items():
        if t["cls"]!=cls: continue
        nx_=[f for f in out.get(uv[e][1],[]) if f in T and T[f]["cls"]==cls and uv[f][1]!=uv[e][0]]
        same=[f for f in nx_ if (A[f].get("name") or "")==(A[e].get("name") or "") and A[e].get("name")]
        for f in nx_: x.append(np.log(t["tti"])); y.append(np.log(T[f]["tti"]))
        for f in same: xs.append(np.log(t["tti"])); ys.append(np.log(T[f]["tti"]))
    lens=[A[e]["length_m"] for e in T if T[e]["cls"]==cls]
    print(cls,"adjacent pairs",len(x),"Spearman %.2f"%spearmanr(x,y)[0],"| same road",len(xs),"%.2f"%spearmanr(xs,ys)[0],"| link length median %.0f m, share <30 m %.2f"%(np.median(lens),np.mean(np.array(lens)<30)))
