# Network facts for OD design v3: through vs dead-end alleys (pockets behind bridges), and how many OD pairs
# have >= 3 near-equal, mostly disjoint routes with at least one through-alley route and one road-only route.
import json,random,collections,math,sys
import networkx as nx
from concurrent.futures import ProcessPoolExecutor
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"
G0=json.load(open(D+"/net_full2/graph/alley_graph_full_z.json")); A=G0["alleys"]
g=nx.DiGraph()
for e in G0["edge_list"]:
    a=A[e["alley_id"]]; L=max(float(a["length_m"]),1.)
    g.add_edge(str(e["u"]),str(e["v"]),t=L/float(a.get("v_free") or 5),L=L,alley=a["road_class"] in("alley","service"),cls=a["road_class"])
und=nx.Graph(g.to_undirected())
road_nodes={n for u,v,d in g.edges(data=True) if not d["alley"] for n in (u,v)}
# pockets: remove bridges of the undirected graph; components without any road node are dead-end pockets
br=set(nx.bridges(und)); h=und.copy(); h.remove_edges_from(br)
pocket=set()
for comp in nx.connected_components(h):
    if not comp & road_nodes: pocket|=comp
# a pocket may hang off another pocket through a bridge: everything not 2-edge-connected to roads
# (iterate: nodes whose every path to a road passes a bridge)
core2=set().union(*[c for c in nx.connected_components(h) if c & road_nodes])
pocket=set(und)-core2
alley_e=[(u,v) for u,v,d in g.edges(data=True) if d["alley"]]
alley_L=sum(g[u][v]["L"] for u,v in alley_e)
dead_L=sum(g[u][v]["L"] for u,v in alley_e if u in pocket or v in pocket)
print(f"nodes {g.number_of_nodes()} | alley length {alley_L/1000:.1f} km, of which in dead-end pockets {dead_L/1000:.1f} km ({dead_L/alley_L:.0%})")
print(f"pocket nodes {len(pocket)} ({len(pocket)/g.number_of_nodes():.0%}); through-alley edges {sum(1 for u,v in alley_e if u not in pocket and v not in pocket)}")
_g=None
def init(x):
    global _g; _g=x
def routes(pair,k=6,ratio=1.2,ovl=.5):
    o,z=pair; g=_g
    try: p0=nx.shortest_path(g,o,z,weight="t")
    except nx.NetworkXNoPath: return None
    E=lambda p:list(zip(p,p[1:])); T=lambda p:sum(g[a][b]["t"] for a,b in E(p)); Lp=lambda p:sum(g[a][b]["L"] for a,b in E(p))
    t0=T(p0)
    if t0<120: return None
    pen=collections.Counter(); out=[p0]
    for _ in range(k*2):
        for a,b in E(out[-1]): pen[(a,b)]+=1
        q=nx.shortest_path(g,o,z,weight=lambda a,b,d:d["t"]*(1.6**pen[(a,b)]))
        if T(q)>ratio*t0: break
        Sq=set(E(q))
        # links every route must use (shared head and tail, e.g. a bridge approach) do not count as overlap
        common=set(E(p0)).intersection(*[set(E(p)) for p in out]) & Sq
        def ov(p):
            sh=(Sq&set(E(p)))-common; den=min(Lp(p),Lp(q))-sum(g[a][b]["L"] for a,b in common)
            return sum(g[a][b]["L"] for a,b in sh)/max(den,1.)
        if all(ov(p)<=ovl for p in out): out.append(q)
        if len(out)>=k: break
    feats=[]
    for p in out:
        al=sum(g[a][b]["L"] for a,b in E(p) if g[a][b]["alley"])/Lp(p)
        feats.append((round(T(p)/t0,3),round(al,2)))
    return t0,feats
if __name__=="__main__":
    rnd=random.Random(0)
    cand=[n for n in g if n in core2 and und.degree(n)>=3]
    pairs=[(rnd.choice(cand),rnd.choice(cand)) for _ in range(3000)]; pairs=[p for p in pairs if p[0]!=p[1]]
    with ProcessPoolExecutor(16,initializer=init,initargs=(g,)) as ex: res=list(ex.map(routes,pairs,chunksize=20))
    ok=[r for r in res if r]; n3=[r for r in ok if len(r[1])>=3]
    both=[r for r in n3 if any(a>=.2 for _,a in r[1]) and any(a<=.05 for _,a in r[1])]
    print(f"pairs with t>=120 s: {len(ok)} | >=3 routes within 1.2x, overlap<=50%: {len(n3)} ({len(n3)/len(ok):.0%}) | of those with an alley route (>=20% alley) AND a road-only route (<=5%): {len(both)} ({len(both)/len(ok):.0%})")
    hist=collections.Counter(len(r[1]) for r in ok); print("routes per pair:",dict(sorted(hist.items())))
    json.dump({"pocket":sorted(pocket),"core2":sorted(core2)},open(D+"/od3_pockets.json","w"))
