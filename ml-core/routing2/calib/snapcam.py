import json,math,collections
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]; geo=G["nodes_geo"]
gates={str(x) for x in G["gates_in"]+G["gates_out"]}
import shapely
core=set()
xy=lambda lon,lat:(lon*109300,lat*110574)
nodes={n:xy(float(v["lon"]),float(v["lat"])) for n,v in geo.items()}
inc=collections.defaultdict(set)
for e in G["edge_list"]:
    a=A[e["alley_id"]]
    if a["road_class"] in("primary","secondary","tertiary","residential"):
        for n in (str(e["u"]),str(e["v"])): inc[n].add((a.get("name") or a["road_class"],a["road_class"]))
cams=json.load(open(D+"/cams/cams_q4box.json")); keep=[]
for c in cams:
    p=xy(c["lon"],c["lat"]); n,d=min(((n,math.dist(p,q)) for n,q in nodes.items() if n in inc),key=lambda x:x[1])
    gd=min(math.dist(nodes[n],nodes[g]) for g in gates)
    c.update(node=n,dist_m=round(d),roads=sorted({r for r,_ in inc[n]}),classes=sorted({k for _,k in inc[n]}),gate_m=round(gd))
    if d<=40: keep.append(c)
keep.sort(key=lambda c:c["gate_m"])
for c in keep: print(c["id"],c["status"],"|",c["name"],"| d",c["dist_m"],"m | gate",c["gate_m"],"m |",c["roads"])
json.dump(keep,open(D+"/cams/cams_q4_net.json","w"),ensure_ascii=False,indent=1)
print("kept",len(keep),"of",len(cams),"| UP:",sum(c["status"]=="UP" for c in keep))
