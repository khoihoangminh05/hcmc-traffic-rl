import json,pandas as pd,numpy as np
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]
gates={str(x) for x in G["gates_in"]+G["gates_out"]}; uv={e["alley_id"]:(str(e["u"]),str(e["v"])) for e in G["edge_list"]}
o=pd.read_csv(D+"/typ_major_m/edge_obs.csv"); o["h"]=o.depart_at.str[11:13].astype(int)
a=o[o.h==5].groupby("alley_id").speed_mps.median(); b=o[o.h.isin([17,18])].groupby("alley_id").speed_mps.median(); k=a.index.intersection(b.index); T=a[k]/b[k]
c=pd.Index(k).map(lambda e:A[e]["road_class"]); g=np.array([uv[e][0] in gates or uv[e][1] in gates for e in k])
print("edges with TTI:",len(k),"by class median",T.groupby(c).median().round(2).to_dict(),"n",T.groupby(c).size().to_dict())
print("gate edges:",int(g.sum()),"median TTI",round(float(T[g].median()),2))
nm=pd.Index(k).map(lambda e:A[e].get("name") or "?"); s=T.groupby(nm).agg(["median","size"]); s=s[s["size"]>=3].sort_values("median")
print(s.round(2).to_string())
