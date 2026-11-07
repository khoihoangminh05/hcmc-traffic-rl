# Parse the AjaxPro camera list (public map page) and keep cameras around Quận 4.
import json,re,sys
t=open(sys.argv[1],encoding="utf-8").read()
t=re.sub(r'new Date\(Date\.UTC\([^)]*\)\)','null',t); t=re.sub(r'new Date\([^)]*\)','null',t)
# new Ajax.Web.DataTable(cols, rows) -> {"__cols":cols,"__rows":rows}
key="new Ajax.Web.DataTable("
parts=[]
while True:   # innermost first: the last occurrence contains no further table
    j=t.rfind(key)
    if j<0: break
    k=j+len(key); depth=1; st=False; esc=False; m=k
    while depth:
        ch=t[m]
        if st:
            if esc: esc=False
            elif ch=="\\": esc=True
            elif ch=='"': st=False
        elif ch=='"': st=True
        elif ch in "([{": depth+=1
        elif ch in ")]}": depth-=1
        m+=1
    t=t[:j]+'{"__dt":['+t[k:m-1]+']}'+t[m:]
t=t.replace("new Ajax.Web.DataTable","")
d=json.loads(t)
def tables(x):
    if isinstance(x,dict):
        if "__dt" in x:
            cols=[c[0] for c in x["__dt"][0]]; yield [dict(zip(cols,r)) for r in x["__dt"][1]]
        for v in x.values(): yield from tables(v)
    elif isinstance(x,list):
        for v in x: yield from tables(v)
tabs=list(tables(d)); big=max(tabs,key=len); print("tables",len(tabs),"camera rows",len(big)); print({k:str(v)[:70] for k,v in big[0].items()})
cams=[]
for r in big:
    loc=r.get("Location"); shp=None
    if isinstance(loc,dict) and "__dt" in loc:
        cols=[c[0] for c in loc["__dt"][0]]; rr=[dict(zip(cols,x)) for x in loc["__dt"][1]]; shp=rr[0].get("Shape") if rr else None
    m=re.findall(r'-?\d+\.\d+',str(shp)) if shp else []
    if len(m)<2: continue
    a,b=float(m[0]),float(m[1]); lon,lat=(a,b) if a>100 else (b,a)
    cams.append(dict(id=r.get("CamId"),code=r.get("Code"),title=r.get("Title"),name=r.get("DisplayName"),lon=lon,lat=lat,district=r.get("Disctrict"),status=r.get("CamStatus"),snap=r.get("SnapshotUrl"),ptz=r.get("PTZ")))
json.dump(cams,open(sys.argv[2],"w"),ensure_ascii=False,indent=0)
q=[c for c in cams if 106.690<=c["lon"]<=106.722 and 10.750<=c["lat"]<=10.772]
print("with coordinates",len(cams),"| in/near Q4 box",len(q))
for c in sorted(q,key=lambda c:c["lat"]): print(c["id"],"|",c["title"],"|",c["district"],"|",c["status"],"|",round(c["lon"],5),round(c["lat"],5))
