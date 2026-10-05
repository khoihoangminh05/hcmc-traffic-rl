"""Parse HCMC Map.aspx HTML for camera-related hints."""
from __future__ import annotations

import re
from pathlib import Path

html = Path(r"C:\Users\ADMIN\AppData\Local\Temp\hcmc_map.html").read_text(encoding="utf-8", errors="ignore")

print("=== Captions ===")
for c in re.findall(r'"Caption":"([^"]{1,120})"', html):
    low = c.lower()
    if any(k in low for k in ("cam", "cctv", "hình", "camera", "an ninh", "giao thông")):
        print(c)

print("\n=== ImageHandler ===")
for m in re.findall(r"ImageHandler[^\"']{0,100}", html):
    print(m[:120])

print("\n=== Layer names with Cam ===")
for m in re.findall(r'"LayerName":"([^"]+)"', html):
    if "CAM" in m.upper() or "CAMERA" in m.upper():
        print(m)

js = Path(r"C:\Users\ADMIN\AppData\Local\Temp\CameraPlayerView.js")
if js.exists():
    text = js.read_text(encoding="utf-8", errors="ignore")
    print("\n=== CameraPlayerView snippets ===")
    for pat in ("ImageHandler", "VideoUrl", "buildHtml", "m3u8", "render/"):
        idx = text.find(pat)
        if idx >= 0:
            print("---", pat, "---")
            print(text[max(0, idx - 80) : idx + 160].replace("\n", " ")[:240])
