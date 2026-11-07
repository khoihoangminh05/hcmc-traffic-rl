# Find queue roots: stuck links (sim TTI>4) whose downstream links are not stuck. Report SUMO lane / connection facts.
import json,collections,numpy as np,sumolib,sys
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
A=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json"))["alleys"]
net=sumolib.net.readNet(D+"/net_full2/quan4_v4.net.xml",withConnections=True)
runs=[(d,i) for d,i in [("cal_meso","c20_m3"),("cal_meso","c4_m3"),("cal_sw","c20_v3"),("cal_sw","c4_v3")]]
ref={}
for d,rid in [("cal_meso","ref_m3"),("cal_ref","ref")]:
    for r in json.load(open(f"{D}/{d}/rows.json")):
        if r["id"]==rid:
            for e,v in r["speed"].items(): ref.setdefault(d,{}).setdefault(e,[]).append(v)
cnt=collections.Counter(); info={}
for d,i in runs:
    rs=[r for r in json.load(open(f"{D}/{d}/rows.json")) if r["id"]==i]
    S=collections.defaultdict(list)
    for r in rs:
        for e,v in r["speed"].items(): S[e].append(v)
    rf=ref["cal_meso" if d=="cal_meso" else "cal_ref"]
    tti={e:np.mean(rf.get(e,[A.get(e,{}).get("v_free",5)]))/np.mean(v) for e,v in S.items()}
    for e,t in tti.items():
        if t<=4 or e not in A: continue
        try: E=net.getEdge(e)
        except KeyError: continue
        outs=[o.getID() for o in E.getOutgoing()]
        if all(tti.get(o,1)<=2 for o in outs): cnt[e]+=1; info[e]=(round(t,1),E,outs)
roots=[e for e,c in cnt.items() if c>=3]
print("queue roots stuck in >=3 of 4 runs:",len(roots))
kind=collections.Counter()
for e in sorted(roots,key=lambda e:-info[e][0])[:40]:
    t,E,outs=info[e]; a=A[e]; to=E.getToNode()
    conns=sum(len(v) for v in E.getOutgoing().values())
    o_cls=[A.get(o,{}).get("road_class","?") for o in outs]
    print(f"{a.get('name') or '-':28s} {a['road_class']:11s} L={a['length_m']:6.0f} lanes={E.getLaneNumber()} w={E.getLane(0).getWidth():.2f} -> node {to.getID()} type={to.getType():22s} outs={len(outs)} conns={conns} out_cls={o_cls} tti={t}")
    kind[(a['road_class'],to.getType())]+=1
print(kind.most_common(10))
