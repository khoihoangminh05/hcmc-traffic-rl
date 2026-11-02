"""Static two-route example for .docs/paper/theory_merge.md: link-only marginal cost can lose to UE.

No dependencies: python -m routing2.theory_merge_example
"""

import math
D,q,tc,tf=0.5,0.10,4.0,2.0
k=tc-tf/2
c=lambda x: math.exp(-k*x)/tf
W=lambda x: 1/(c(x)-q) if c(x)>q else math.inf
A=lambda x: 60+20*x
B=lambda y: 50+100*y
TC=lambda x: x*A(x)+(D-x)*B(D-x)+q*W(x)
grid=[i*D/100000 for i in range(100001)]
def root(f):
    return min(grid,key=lambda x:abs(f(x)))
ue=root(lambda x:A(x)-B(D-x))
lm=root(lambda x:(60+40*x)-(50+200*(D-x)))
so=min(grid,key=TC)
for n,x in (("UE",ue),("link-only MC",lm),("true SO",so)):
    print(f"{n:13s} x={x:.4f} Q={x:.4f} cap={c(x):.4f} W={W(x):6.2f}s major={x*A(x)+(D-x)*B(D-x):7.3f} minor={q*W(x):6.3f} total={TC(x):7.3f} veh-s/s")
print("link-only vs UE %+.2f%%; SO vs UE %+.2f%%"%(100*(TC(lm)-TC(ue))/TC(ue),100*(TC(so)-TC(ue))/TC(ue)))
