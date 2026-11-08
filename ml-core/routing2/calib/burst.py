# Finite capture for step 1 (signal cycles, flow): every 20 s one frame per Q4 camera, sequentially (about 1 request/s),
# in the windows below, Mon 9 Nov to Fri 13 Nov 2026 (VN time). Exits after the last window. Portal frames refresh about every 12 s.
import json,time,urllib.request,os,datetime as dt
OUT="/mnt/data8tb/minhkhoi/hcmc-traffic-rl/ingestion/data_raw/camera_burst"
cams=[c for c in json.load(open(os.path.expanduser("~/hcmc-traffic-rl/ingestion-worker/config/cameras.quan4_real.json"))) if c["cameraId"].startswith("q4_")]
VN=dt.timezone(dt.timedelta(hours=7))
W=[(dt.datetime(2026,11,d,a,b,tzinfo=VN),dt.datetime(2026,11,d,c,e,tzinfo=VN)) for d in range(9,14) for a,b,c,e in ((7,0,8,30),(11,30,12,0),(16,30,18,30))]
for s,e in W:
    while dt.datetime.now(VN)<s: time.sleep(min(60,(s-dt.datetime.now(VN)).total_seconds()+1))
    while dt.datetime.now(VN)<e:
        t0=time.time()
        for c in cams:
            now=dt.datetime.now(VN); d=f"{OUT}/{c['cameraId']}/{now:%Y-%m-%d}"; os.makedirs(d,exist_ok=True)
            try:
                r=urllib.request.Request(c["url"],headers={"User-Agent":"Mozilla/5.0"})
                open(f"{d}/{now:%H-%M-%S}.jpg","wb").write(urllib.request.urlopen(r,timeout=8).read())
            except Exception as x: print(now,c["cameraId"],x,flush=True)
        time.sleep(max(0,20-(time.time()-t0)))
print("BURST_DONE",flush=True)
