import json,sys,numpy as np,collections
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
A=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json"))["alleys"]
ref=json.load(open(D+"/cal_ref/rows.json")); REF=collections.defaultdict(list)
for r in ref:
    for e,v in r["speed"].items(): REF[e].append(v)
REF={e:np.mean(v) for e,v in REF.items()}
R=json.load(open(D+f"/{sys.argv[1]}/rows.json"))
for i in sorted({r["id"] for r in R}):
    rs=[r for r in R if r["id"]==i]; S=collections.defaultdict(list)
    for r in rs:
        for e,v in r["speed"].items(): S[e].append(v)
    t={e:max(REF.get(e,A[e]["v_free"])/np.mean(v),1) for e,v in S.items() if e in A}
    T=np.array(list(t.values()))
    med={c:round(float(np.median([x for e,x in t.items() if A[e]["road_class"]==c])),2) for c in ["primary","secondary","tertiary","residential","alley"]}
    nm=collections.defaultdict(list)
    for e,x in t.items(): nm[A[e].get("name")].append(x)
    print(i,"arr",round(np.mean([r["arr"] for r in rs]),3),"tele",np.mean([r["tele"] for r in rs]),"stuck(TTI>3)",round(float((T>3).mean()),3),"1.15-3",round(float(((T>1.15)&(T<=3)).mean()),3),med,
          "KH",round(float(np.median(nm["Khánh Hội"])),2),"NTT",round(float(np.median(nm["Nguyễn Tất Thành"])),2),"HD",round(float(np.median(nm["Hoàng Diệu"])),2))
