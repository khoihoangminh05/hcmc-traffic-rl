# Score cal_moto: each (junction, motorcycle size) variant against its own low-demand reference, at 300 m stretches
import sys,json,collections,math,numpy as np
from scipy.stats import spearmanr
sys.argv=[sys.argv[0],"x","cal_moto"]
import importlib.util; sp=importlib.util.spec_from_file_location("c","/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6/cal12b.py"); c=importlib.util.module_from_spec(sp); sp.loader.exec_module(c)
T=c.target(); D=c.D; G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]; geo=G["nodes_geo"]
uv={e["alley_id"]:(str(e["u"]),str(e["v"])) for e in G["edge_list"]}
def key(e):
    u,v=uv[e]; x=(float(geo[u]["lon"])+float(geo[v]["lon"]))/2*109300; y=(float(geo[u]["lat"])+float(geo[v]["lat"]))/2*110574
    return (A[e].get("name") or A[e]["road_class"],int(x//300),int(y//300))
grp=collections.defaultdict(list)
for e in T: grp[key(e)].append(e)
grp={k:v for k,v in grp.items() if len(v)>=3}
cls={k:collections.Counter(T[e]["cls"] for e in v).most_common(1)[0][0] for k,v in grp.items()}
y={k:np.median([math.log(T[e]["tti"]) for e in v]) for k,v in grp.items()}
R={r["id"]:r for r in json.load(open(D+"/cal_moto/rows.json"))}
for j in ("j0","j1"):
    for m in ("old","new"):
        ref=R[f"ref_{j}_{m}"]["speed"]
        for d in ("c20","c4","d14"):
            r=R[f"{d}_{j}_{m}"]; s=r["speed"]
            x={k:np.median([math.log(max(ref.get(e,T[e]["vf"])/s[e],1)) if e in s else 0. for e in v]) for k,v in grp.items()}
            ks=list(grp); maj=[k for k in ks if cls[k] in("primary","secondary","tertiary")]
            med={cl:round(math.exp(np.median([x[k] for k in ks if cls[k]==cl])),2) for cl in ("primary","secondary","tertiary")}
            print(f"{j} {m:3s} {d:4s} arr {r['arr']:.2f} tele {r['tele']:4d} wall {r['wall']:4.0f} | stretch rho all {spearmanr([x[k] for k in ks],[y[k] for k in ks])[0]:.2f} major {spearmanr([x[k] for k in maj],[y[k] for k in maj])[0]:.2f} | TTI sim {med} (Mapbox p1.67 s1.47 t1.33)")
