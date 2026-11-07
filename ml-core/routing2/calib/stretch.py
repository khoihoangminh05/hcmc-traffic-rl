# Score sims against Mapbox on ~300 m road stretches (same road name, 300 m grid cell), not 40 m links.
import sys,json,collections,math,hashlib,numpy as np
from scipy.stats import spearmanr
sys.argv=[sys.argv[0],"x","cal_meso"]
import importlib.util; sp=importlib.util.spec_from_file_location("c","/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6/cal12b.py"); c=importlib.util.module_from_spec(sp); sp.loader.exec_module(c)
T=c.target(); D=c.D; G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]; geo=G["nodes_geo"]
uv={e["alley_id"]:(str(e["u"]),str(e["v"])) for e in G["edge_list"]}
CELL=float(sys.argv[3]) if len(sys.argv)>3 else 300.
def key(e):
    u,v=uv[e]; x=(float(geo[u]["lon"])+float(geo[v]["lon"]))/2*109300; y=(float(geo[u]["lat"])+float(geo[v]["lat"]))/2*110574
    return (A[e].get("name") or A[e]["road_class"], int(x//CELL), int(y//CELL))
grp=collections.defaultdict(list)
for e in T: grp[key(e)].append(e)
grp={k:v for k,v in grp.items() if len(v)>=3}
half={k:("cal" if int(hashlib.sha1(str(k).encode()).hexdigest(),16)%2==0 else "test") for k in grp}
cls={k:collections.Counter(T[e]["cls"] for e in v).most_common(1)[0][0] for k,v in grp.items()}
y={k:np.median([math.log(T[e]["tti"]) for e in v]) for k,v in grp.items()}
# data ceiling: split each stretch's links in two halves and correlate
a=[np.median([math.log(T[e]["tti"]) for e in v[0::2]]) for v in grp.values()]; b=[np.median([math.log(T[e]["tti"]) for e in v[1::2]]) for v in grp.values()]
print("stretches",len(grp),"| data split-half Spearman (ceiling-ish): %.2f"%spearmanr(a,b)[0])
def ev(d,rid,refid):
    R={r["id"]:r for r in json.load(open(f"{D}/{d}/rows.json"))}; ref=R[refid]["speed"]; s=R[rid]["speed"]
    x={k:np.median([math.log(max(ref.get(e,T[e]["vf"])/s[e],1)) if e in s else 0.0 for e in v]) for k,v in grp.items()}
    o={}
    for h in ("cal","test"):
        ks=[k for k in grp if half[k]==h]; o[h]=round(spearmanr([x[k] for k in ks],[y[k] for k in ks])[0],2)
    for cl in ("primary","secondary","tertiary"):
        ks=[k for k in grp if cls[k]==cl]; o[cl]=round(spearmanr([x[k] for k in ks],[y[k] for k in ks])[0],2)
    med={cl:(round(math.exp(np.median([x[k] for k in grp if cls[k]==cl])),2),round(math.exp(np.median([y[k] for k in grp if cls[k]==cl])),2)) for cl in ("primary","secondary","tertiary")}
    return o,med,round(R[rid]["arr"],2)
runs=[("cal_meso",f"{d}_m{m}",f"ref_m{m}") for m in (1,2,3) for d in ("c20","c4","d14","d3")]
runs+=[("cal_sd",f"s{i}","ref") for i in range(31)]
import os
if os.path.exists(D+"/cal_sdlin/rows.json"): runs=[("cal_sdlin",r["id"],"ref") for r in json.load(open(D+"/cal_sdlin/rows.json")) if r["id"]!="ref"]
res=[]
for r in runs:
    try: o,med,arr=ev(*r); res.append((o["cal"],r,o,med,arr))
    except Exception as ex: pass
for x in sorted(res,key=lambda x:-x[0])[:12]: print(x[1][0],x[1][1],x[2],x[3],"arr",x[4])
