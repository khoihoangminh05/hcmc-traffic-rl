# K1/K2 first look on OD v3: ff, app, greedy_load with the fleet on C/X pairs at three fleet sizes, on the
# "most reasonable" sim (meso m3 + linear speed-density layer, c4-level background incl. other districts,
# forced dead-end entries from F pairs). python k1.py run <outdir>
import json,sys,time,multiprocessing as mp
from pathlib import Path
import numpy as np
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"; NET=D+"/net_full2"; O=Path(D)/sys.argv[2]
H=2700.0
M3=("--mesosim","true","--meso-junction-control","false","--meso-tls-penalty","1","--meso-tauff","0.57","--meso-taufj","0.57","--meso-taujf","0.87","--meso-taujj","0.7")
BG={"internal":3307.,"gate":(2503.,2699.,1372.,920.),"thr":.74,"car":.15}   # c20 level
SDS={"weak":(.6,.1),"real":(1.,.05)}   # (a, k0), b = 1; "real" gives class TTI near Mapbox (cal_sdlin)
def init(conf):
    from routing2 import sumo_marl as M
    M._worker_init(conf)
    from routing2.demand import load_od_v3
    M._W["od3"]=load_od_v3(M._W["g"])
def run(t):
    try: return _run(t)
    except Exception:
        import traceback; return {**t,"err":traceback.format_exc()[-2000:]}
def _run(t):
    from routing2 import sumo_marl as M
    from routing2.demand import make_demand_v2
    env,g,zones,od=M._W["env"],M._W["g"],M._W["zones"],M._W["od3"]
    d=make_demand_v2(g,zones,[t["seed"]],H,0.0,BG["internal"],BG["gate"],BG["thr"],BG["car"],
                     fleet_pairs=od["C"]+od["X"],fleet_tph=t["fleet"],forced_pairs=od["F"],forced_tph=600.,bg_zones=47)
    ok=car_ok(env,g); d.cars[0]=[c for c in d.cars[0] if ok(c[1],c[2])]
    env.cfg.extra_args=M3; env.cfg.lateral_m=-1; env.cfg.bg_route="informed"; env.cfg.teleport_s=300
    env.cfg.sd_every_s=30.; env.cfg.sd_a,env.cfg.sd_k0=SDS[t["sd"]]; env.cfg.sd_b=1.
    env.cfg.sumo_seed=t["seed"]; env.cfg.horizon_s=H+300; env.cfg.incident_seed=t["seed"]; env.cfg.compliance=.9; env.cfg.record_link_wait=True
    pol=M._Score(live=t["policy"] in("app","greedy"),queue_s=.5 if t["policy"]=="greedy" else 0.)
    t0=time.time(); ep=env.run(d,0,pol,record=False)
    w=np.asarray(ep.link_wait_s,dtype=np.float64); al=g.is_alley.cpu().numpy()
    top=np.argsort(-w)[:15]
    rn=np.asarray(env._report_n,dtype=np.float64); L=g.length.cpu().numpy()
    fleet_alley_km=float((rn*L)[al].sum()/1000); fleet_km=float((rn*L).sum()/1000)
    mech={"fleet_alley_share":fleet_alley_km/max(fleet_km,1e-9),"wait_alley_s":float(w[al].sum()),"wait_road_s":float(w[~al].sum()),"top":[[g.edge_ids[i],bool(al[i]),round(float(w[i]))] for i in top]}
    return {**t,"mech":mech,"metrics":ep.metrics,"n_ctrl":ep.n_ctrl,"tt_ctrl":ep.ttt_ctrl_s/max(1,ep.n_ctrl),"wall":time.time()-t0,"tele":ep.teleports}
def car_ok(env,g):
    from routing2 import sumo_marl as M
    if "car_ok" in M._W: return M._W["car_ok"]
    import sumolib,networkx as nx,torch
    net=sumolib.net.readNet(NET+"/quan4_v4.net.xml"); G=nx.DiGraph()
    for e in net.getEdges():
        if e.isSpecial() or not e.allows("passenger"): continue
        for f in e.getOutgoing():
            if f.allows("passenger"): G.add_edge(e.getID(),f.getID())
    road=g.priority.cpu()>=3; cache={}
    def ok(a,z):
        src=[e for e in env.out_edges[a].tolist() if e>=0 and bool(road[e])]
        dst=[k for k in torch.nonzero((env.dst==z)&road).squeeze(1).tolist()]
        if not src or not dst: return False
        u,v=env.eid[src[0]],env.eid[dst[0]]
        if (u,v) not in cache: cache[(u,v)]=u in G and v in G and nx.has_path(G,u,v)
        return cache[(u,v)]
    M._W["car_ok"]=ok; return ok
if __name__=="__main__":
    from routing2.eval_heldout import worker_conf
    from routing2.objectives import objective
    O.mkdir(parents=True,exist_ok=False)
    saved=json.load(open(sorted(Path("/home/minhkhoi/hcmc-traffic-rl/ml-core/artifacts/out/quan4/routing2_runs").glob("sumo_marl_v10_selfish_*"))[0]/"args.json"))
    gj=json.load(open(NET+"/graph/alley_graph_full_v3.json"))
    saved.update(burst_n=0,hotspots="",net_dir=NET,zones=len(gj["zones"]),horizon=H,incident_rate=2.0,school_rate=1.0)
    conf=worker_conf(saved,O/"work")
    FL=[float(x) for x in sys.argv[3].split(",")] if len(sys.argv)>3 else [1500.,3000.,6000.]
    SD=[int(x) for x in sys.argv[4].split(",")] if len(sys.argv)>4 else [40000,40001]
    ts=[{"policy":p,"fleet":f,"seed":s,"sd":sd} for sd in SDS for s in SD for f in FL for p in ("ff","app","greedy")]
    with mp.get_context("spawn").Pool(16,init,(conf,)) as pool: rows=pool.map(run,ts,chunksize=1)
    for r in rows:
        if "err" in r: print("ERR",r["policy"],r["fleet"],r["err"],flush=True)
    rows=[r for r in rows if "err" not in r]; json.dump(rows,open(O/"rows.json","w"))
    for sd,f in [(a,b) for a in SDS for b in FL]:
        out={"sd":sd}
        for p in ("ff","app","greedy"):
            m=[r for r in rows if r["fleet"]==f and r["policy"]==p and r["sd"]==sd]
            if not m: continue
            out[p]={"J":round(float(np.mean([objective(r["metrics"],.5) for r in m])),1),"T_cust":round(float(np.mean([r["metrics"].get("mean_tt_cust_s",r["tt_ctrl"]) for r in m])),1),
                     "arr":round(float(np.mean([r["metrics"]["arrived_share_all"] for r in m])),3),
                     "n_ctrl":int(np.mean([r["n_ctrl"] for r in m])),"J_seeds":[round(objective(r["metrics"],.5)) for r in sorted(m,key=lambda r:r["seed"])],
                     "alley_share":round(float(np.mean([r["mech"]["fleet_alley_share"] for r in m])),3),"T_all":round(float(np.mean([r["metrics"]["T_all_s"] for r in m])),1),"wait_alley_ks":round(float(np.mean([r["mech"]["wait_alley_s"] for r in m]))/1000),"wait_road_ks":round(float(np.mean([r["mech"]["wait_road_s"] for r in m]))/1000),"wall":round(float(np.mean([r["wall"] for r in m])))}
        print(json.dumps({"fleet_tph":f,**out}),flush=True)
    print("K1_DONE",flush=True)
