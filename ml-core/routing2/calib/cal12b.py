# Calibrate demand v2 (internal, per-side gate flows, through share, car share) on the full-OSM net v2 so that
# per-link slowdown (TTI = free speed / space-mean speed, 900-2700 s of a steady hour) matches Mapbox 17-18h.
# Mapbox links are split by a hash into calibration and test halves; only the calibration half drives the search.
import json,multiprocessing as mp,os,sys,time,hashlib,random,math
from pathlib import Path
import numpy as np
D="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/diag_v6"; NET=os.environ.get("CAL_NET",D+"/net_full2"); O=Path(D)/sys.argv[2]
H,W0=2700.0,900.0
def init(conf):
    from routing2 import sumo_marl as M
    M._worker_init(conf)
def run(t):
    try: return _run(t)
    except Exception:
        import traceback; return {"id":t["id"],"seed":t["seed"],"err":traceback.format_exc()[-3000:]}
def _run(t):
    import xml.etree.ElementTree as ET
    from routing2 import sumo_marl as M
    from routing2.demand import make_demand_v2
    env,g,zones=M._W["env"],M._W["g"],M._W["zones"]; p=t["p"]
    out=O/f'ed_{t["id"]}_{t["seed"]}.xml'; add=O/f'add_{os.getpid()}.xml'
    add.write_text(f'<additional><edgeData id="ed" begin="{W0}" end="{H}" period="{H-W0}" file="{out}" excludeEmpty="true"/></additional>')
    env.cfg.extra_args=("-a",str(add))+tuple(t.get("sumo",())); env.cfg.bg_route="informed"
    M._W.setdefault("tele0",env.cfg.teleport_s); env.cfg.teleport_s=t.get("teleport",M._W["tele0"])   # workers are reused: always reset
    env.cfg.moto_length_m=t.get("moto_len"); env.cfg.moto_mingap_m=t.get("moto_gap"); env.cfg.moto_extra=t.get("moto_extra","")
    sd=t.get("sd",{}); env.cfg.sd_every_s=sd.get("every",0.0); env.cfg.sd_a=sd.get("a",1.0); env.cfg.sd_b=sd.get("b",2.0); env.cfg.sd_k0=sd.get("k0",.1)
    M._W.setdefault("lat0",env.cfg.lateral_m); env.cfg.lateral_m=-1 if "--mesosim" in t.get("sumo",()) else M._W["lat0"]   # meso has no sublanes
    import torch
    gw=torch.tensor(p["gin_w"]) if p.get("gin_w") else None; xw=torch.tensor(p["exit_w"]) if p.get("exit_w") else None
    d=make_demand_v2(g,zones,[t["seed"]],H,.15,p["internal"],tuple(p["gate"]),p["thr"],p["car"],gate_in_w=gw,exit_w=xw,internal_car_tph=p.get("icar",0.0))
    ok=car_ok(env,g); n0=len(d.cars[0]); d.cars[0]=[c for c in d.cars[0] if ok(c[1],c[2])]; dropped=n0-len(d.cars[0])
    env.cfg.sumo_seed=t["seed"]; env.cfg.horizon_s=H; env.cfg.incident_seed=t["seed"]; env.cfg.compliance=.9; env.cfg.record_link_wait=False
    t0=time.time(); ep=env.run(d,0,M._Score(live=True),record=False)
    sp={}
    for e in ET.parse(out).getroot().iter("edge"):
        ss=float(e.get("sampledSeconds",0)); v=float(e.get("speed",0))
        if ss>30 and v>0: sp[e.get("id")]=v
    os.remove(out)
    return {"id":t["id"],"seed":t["seed"],"p":p,"sd":t.get("sd",{}),"n_car_all":len(d.cars[0]),"speed":sp,"n_moto":int(d.dep_t.shape[1]),"n_car":len(d.cars[0]),
            "tele":ep.teleports,"car_dropped":dropped,"arr":ep.metrics.get("arrived_share_all"),"wall":time.time()-t0}
def car_ok(env,g):
    """(entry node, exit node) -> can a car drive from the link the env picks to the one it picks (SUMO passenger)."""
    from routing2 import sumo_marl as M
    if "car_ok" in M._W: return M._W["car_ok"]
    import sumolib,networkx as nx,torch
    net=sumolib.net.readNet(NET+"/quan4_v4.net.xml"); G=nx.DiGraph()
    for e in net.getEdges():
        if e.isSpecial() or not e.allows("passenger"): continue
        for f in e.getOutgoing():
            if f.allows("passenger") and any(c.getFromLane().allows("passenger") and c.getToLane().allows("passenger") for c in e.getOutgoing()[f]): G.add_edge(e.getID(),f.getID())
    road=g.priority.cpu()>=3; cache={}
    def ok(a,z):
        src=[e for e in env.out_edges[a].tolist() if e>=0 and bool(road[e])]
        dst=[k for k in torch.nonzero((env.dst==z)&road).squeeze(1).tolist()]
        if not src or not dst: return False
        u,v=env.eid[src[0]],env.eid[dst[0]]
        if (u,v) not in cache: cache[(u,v)]=u in G and v in G and nx.has_path(G,u,v)
        return cache[(u,v)]
    M._W["car_ok"]=ok; return ok
def target():
    import pandas as pd
    gj=json.load(open(NET+"/graph/alley_graph_full_z.json")); A=gj["alleys"]
    o=pd.read_csv(D+"/probe_full2/edge_obs.csv",usecols=["timestamp","alley_id","speed_mps"])
    tl=pd.to_datetime(o.timestamp)+pd.Timedelta(hours=7); o["h"]=tl.dt.hour
    o=o[tl.dt.dayofweek<5]   # weekdays only: on Sat/Sun 5h is slower than the evening peak in the Mapbox data
    # + typical (depart_at) on the 40 main-road and gate routes, Mon-Tue 9-10/11 (typical = live, AUDIT_SIM M2b)
    t2=pd.read_csv(D+"/typ_major_m/edge_obs.csv",usecols=["depart_at","alley_id","speed_mps"]); t2["h"]=t2.depart_at.str[11:13].astype(int)
    o=pd.concat([o[["alley_id","speed_mps","h"]],t2[["alley_id","speed_mps","h"]]])
    v5=o[o.h==5].groupby("alley_id").speed_mps.median(); n5=o[o.h==5].groupby("alley_id").size()
    vpm=o[o.h.isin([17,18])].groupby("alley_id").speed_mps.median(); npm=o[o.h.isin([17,18])].groupby("alley_id").size()
    T={}
    for e in vpm.index:
        if e in v5.index and e in A and A[e]["road_class"] in("primary","secondary","tertiary","residential") and n5[e]>=4 and npm[e]>=4:
            T[e]={"tti":float(v5[e]/vpm[e]),"cls":A[e]["road_class"],"vf":float(A[e]["v_free"]),
                  "half":"cal" if int(hashlib.sha1(e.encode()).hexdigest(),16)%2==0 else "test"}
    return T
REF={}   # edge -> mean speed in the low-demand reference run (the sim's own "5h")
def score(rows,T,half):
    by={}
    for r in rows:
        for e,v in r["speed"].items(): by.setdefault(e,[]).append(v)
    xs,ys,cl=[],[],[]
    for e,t in T.items():
        if t["half"]!=half and half!="all": continue
        r=REF.get(e,t["vf"])
        s=max(r/np.mean(by[e]),1.0) if e in by else 1.0   # sim TTI = low-demand speed / peak speed, like Mapbox 5h / 17-18h
        xs.append(math.log(s)); ys.append(math.log(t["tti"])); cl.append(t["cls"])
    xs,ys=np.array(xs),np.array(ys)
    from scipy.stats import spearmanr
    loss=float(np.mean((xs-ys)**2))
    med={c:(round(float(np.exp(np.median(xs[np.array(cl)==c]))),2),round(float(np.exp(np.median(ys[np.array(cl)==c]))),2)) for c in sorted(set(cl))}
    return {"loss":round(loss,4),"spearman":round(float(spearmanr(xs,ys)[0]),3),"n":len(xs),"class_median_sim_vs_mbx":med}
if __name__=="__main__":
    from routing2.eval_heldout import worker_conf
    mode=sys.argv[1]
    if mode=="rescore":   # rescore saved rows: rescore <run dir> <ref dir>
        T=target(); ref=json.load(open(Path(D)/sys.argv[3]/"rows.json")); ref=[r for r in ref if r["id"]=="ref"] or ref
        for e in {k for r in ref for k in r["speed"]}: REF[e]=float(np.mean([r["speed"][e] for r in ref if e in r["speed"]]))
        rows=json.load(open(O/"rows.json")); res=[]
        for i in sorted({r["id"] for r in rows}):
            rs=[r for r in rows if r["id"]==i]
            res.append({"id":i,"p":rs[0]["p"],"cal":score(rs,T,"cal"),"test":score(rs,T,"test"),"tele":np.mean([r["tele"] for r in rs]),"arr":round(float(np.mean([r["arr"] or 0 for r in rs])),3)})
        res.sort(key=lambda x:x["cal"]["loss"]); json.dump(res,open(O/"rescore.json","w"),indent=1)
        print("targets",len(T),"ref edges",len(REF))
        for x in res[:10]: print(json.dumps(x))
        sys.exit(0)
    O.mkdir(parents=True,exist_ok=False)
    saved=json.load(open(sorted(Path("/home/minhkhoi/hcmc-traffic-rl/ml-core/artifacts/out/quan4/routing2_runs").glob("sumo_marl_v10_selfish_*"))[0]/"args.json"))
    gj=json.load(open(NET+"/graph/alley_graph_full_z.json"))
    saved.update(burst_n=0,hotspots="",net_dir=NET,zones=len(gj["zones"]),horizon=H,incident_rate=2.0,school_rate=1.0)
    conf=worker_conf(saved,O/"work"); T=target()
    print("targets",len(T),{h:sum(1 for t in T.values() if t["half"]==h) for h in("cal","test")},flush=True)
    if mode=="fac":   # why B2 fails: chosen model at c20 / c4, speed-density layer off / weak, cars inside Q4 0 / 1500 / 3000 per hour
        J1=("--mesosim","true","--meso-junction-control","true")
        dem={"c20":{"internal":3307.,"gate":[2503.,2699.,1372.,920.],"thr":.74,"car":.15},"c4":{"internal":8693.,"gate":[3126.,1629.,1616.,1547.],"thr":.48,"car":.09}}
        P=[{"id":"ref","p":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1,"icar":300.}}]
        for d in dem:
            for sn,sd in (("off",{}),("weak",{"every":30.0,"a":.6,"b":1.0,"k0":.1})):
                for ic in (0.,1500.,3000.):
                    P.append({"id":f"{d}_{sn}_ic{int(ic)}","p":{**dem[d],"icar":ic},"sd":sd})
        for c in P: c.update(sumo=J1,teleport=300,moto_len=.5,moto_gap=.2)
        seeds=[40000]
    elif mode=="b2":   # step B2: meso + junction control + motorcycles 3 files; demand, cars inside Q4, speed-density layer
        rnd=random.Random(int(sys.argv[3])); J1=("--mesosim","true","--meso-junction-control","true")
        P=[{"id":"ref","p":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1,"icar":300.}}]
        for i in range(int(sys.argv[4])):
            P.append({"id":f"b{i}","p":{"internal":rnd.uniform(2000,10000),"gate":[rnd.uniform(1000,6000) for _ in range(4)],
                      "thr":rnd.uniform(.3,.9),"car":rnd.uniform(.05,.3),"icar":rnd.uniform(1000,6000)},
                      "sd":{"every":30.0,"a":rnd.uniform(0,1.5),"b":1.0,"k0":math.exp(rnd.uniform(math.log(.03),math.log(.2)))}})
        for c in P: c.update(sumo=J1,teleport=300,moto_len=.5,moto_gap=.2)
        seeds=[40000]
    elif mode=="vn":   # micro, sublane, local driving: weave and push in at junctions (vType), anti-deadlock v3
        dem={"c20":{"internal":3307.,"gate":[2503.,2699.,1372.,920.],"thr":.74,"car":.15},
             "c4":{"internal":8693.,"gate":[3126.,1629.,1616.,1547.],"thr":.48,"car":.09},
             "d14":{"internal":9662.,"gate":[2660.,2938.,3552.,3567.],"thr":.59,"car":.15},
             "ref":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1}}
        V={"polite":"",
           "vn1":'lcAssertive="3" lcImpatience="1" minGapLat="0.1" jmIgnoreFoeProb="0.2" jmIgnoreFoeSpeed="2" jmTimegapMinor="0.5"',
           "vn2":'lcAssertive="5" lcImpatience="1" lcPushy="1" minGapLat="0.05" jmIgnoreFoeProb="0.5" jmIgnoreFoeSpeed="4" jmTimegapMinor="0.2" jmIgnoreJunctionFoeProb="0.3"'}
        P=[{"id":f"{d}_{v}","p":dem[d],"sumo":("--ignore-junction-blocker","5","--time-to-impatience","20"),"teleport":120,"moto_extra":V[v]}
           for v in V for d in dem]
        seeds=[40000]
    elif mode=="moto":   # meso motorcycle storage fix: 1.9/0.5 (one file per lane) vs 0.5/0.2 (about 3 files)
        dem={"c20":{"internal":3307.,"gate":[2503.,2699.,1372.,920.],"thr":.74,"car":.15},
             "c4":{"internal":8693.,"gate":[3126.,1629.,1616.,1547.],"thr":.48,"car":.09},
             "d14":{"internal":9662.,"gate":[2660.,2938.,3552.,3567.],"thr":.59,"car":.15},
             "ref":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1}}
        J={"j0":("--mesosim","true","--meso-junction-control","false","--meso-tls-penalty","1","--meso-tauff","0.57","--meso-taufj","0.57","--meso-taujf","0.87","--meso-taujj","0.7"),
           "j1":("--mesosim","true","--meso-junction-control","true")}
        MO={"old":(None,None),"new":(.5,.2)}
        P=[{"id":f"{d}_{j}_{m}","p":dem[d],"sumo":J[j],"teleport":300,"moto_len":MO[m][0],"moto_gap":MO[m][1]}
           for j in J for m in MO for d in dem]
        seeds=[40000]
    elif mode=="sdlin":   # stable layer: b = 1, weak a, two k0, two demand levels, meso m3
        m3=("--mesosim","true","--meso-junction-control","false","--meso-tls-penalty","1","--meso-tauff","0.57","--meso-taufj","0.57","--meso-taujf","0.87","--meso-taujj","0.7")
        dem={"c20":{"internal":3307.,"gate":[2503.,2699.,1372.,920.],"thr":.74,"car":.15},"c4":{"internal":8693.,"gate":[3126.,1629.,1616.,1547.],"thr":.48,"car":.09}}
        P=[{"id":"ref","p":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1}}]
        for d in dem:
            for a_ in (.3,.6,1.):
                for k0 in (.05,.1):
                    P.append({"id":f"{d}_a{a_}_k{k0}","p":dem[d],"sd":{"every":30.0,"a":a_,"b":1.0,"k0":k0}})
        for c in P: c.update(sumo=m3,teleport=300)
        seeds=[40000]
    elif mode=="sd":   # meso m3 + speed-density layer: random search over (a, b, k0) and demand
        rnd=random.Random(int(sys.argv[3])); m3=("--mesosim","true","--meso-junction-control","false","--meso-tls-penalty","1",
            "--meso-tauff","0.57","--meso-taufj","0.57","--meso-taujf","0.87","--meso-taujj","0.7")
        P=[{"id":"ref","p":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1}}]
        for i in range(int(sys.argv[4])):
            P.append({"id":f"s{i}","p":{"internal":rnd.uniform(2000,10000),"gate":[rnd.uniform(1000,10000) for _ in range(4)],
                      "thr":rnd.uniform(.3,.9),"car":rnd.uniform(.05,.25)},
                      "sd":{"every":30.0,"a":rnd.uniform(.3,3.0),"b":rnd.uniform(1.0,3.0),"k0":math.exp(rnd.uniform(math.log(.01),math.log(.2)))}})
        for c in P: c.update(sumo=m3,teleport=300)
        seeds=[int(sys.argv[5]) if len(sys.argv)>5 else 40000]
    elif mode=="meso":   # SUMO mesoscopic edges (speed falls with density, no lane-level junction deadlock)
        dem={"c20":{"internal":3307.,"gate":[2503.,2699.,1372.,920.],"thr":.74,"car":.15},
             "c4":{"internal":8693.,"gate":[3126.,1629.,1616.,1547.],"thr":.48,"car":.09},
             "d14":{"internal":9662.,"gate":[2660.,2938.,3552.,3567.],"thr":.59,"car":.15},
             "d3":{"internal":2373.,"gate":[10443.,4186.,2587.,2296.],"thr":.49,"car":.15},
             "ref":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1}}
        base=("--mesosim","true","--meso-junction-control","true")
        half=("--meso-tauff","0.57","--meso-taufj","0.57","--meso-taujf","0.87","--meso-taujj","0.7")
        V={"m1":base,"m2":base+half,"m3":("--mesosim","true","--meso-junction-control","false","--meso-tls-penalty","1")+half}
        P=[{"id":f"{d}_{v}","p":dem[d],"sumo":V[v],"teleport":300} for v in V for d in dem]; seeds=[40000]
    elif mode=="search2":   # wide gate flows (bridges), anti-deadlock v3, plus the low-demand reference on the same net
        rnd=random.Random(int(sys.argv[3])); P=[{"id":"ref","p":{"internal":1500.,"gate":[150.]*4,"thr":.5,"car":.1}}]
        for i in range(int(sys.argv[4])):
            P.append({"id":f"d{i}","p":{"internal":rnd.uniform(2000,10000),"gate":[rnd.uniform(1000,12000) for _ in range(4)],
                      "thr":rnd.uniform(.3,.9),"car":rnd.uniform(.05,.25)}})
        for c in P: c.update(sumo=("--ignore-junction-blocker","5","--time-to-impatience","20"),teleport=120)
        seeds=[40000]
    elif mode=="sweep":   # junction-deadlock options at two demand levels (c20 low, c4 high of cal_r1)
        base={"c20":{"internal":3307.,"gate":[2503.,2699.,1372.,920.],"thr":.74,"car":.15},
              "c4":{"internal":8693.,"gate":[3126.,1629.,1616.,1547.],"thr":.48,"car":.09}}
        V={"v0":{},"v1":{"sumo":("--ignore-junction-blocker","10")},
           "v2":{"sumo":("--ignore-junction-blocker","10","--time-to-impatience","30")},
           "v3":{"sumo":("--ignore-junction-blocker","5","--time-to-impatience","20"),"teleport":120}}
        P=[{"id":f"{b}_{v}","p":base[b],**V[v]} for b in base for v in V]; seeds=[40000,40001]
    elif mode=="ref":   # low-demand reference: the sim's own free-ish state
        P=[{"id":"ref","p":{"internal":1500.,"gate":[150.,150.,150.,150.],"thr":.5,"car":.1}}]; seeds=[40000,40001]
    elif mode=="smoke":
        P=[{"id":"s0","p":{"internal":8000.,"gate":[2000.,2000.,2000.,2000.],"thr":.5,"car":.15}}]; seeds=[40000]
    else:
        rnd=random.Random(int(sys.argv[3]) if len(sys.argv)>3 else 0); P=[]
        for i in range(int(sys.argv[4]) if len(sys.argv)>4 else 32):
            P.append({"id":f"c{i}","p":{"internal":rnd.uniform(3000,16000),"gate":[rnd.uniform(300,6000) for _ in range(4)],
                      "thr":rnd.uniform(.2,.8),"car":rnd.uniform(0,.3)}})
        seeds=[40000,40001]
    ts=[{**c,"seed":s} for c in P for s in seeds]
    with mp.get_context("spawn").Pool(min(int(os.environ.get("CAL_POOL","16")),len(ts)),init,(conf,)) as pool: rows=pool.map(run,ts,chunksize=1)
    for r in rows:
        if "err" in r: print("ERR",r["id"],r["err"],flush=True)
    rows=[r for r in rows if "err" not in r]
    json.dump(rows,open(O/"rows.json","w"))
    res=[]
    for c in P:
        rs=[r for r in rows if r["id"]==c["id"]]
        res.append({"id":c["id"],"p":c["p"],"cal":score(rs,T,"cal"),"test":score(rs,T,"test"),
                    "moto":rs[0]["n_moto"],"car":rs[0]["n_car"],"car_dropped":rs[0]["car_dropped"],"tele":np.mean([r["tele"] for r in rs]),"arr":np.mean([r["arr"] or 0 for r in rs]),"wall":round(np.mean([r["wall"] for r in rs]))})
    res.sort(key=lambda x:x["cal"]["loss"]); json.dump(res,open(O/"result.json","w"),indent=1)
    for x in res[:8]: print(json.dumps(x),flush=True)
    print("CAL_DONE",flush=True)
