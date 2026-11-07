# score meso variants: each variant's TTI uses its own low-demand reference run
import sys,json,collections,numpy as np
run=sys.argv[1]; sys.argv=[sys.argv[0],"x",run]
import importlib.util; sp=importlib.util.spec_from_file_location("c","/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6/cal12b.py"); c=importlib.util.module_from_spec(sp); sp.loader.exec_module(c)
A=json.load(open(c.NET+"/graph/alley_graph_full_z.json"))["alleys"]
T=c.target(); R=json.load(open(c.O/"rows.json"))
for v in sorted({r["id"].split("_")[1] for r in R}):
    c.REF.clear(); ref=[r for r in R if r["id"]==f"ref_{v}"]
    for e in {k for r in ref for k in r["speed"]}: c.REF[e]=float(np.mean([r["speed"][e] for r in ref if e in r["speed"]]))
    for i in sorted({r["id"] for r in R if r["id"].endswith(v)}):
        rs=[r for r in R if r["id"]==i]; S=collections.defaultdict(list)
        for r in rs:
            for e,x in r["speed"].items(): S[e].append(x)
        t=np.array([max(c.REF.get(e,A[e]["v_free"])/np.mean(x),1) for e,x in S.items() if e in A])
        print(i,"arr",round(rs[0]["arr"] or 0,3),"tele",rs[0]["tele"],"wall",round(rs[0]["wall"]),"stuck",round(float((t>3).mean()),3),
              "| test",json.dumps(c.score(rs,T,"test")),"| cal sp",c.score(rs,T,"cal")["spearman"])
