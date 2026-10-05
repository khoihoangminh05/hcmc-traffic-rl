import json
from pathlib import Path
from collections import Counter

root = Path("ml-core/artifacts/out/quan4/density")
meta = json.loads((root / "density_meta.json").read_text(encoding="utf-8"))
print("=== META ===")
print(json.dumps(meta, indent=2, ensure_ascii=False))

rows = json.loads((root / "alley_density_latest.json").read_text(encoding="utf-8"))
print("\n=== COUNTS ===")
print("alleys", len(rows))
print("source", dict(Counter(r["source"] for r in rows)))
ks = [r["density_k"] for r in rows]
vs = [r["speed_mps"] for r in rows]
print(
    "density_k min/mean/max = "
    f"{min(ks):.4f} / {sum(ks)/len(ks):.4f} / {max(ks):.4f}"
)
print(
    "speed_mps min/mean/max = "
    f"{min(vs):.2f} / {sum(vs)/len(vs):.2f} / {max(vs):.2f}"
)

obs = [r for r in rows if r["source"] == "observed"]
print("\n=== OBSERVED top-5 by density ===")
for r in sorted(obs, key=lambda x: -x["density_k"])[:5]:
    name = (r.get("name") or "")[:30]
    print(
        f"{r['alley_id'][:42]:42} k={r['density_k']:.4f} "
        f"v={r['speed_mps']:.2f} name={name}"
    )

print("\n=== FILES ===")
for p in sorted(root.glob("*")):
    print(p.name, p.stat().st_size)
gj = root / "quan4_density_latest.geojson"
if gj.exists():
    feat = json.loads(gj.read_text(encoding="utf-8"))["features"]
    print("geojson_features", len(feat))
