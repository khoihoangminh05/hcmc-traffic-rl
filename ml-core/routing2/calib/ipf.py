# Corridor-wise demand adjustment (audit C1). python ipf.py run <outdir> <iters>
# Each entry gate g has an inbound flow f_g, each exit zone z a weight x_z, plus an internal level. A gate's
# corridor = links on free-flow shortest paths from it to the zones (an exit's: from sampled core nodes to it).
# Per iteration: r_e = log TTI_mapbox - log TTI_sim on calibration links; log f_g += eta * mean r over its
# corridor, same for x_z, log internal += eta * mean r off all corridors; 8 step sizes x 2 seeds, keep the best.
import sys,json,math,random,collections,multiprocessing as mp
from pathlib import Path
import numpy as np, networkx as nx
sys.path.insert(0,"/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6")
import cal12b as C
M3=("--mesosim","true","--meso-junction-control","false","--meso-tls-penalty","1","--meso-tauff","0.57","--meso-taufj","0.57","--meso-taujf","0.87","--meso-taujj","0.7")
SD={"every":30.0,"a":1.55,"b":1.88,"k0":0.125}
def corridors(g):
    E=g.n_edges; src,dst=g.src.tolist(),g.dst.tolist(); tt=(g.length/g.v_free).tolist(); ids=g.edge_ids
    G=nx.DiGraph()
    for e in range(E): G.add_edge(src[e],dst[e],t=tt[e],e=e)
    zn=g.zone_nodes.tolist(); zx=g.zone_exit.tolist()[:len(zn)]
    internal=[zn[i] for i in range(len(zn)) if zx[i]<0]; rnd=random.Random(0); core=rnd.sample(g.scc_nodes.tolist(),60)
    gin=g.gate_in.tolist(); cin=[]
    for a in gin:
        pr=nx.single_source_dijkstra_path(G,a,weight="t"); c=collections.Counter()
        for z in internal+[zn[i] for i in range(len(zn)) if zx[i]>=0]:
            p=pr.get(z)
            if p: c.update(G[u][v]["e"] for u,v in zip(p,p[1:]))
        cin.append({ids[e]:n/sum(c.values()) for e,n in c.items()} if c else {})
    Gr=G.reverse(copy=False); cex={}
    for i in range(len(zn)):
        if zx[i]<0: continue
        pr=nx.single_source_dijkstra_path(Gr,zn[i],weight="t"); c=collections.Counter()
        for o in core:
            p=pr.get(o)
            if p: c.update(G[v][u]["e"] for u,v in zip(p,p[1:]))
        cex[i]={ids[e]:n/sum(c.values()) for e,n in c.items()} if c else {}
    return cin,cex
def resid(rows,T):
    S=collections.defaultdict(list)
    for r in rows:
        for e,v in r["speed"].items(): S[e].append(v)
    out={}
    for e,t in T.items():
        if t["half"]!="cal": continue
        st=max(C.REF.get(e,t["vf"])/np.mean(S[e]),1.0) if e in S else 1.0
        out[e]=math.log(t["tti"])-math.log(st)
    return out
def params(st,g):
    side=g.gate_in_side.tolist(); f=st["f"]
    gate=[sum(f[i] for i in range(len(f)) if side[i]==k) for k in range(4)]
    return {"internal":st["internal"],"gate":gate,"thr":st["thr"],"car":st["car"],"gin_w":[max(x,1e-6) for x in f],"exit_w":st["x"]}
def step(st,r,cin,cex,eta):
    def m(c):
        k=[e for e in c if e in r]; w=sum(c[e] for e in k)
        return sum(c[e]*r[e] for e in k)/w if w>0 else 0.0
    clip=lambda v:max(-.7,min(.7,v))
    n=dict(st); n["f"]=[min(8000.,max(30.,f*math.exp(clip(eta*m(cin[i]))))) for i,f in enumerate(st["f"])]
    n["x"]=[x*math.exp(clip(eta*m(cex[i]))) if i in cex else x for i,x in enumerate(st["x"])]
    allc=set().union(*[set(c) for c in cin],*[set(c) for c in cex.values()])
    off=[r[e] for e in r if e not in allc]; n["internal"]=min(15000.,max(500.,st["internal"]*math.exp(clip(eta*(np.mean(off) if off else 0)))))
    return n
if __name__=="__main__":
    from routing2.graph import load_graph
    from routing2.eval_heldout import worker_conf
    O=C.O; O.mkdir(parents=True,exist_ok=True); iters=int(sys.argv[3])
    g=load_graph(); cin,cex=corridors(g); T=C.target()
    print("corridors",len(cin),"gates",len(cex),"exits; targets",len(T),flush=True)
    saved=json.load(open(sorted(Path("/home/minhkhoi/hcmc-traffic-rl/ml-core/artifacts/out/quan4/routing2_runs").glob("sumo_marl_v10_selfish_*"))[0]/"args.json"))
    gj=json.load(open(C.NET+"/graph/alley_graph_full_z.json"))
    saved.update(burst_n=0,hotspots="",net_dir=C.NET,zones=len(gj["zones"]),horizon=C.H,incident_rate=2.0,school_rate=1.0)
    conf=worker_conf(saved,O/"work")
    nside=collections.Counter(g.gate_in_side.tolist())
    st={"internal":4000.,"thr":.6,"car":.15,"f":[2500./nside[k] for k in g.gate_in_side.tolist()],"x":[1.0]*len(g.zone_nodes)}
    task=lambda i,p,s:{"id":i,"p":p,"seed":s,"sumo":M3,"teleport":300,"sd":SD}
    hist=[]
    with mp.get_context("spawn").Pool(16,C.init,(conf,)) as pool:
        rows=pool.map(C.run,[task("ref",{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1},40000)]+[task("it0",params(st,g),s) for s in (40000,40001)],chunksize=1)
        bad=[r for r in rows if "err" in r]
        if bad: print("ERR",bad[0]["err"]); sys.exit(1)
        for e in {k for k in rows[0]["speed"]}: C.REF[e]=rows[0]["speed"][e]
        cur=rows[1:]; best={"st":st,"cal":C.score(cur,T,"cal"),"test":C.score(cur,T,"test")}
        print("it0",json.dumps({k:best[k] for k in ("cal","test")}),flush=True)
        ETA=[.25,.5,1.,1.5,2.,3.,4.,6.]
        for it in range(1,iters+1):
            r=resid(cur,T); cand=[step(best["st"],r,cin,cex,e) for e in ETA]
            rows=pool.map(C.run,[task(f"it{it}_{j}",params(c,g),s) for j,c in enumerate(cand) for s in (40000,40001)],chunksize=1)
            res=[]
            for j,c in enumerate(cand):
                rs=[x for x in rows if x["id"]==f"it{it}_{j}" and "err" not in x]
                if len(rs)<2: continue
                res.append((C.score(rs,T,"cal"),C.score(rs,T,"test"),c,rs,ETA[j],np.mean([x["arr"] or 0 for x in rs])))
            res.sort(key=lambda x:x[0]["loss"]); sc,tc,c,rs,eta,arr=res[0]
            line={"it":it,"eta":eta,"arr":round(float(arr),3),"cal":sc,"test":tc,"internal":round(c["internal"]),"gate_tph":[round(v) for v in params(c,g)["gate"]],
                  "all_cal_loss":[round(x[0]["loss"],3) for x in sorted(res,key=lambda x:x[4])]}
            print(json.dumps(line),flush=True); hist.append(line)
            if sc["loss"]<best["cal"]["loss"]: best={"st":c,"cal":sc,"test":tc}; cur=rs
            else: print("no improvement; stop",flush=True); break
            json.dump({"best":best,"hist":hist},open(O/"ipf.json","w"))
    json.dump({"best":best,"hist":hist},open(O/"ipf.json","w")); print("IPF_DONE",flush=True)
