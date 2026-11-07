# Mapbox typical (depart_at, requested days ahead) vs live on the same routes, same weekday 2026-11-05 (Thu)
import json,sys,pandas as pd,numpy as np
from scipy.stats import spearmanr
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
A=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json"))["alleys"]
ty=pd.read_csv(sys.argv[1]); ty["h"]=ty.depart_at.str[11:13].astype(int)
lv=pd.read_csv(D+"/probe_full2/edge_obs.csv",usecols=["timestamp","alley_id","speed_mps"])
t=pd.to_datetime(lv.timestamp)+pd.Timedelta(hours=7); lv["h"]=t.dt.hour; lv=lv[t.dt.dayofweek<5]
def tti(o):
    a=o[o.h==5].groupby("alley_id").speed_mps.median(); b=o[o.h.isin([17,18])].groupby("alley_id").speed_mps.median(); k=a.index.intersection(b.index); return a[k]/b[k]
for h in [5,17,18]:
    a=ty[ty.h==h].groupby("alley_id").speed_mps.median(); b=lv[lv.h==h].groupby("alley_id").speed_mps.median(); k=a.index.intersection(b.index)
    print(f"{h}h speed typical vs live(weekdays): n {len(k)} median ratio {float((a[k]/b[k]).median()):.3f} spearman {spearmanr(a[k],b[k])[0]:.3f}")
a=tti(ty); b=tti(lv); k=a.index.intersection(b.index); c=pd.Index(k).map(lambda e:A[e]["road_class"]); mj=c.isin(["primary","secondary","tertiary"])
print("TTI typical vs live: all spearman",round(spearmanr(a[k],b[k])[0],3),"n",len(k),"| major",round(spearmanr(a[k][mj],b[k][mj])[0],3),int(mj.sum()))
print("class median TTI typical",a[k].groupby(c).median().round(2).to_dict()); print("class median TTI live",b[k].groupby(c).median().round(2).to_dict())
