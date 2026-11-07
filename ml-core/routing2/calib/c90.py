# copy net_full2 -> net_full2_c90 with every signal program stretched from 60 s to 90 s (same splits)
import shutil,re,sys
src,dst=sys.argv[1],sys.argv[2]; shutil.copytree(src,dst,ignore=shutil.ignore_patterns("*.rou.xml"))
p=dst+"/quan4_v4.net.xml"; s=open(p).read(); n=0
def f(m):
    global n; n+=1; return f'{m.group(1)}"{float(m.group(2))*1.5:g}"'
s=re.sub(r'(<phase duration=)"([0-9.]+)"',f,s); open(p,"w").write(s); print("phases scaled",n)
