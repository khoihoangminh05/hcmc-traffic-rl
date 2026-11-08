# Score the B2 sweep at 300 m stretches against Mapbox, halves by stretch hash; gate C1 from PLAN_CALIB_TRAIN.md
import sys,json,collections,math,hashlib,numpy as np
from scipy.stats import spearmanr
run=sys.argv[1]; sys.argv=[sys.argv[0],"x",run]
import importlib.util; sp=importlib.util.spec_from_file_location("c","/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6/cal12b.py"); c=importlib.util.module_from_spec(sp); sp.loader.exec_module(c)
T=c.target(); D=c.D; G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]; geo=G["nodes_geo"]
uv={e["alley_id"]:(str(e["u"]),str(e["v"])) for e in G["edge_list"]}
def key(e):
    u,v=uv[e]; x=(float(geo[u]["lon"])+float(geo[v]["lon"]))/2*109300; y=(float(geo[u]["lat"])+float(geo[v]["lat"]))/2*110574
    return (A[e].get("name") or A[e]["road_class"],int(x//300),int(y//300))
grp=collections.defaultdict(list)
for e in T: grp[key(e)].append(e)
grp={k:v for k,v in grp.items() if len(v)>=3}
half={k:"cal" if int(hashlib.sha1(str(k).encode()).hexdigest(),16)%2==0 else "test" for k in grp}
cls={k:collections.Counter(T[e]["cls"] for e in v).most_common(1)[0][0] for k,v in grp.items()}
y={k:np.median([math.log(T[e]["tti"]) for e in v]) for k,v in grp.items()}
R={r["id"]:r for r in json.load(open(D+f"/{run}/rows.json"))}; ref=R["ref"]["speed"]
MB={"primary":1.67,"secondary":1.47,"tertiary":1.33}
rho=lambda ks,x:float(spearmanr([x[k] for k in ks],[y[k] for k in ks])[0])
res=[]
for i,r in R.items():
    if i=="ref": continue
    s=r["speed"]; x={k:np.median([math.log(max(ref.get(e,T[e]["vf"])/s[e],1)) if e in s else 0. for e in v]) for k,v in grp.items()}
    M=[k for k in grp if cls[k] in MB]
    med={cl:math.exp(np.median([x[k] for k in grp if cls[k]==cl])) for cl in MB}
    err=max(abs(med[cl]/MB[cl]-1) for cl in MB)
    cal=[k for k in grp if half[k]=="cal"]; test=[k for k in grp if half[k]=="test"]
    res.append(dict(id=i,arr=r["arr"],tele=r["tele"],rc=rho(cal,x),rt=rho(test,x),rm=rho(M,x),med={k:round(v,2) for k,v in med.items()},err=err,p=r["p"],sd=r["sd"],moto=r["n_moto"],car=r["n_car"]))
print("stretches",len(grp),"sets",len(res),"| arr>=.8:",sum(x["arr"]>=.8 for x in res),"| arr>=.7:",sum(x["arr"]>=.7 for x in res))
ok=[x for x in res if x["arr"]>=.75]
for name,L in [("best by level error among arr>=.75",sorted(ok,key=lambda x:x["err"])[:6]),("best by cal rho among arr>=.75",sorted(ok,key=lambda x:-x["rc"])[:4])]:
    print("--",name)
    for x in L:
        p=x["p"]; print(x["id"],"arr %.2f tele %d rho cal %.2f test %.2f major %.2f"%(x["arr"],x["tele"],x["rc"],x["rt"],x["rm"]),"TTI",x["med"],"err %.0f%%"%(100*x["err"]),"| int",round(p["internal"]),"gate",[round(g) for g in p["gate"]],"icar",round(p["icar"]),"a %.2f k0 %.3f"%(x["sd"]["a"],x["sd"]["k0"]),"moto",x["moto"],"car",x["car"])
print("arr vs level: ",[(round(x["arr"],2),x["med"]["primary"]) for x in sorted(res,key=lambda x:-x["arr"])[:48:4]])
