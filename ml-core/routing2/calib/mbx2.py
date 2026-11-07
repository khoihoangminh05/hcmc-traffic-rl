# Audit the Mapbox probe data itself: is it live, is it reproducible day to day, is 5h a free-flow reference.
import json,pandas as pd,numpy as np
from scipy.stats import spearmanr
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
g=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=g["alleys"]
o=pd.read_csv(D+"/probe_full2/edge_obs.csv")
print("congestion_numeric non-null:",int(o.congestion_numeric.notna().sum()),"depart_at non-null:",int(o.depart_at.notna().sum()))
t=pd.to_datetime(o.timestamp)+pd.Timedelta(hours=7)
o["h"]=t.dt.hour; o["day"]=t.dt.date; o["dow"]=t.dt.dayofweek; o["cls"]=o.alley_id.map(lambda e:A.get(e,{}).get("road_class"))
o["kmh"]=o.speed_mps*3.6
print("days:",sorted(map(str,o.day.unique()))); print("obs per day:",o.groupby("day").size().to_dict())
print("polls per route per hour (median):",o.groupby(["route_id","day","h"]).timestamp.nunique().median())
print("share of speeds that are whole km/h:",round(float((np.abs(o.kmh-o.kmh.round())<0.01).mean()),3))
print("distinct speed values:",o.speed_mps.round(3).nunique())
# live or typical? per edge: share of obs equal to the edge's modal speed; spread across days at the same hour
mode=o.groupby("alley_id").speed_mps.agg(lambda s:s.round(2).value_counts(normalize=True).iloc[0])
mc=pd.DataFrame({"m":mode,"cls":mode.index.map(lambda e:A.get(e,{}).get("road_class"))})
print("median share of obs at the edge's single most common speed, by class:",mc.groupby("cls").m.median().round(2).to_dict())
print("edges where one speed value is >=90% of obs:",int((mode>=.9).sum()),"of",len(mode))
ed=o.groupby(["alley_id","day","h"]).speed_mps.median().reset_index()
cv=ed.groupby(["alley_id","h"]).speed_mps.agg(["std","mean","count"]); cv=cv[cv["count"]>=4]
print("day-to-day CV of edge-hour median speed, median:",round(float((cv["std"]/cv["mean"]).median()),3))
# hourly profile major roads, weekday vs weekend
M=o[o.cls.isin(["primary","secondary","tertiary"])]
for nm,sub in [("weekday",M[M.dow<5]),("weekend",M[M.dow>=5])]:
    p=sub.groupby(["alley_id","h"]).speed_mps.median().reset_index().groupby("h").speed_mps.median()
    print(nm,"major-road median speed m/s by hour:",p.round(2).to_dict())
# reproducibility of per-edge TTI(5h / 17-18h): split days into two halves
days=sorted(o.day.unique()); hA=set(days[0::2]); hB=set(days[1::2])
def tti(sub):
    v5=sub[sub.h==5].groupby("alley_id").speed_mps.median(); n5=sub[sub.h==5].groupby("alley_id").size()
    vp=sub[sub.h.isin([17,18])].groupby("alley_id").speed_mps.median(); npk=sub[sub.h.isin([17,18])].groupby("alley_id").size()
    k=[e for e in vp.index if e in v5.index and n5[e]>=8 and npk[e]>=8]
    return (v5[k]/vp[k])
for nm,cl in [("major",["primary","secondary","tertiary"]),("major+res",["primary","secondary","tertiary","residential"])]:
    s=o[o.cls.isin(cl)]
    a=tti(s[s.day.isin(hA)]); b=tti(s[s.day.isin(hB)]); k=a.index.intersection(b.index)
    print(nm,"split-day TTI Spearman:",round(float(spearmanr(a[k],b[k])[0]),3),"n",len(k),
          "| weekday vs weekend:",end=" ")
    a=tti(s[s.dow<5]); b=tti(s[s.dow>=5]); k=a.index.intersection(b.index)
    print(round(float(spearmanr(a[k],b[k])[0]),3),"n",len(k))
# is 5h the fastest hour? compare 5h vs max-hour speed per edge
eh=o.groupby(["alley_id","h"]).speed_mps.median().unstack()
print("hours available:",list(eh.columns))
r=(eh.max(axis=1)/eh[5]).dropna(); print("max-hour speed / 5h speed, median:",round(float(r.median()),3),"p90",round(float(r.quantile(.9)),3))
# Mapbox speed vs speed limit-ish: 5h speed by class
print("5h speed by class m/s:",o[o.h==5].groupby("cls").speed_mps.median().round(2).to_dict())
# coverage of target edges: which named roads
T=o[o.cls.isin(["primary","secondary","tertiary"])].groupby("alley_id").size()
names=pd.Series({e:(A[e].get("name") or "?") for e in T.index}); print("major edges observed:",len(T),"named roads:",names.value_counts().head(25).to_dict())
