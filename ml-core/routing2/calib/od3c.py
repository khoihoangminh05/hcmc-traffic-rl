# OD v3 -> zones + pair lists in a graph JSON copy. Destinations limited (env cost grows with zones):
# <=40 destinations for C/X chosen greedily by qualifying pairs (>=250 m apart), <=10 pocket destinations for F.
import json,math,random,collections,sys
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); geo=G["nodes_geo"]
xy=lambda n:(float(geo[n]["lon"])*109300,float(geo[n]["lat"])*110574)
allq=json.load(open(D+"/od_v3_all.json")); pk=json.load(open(D+"/od3_pockets.json"))
CX=[("C",o,z,t,r) for o,z,t,r in allq["C_all"]]+[("X",o,z,t,r) for o,z,t,r in allq["X_all"]]
old=[str(z) for z in G["zones"]]; gates_out={str(x) for x in G["gates_out"]}
byz=collections.Counter(z for _,o,z,_,_ in CX)
dest=[]
for z,n in byz.most_common():
    if len(dest)>=40: break
    if z in gates_out or z in old: dest.append(z); continue   # exits/old zones cost nothing extra
    if all(math.dist(xy(z),xy(d))>=250 for d in dest if d not in gates_out): dest.append(z)
use=collections.Counter(); pairs={"C":[],"X":[]}
for typ,o,z,t,r in sorted(CX,key=lambda x:(-len(x[4]),x[1],x[2])):
    if z in dest and use[o]<3:
        pairs[typ].append([o,z,round(t,1),len(r)]); use[o]+=1
# F: pocket destinations with the most alley length behind them, >=250 m apart; origins anywhere in core
import networkx as nx
pocket=set(pk["pocket"]); core=[n for n in pk["core2"]]
und=nx.Graph(); A=G["alleys"]
for e in G["edge_list"]: und.add_edge(str(e["u"]),str(e["v"]),L=float(A[e["alley_id"]]["length_m"]))
h=und.subgraph(pocket); comps=sorted(nx.connected_components(h),key=lambda c:-sum(d["L"] for _,_,d in h.subgraph(c).edges(data=True)))
fz=[]
for c in comps:
    if len(fz)>=10: break
    # the deepest node of the pocket (farthest from its entrance)
    ent=[n for n in c if any(m not in pocket for m in und[n])] or list(c)
    dd=nx.multi_source_dijkstra_path_length(h.subgraph(c),ent,weight="L"); z=max(dd,key=dd.get)
    if all(math.dist(xy(z),xy(d))>=250 for d in fz): fz.append(z)
rnd=random.Random(3); F=[[rnd.choice(core),z] for z in fz for _ in range(16)]
zones=old+[z for z in dest+fz if z not in old]
out=dict(G); out["zones"]=zones; out["od_v3"]={"C":pairs["C"],"X":pairs["X"],"F":F,"pocket_dest":fz}
json.dump(out,open(D+"/net_full2/graph/alley_graph_full_v3.json","w"),ensure_ascii=False)
print("zones",len(old),"->",len(zones),"| C pairs",len(pairs["C"]),"X",len(pairs["X"]),"F",len(F),"| C/X destinations",len(dest),"pocket dest",len(fz))
print("routes per pair C",dict(collections.Counter(p[3] for p in pairs["C"])),"X",dict(collections.Counter(p[3] for p in pairs["X"])))
