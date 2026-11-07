# OD design v3: pick pairs (not zones). C = >=3 near-equal (<=1.2x), <=50% overlapping routes incl. one through-alley
# route (>=20% alley, no pocket) and one road-only route (<=5% alley). X = C-like pairs that cross a bridge/gate corridor.
# F = origin or destination inside a dead-end pocket (forced entry). Spread: each node used by at most 3 pairs.
import json,random,collections,math
import networkx as nx
from concurrent.futures import ProcessPoolExecutor
import od3
from od3 import g,und,core2,pocket,routes,init,G0
D=od3.D
gates={str(x) for x in G0["gates_in"]+G0["gates_out"]}
if __name__=="__main__":
    rnd=random.Random(1)
    cand=[n for n in g if n in core2 and und.degree(n)>=3]
    gin=[str(x) for x in G0["gates_in"] if str(x) in g]; gout=[str(x) for x in G0["gates_out"] if str(x) in g]
    pairs=set()
    while len(pairs)<16000:
        o,z=rnd.choice(cand),rnd.choice(cand)
        if o!=z: pairs.add((o,z))
    for _ in range(3000): pairs.add((rnd.choice(gin),rnd.choice(cand))); pairs.add((rnd.choice(cand),rnd.choice(gout)))
    pairs=sorted(pairs)
    with ProcessPoolExecutor(16,initializer=init,initargs=(g,)) as ex: res=dict(zip(pairs,ex.map(routes,pairs,chunksize=50)))
    C,X=[],[]
    for p,r in res.items():
        if not r or len(r[1])<3: continue
        if not (any(a>=.2 for _,a in r[1]) and any(a<=.05 for _,a in r[1])): continue
        (X if (p[0] in gates or p[1] in gates) else C).append((p,r))
    use=collections.Counter()
    def pick(L,n):
        out=[]
        for x in sorted(L,key=lambda x:(-len(x[1][1]),x[0])):
            cap=lambda v:8 if v in gates else 3
            if use[x[0][0]]<cap(x[0][0]) and use[x[0][1]]<cap(x[0][1]):
                out.append(x); use.update(x[0])
            if len(out)>=n: break
        return out
    Cs=pick(C,240); Xs=pick(X,80)
    # forced: origin or destination inside a pocket, other end anywhere in core
    pk=[n for n in pocket if n in g]
    F=[]
    while len(F)<160:
        a,b=rnd.choice(pk),rnd.choice(cand)
        if rnd.random()<.5: a,b=b,a
        try: nx.shortest_path(g,a,b,weight="t"); F.append((a,b))
        except nx.NetworkXNoPath: pass
    print(f"sampled {len(pairs)} | qualifying C {len(C)}, X {len(X)} | kept C {len(Cs)}, X {len(Xs)}, F {len(F)}")
    rr=lambda L:collections.Counter(len(x[1][1]) for x in L)
    print("routes per pair C",dict(sorted(rr(Cs).items())),"X",dict(sorted(rr(Xs).items())))
    print("median free-flow s C %.0f X %.0f"%(sorted(x[1][0] for x in Cs)[len(Cs)//2],sorted(x[1][0] for x in Xs)[len(Xs)//2]))
    spread=lambda L:max(f for f,_ in L[1][1])
    print("median slowest/fastest among kept routes C %.2f"%sorted(spread(x) for x in Cs)[len(Cs)//2])
    json.dump({"C":[{"o":p[0],"z":p[1],"t_ff":r[0],"routes":r[1]} for p,r in Cs],"X":[{"o":p[0],"z":p[1],"t_ff":r[0],"routes":r[1]} for p,r in Xs],
               "F":[{"o":a,"z":b} for a,b in F],"pocket":sorted(pocket),
               "criteria":{"ratio":1.2,"overlap":.5,"min_tt_s":120,"alley_route_share":.2,"road_route_share":.05,"max_pairs_per_node":3,"max_pairs_per_gate":8,"overlap_excludes_shared_head_tail":True}},
              open(D+"/od_v3.json","w"))
