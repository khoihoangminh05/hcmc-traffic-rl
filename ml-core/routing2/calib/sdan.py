import json,sys
rows={r["id"]:r for r in json.load(open(sys.argv[1]+"/rows.json"))}
for x in json.load(open(sys.argv[1]+"/rescore.json"))[:12]:
    r=rows[x["id"]]; p=x["p"]; sd=r.get("sd",{})
    print(x["id"],"int",round(p["internal"]),"gate",[round(g) for g in p["gate"]],"thr",round(p["thr"],2),"| a",round(sd.get("a",0),2),"b",round(sd.get("b",0),2),"k0",round(sd.get("k0",0),3),
          "| sp cal",x["cal"]["spearman"],"test",x["test"]["spearman"],"loss",x["test"]["loss"],"arr",x["arr"],"tele",x["tele"],x["test"]["class_median_sim_vs_mbx"])
