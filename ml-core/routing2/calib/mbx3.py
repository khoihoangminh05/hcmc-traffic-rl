import json,pandas as pd,numpy as np
from scipy.stats import spearmanr
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
A=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json"))["alleys"]
o=pd.read_csv(D+"/probe_full2/edge_obs.csv",usecols=["timestamp","alley_id","speed_mps","route_id"])
t=pd.to_datetime(o.timestamp)+pd.Timedelta(hours=7); o["h"]=t.dt.hour; o["day"]=t.dt.date; o["dow"]=t.dt.dayofweek
o["cls"]=o.alley_id.map(lambda e:A.get(e,{}).get("road_class")); o["nm"]=o.alley_id.map(lambda e:A.get(e,{}).get("name") or "?")
M=o[o.cls.isin(["primary","secondary","tertiary"])]
# same edges, per day, speed at 5h and 17-18h
p=M.groupby(["day","h"]).agg(n=("speed_mps","size"),edges=("alley_id","nunique"),v=("speed_mps","median")).reset_index()
print(p[p.h.isin([5,6,17,18])].to_string())
W=o[(o.dow<5)]
def T(sub,ref=(5,)):
    v5=sub[sub.h.isin(ref)].groupby("alley_id").speed_mps.median(); n5=sub[sub.h.isin(ref)].groupby("alley_id").size()
    vp=sub[sub.h.isin([17,18])].groupby("alley_id").speed_mps.median(); npk=sub[sub.h.isin([17,18])].groupby("alley_id").size()
    k=[e for e in vp.index if e in v5.index and n5[e]>=8 and npk[e]>=8]; return v5[k]/vp[k]
for ref in [(5,),(5,6),(21,)]:
    x=T(W,ref); c=x.index.map(lambda e:A[e]["road_class"])
    print("weekday ref",ref,"TTI median by class",x.groupby(c).median().round(2).to_dict(),"n",x.groupby(c).size().to_dict())
x=T(W); nm=x.index.map(lambda e:A[e].get("name") or "?"); print("weekday TTI by road:",x.groupby(nm).median().round(2).sort_values().to_dict())
xa=T(o); nm=xa.index.map(lambda e:A[e].get("name") or "?"); print("ALL-days TTI by road (old target):",xa.groupby(nm).median().round(2).sort_values().to_dict())
wd=sorted(W.day.unique()); a=T(W[W.day.isin(wd[0::2])]); b=T(W[W.day.isin(wd[1::2])]); k=a.index.intersection(b.index)
c=pd.Index(k).map(lambda e:A[e]["road_class"]); mj=c.isin(["primary","secondary","tertiary"])
print("weekday split-day Spearman: major",round(spearmanr(a[k][mj],b[k][mj])[0],3),int(mj.sum()),"all",round(spearmanr(a[k],b[k])[0],3),len(k))
print("weekdays:",wd)
