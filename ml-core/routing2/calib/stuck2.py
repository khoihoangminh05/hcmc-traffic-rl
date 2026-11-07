import json,collections,numpy as np,sumolib
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]
gates={str(x) for x in G["gates_in"]}; uv={e["alley_id"]:(str(e["u"]),str(e["v"])) for e in G["edge_list"]}
import networkx as nx
H=nx.DiGraph([(uv[e][0],uv[e][1]) for e in uv])
dist={}
for g in gates:
    for n,d in nx.single_source_shortest_path_length(H,g,cutoff=6).items(): dist[n]=min(dist.get(n,99),d)
R={r["id"]:r for r in json.load(open(D+"/cal_meso/rows.json"))}
ref=R["ref_m3"]["speed"]
for rid in ["c20_m3","c4_m3","d14_m3"]:
    sp=R[rid]["speed"]; st=[e for e,v in sp.items() if e in A and ref.get(e,A[e]["v_free"])/v>4]
    c=collections.Counter(A[e]["road_class"] for e in st); near=sum(dist.get(uv[e][0],99)<=3 for e in st)
    print(rid,"stuck",len(st),"by class",dict(c),"| within 3 hops of an entry gate:",near,"| arr",round(R[rid]["arr"],3),"moto",R[rid]["n_moto"])
    # connected clusters of stuck links
    Hs=nx.Graph([(uv[e][0],uv[e][1]) for e in st]); cl=sorted(nx.connected_components(Hs),key=len,reverse=True)
    print("   clusters (nodes):",[len(x) for x in cl[:8]], "names of biggest:",collections.Counter(A[e].get("name") for e in st if uv[e][0] in cl[0]).most_common(5))
