import sys,json,collections,numpy as np,sumolib
from scipy.stats import spearmanr
sys.argv=[sys.argv[0],"x","cal_meso"]
import importlib.util; sp=importlib.util.spec_from_file_location("c","/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6/cal12b.py"); c=importlib.util.module_from_spec(sp); sp.loader.exec_module(c)
T=c.target(); D=c.D
net=sumolib.net.readNet(D+"/net_full2/quan4_v4.net.xml")
G=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G["alleys"]
import networkx as nx
uv={e["alley_id"]:(str(e["u"]),str(e["v"])) for e in G["edge_list"]}
H=nx.DiGraph([uv[e] for e in uv]); gates={str(x) for x in G["gates_in"]+G["gates_out"]}
dg={}
for g in gates:
    for n,d in nx.single_source_shortest_path_length(H.to_undirected(),g,cutoff=30).items(): dg[n]=min(dg.get(n,99),d)
# betweenness on free-flow time (proxy for through flow)
for e in uv: H[uv[e][0]][uv[e][1]]["t"]=A[e]["length_m"]/A[e]["v_free"]
bt=nx.edge_betweenness_centrality(H,k=300,weight="t",seed=0)
rows=[]
for e,t in T.items():
    try: E=net.getEdge(e)
    except KeyError: continue
    to=E.getToNode()
    rows.append(dict(cls=t["cls"],tti=t["tti"],L=A[e]["length_m"],sig=to.getType()=="traffic_light",lanes=E.getLaneNumber(),
                     deg=len(to.getIncoming())+len(to.getOutgoing()),gate=dg.get(uv[e][1],99),btw=bt.get(uv[e],0),
                     sigup=E.getFromNode().getType()=="traffic_light"))
for cls in ["primary","secondary","tertiary","residential"]:
    r=[x for x in rows if x["cls"]==cls]; y=[x["tti"] for x in r]
    print(cls,len(r),{f:round(spearmanr([float(x[f]) for x in r],y)[0],2) for f in ["L","sig","sigup","lanes","deg","gate","btw"]},
          "| median TTI sig/nosig",round(np.median([x["tti"] for x in r if x["sig"]]),2) if any(x["sig"] for x in r) else None,round(np.median([x["tti"] for x in r if not x["sig"]]),2))
