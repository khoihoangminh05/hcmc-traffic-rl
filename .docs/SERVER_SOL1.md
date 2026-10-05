# Server sol1 — snapshot (cập nhật khi đổi máy)

> Metadata tại thời điểm ghi. **Luôn** `nvidia-smi` lại trước khi train.

## Hardware

| Item | Value |
|------|--------|
| OS | Ubuntu 24.04.4 LTS |
| CPU | 2× Intel Xeon Gold 6148 @ 2.40GHz |
| Cores | 40 physical / 80 threads, 2 NUMA |
| RAM | 125 GiB (+ Swap 21 GiB) |
| GPU | **2× NVIDIA RTX 4090** (~24 GB VRAM each) |
| Driver | 595.84 (CUDA compat 13.2) |
| System `nvcc` | 12.0 |

## Storage

| Mount | Size | Free (snapshot) | Dùng cho |
|-------|------|-----------------|----------|
| `/` | 92 GB | ~63 GB | hệ thống — tránh data lớn |
| `/home` | 641 GB | ~143 GB | code nhỏ; **không** dump checkpoint lớn |
| `/mnt/data8tb` | 7.3 TB | ~6.5 TB | **datasets, checkpoints, outputs, caches** |

## GPU policy

- Shared multi-user — **không** kill process người khác.
- Trước mỗi job: `nvidia-smi`.
- Ưu tiên GPU **nhàn** (thường physical GPU 1).
- Launch: `CUDA_VISIBLE_DEVICES=1 …` → trong process là `cuda:0`.

## User

- `minhkhoi` (UID/GID 1008/1009)
- Không `sudo pip` global; dùng venv/conda riêng.
- Không sửa CUDA/driver hệ thống trừ khi được phép rõ.

## Paths gợi ý cho project này

```text
# Code (nhẹ)
/home/minhkhoi/hcmc-traffic-rl/

# Output / cache (nặng)
/mnt/data8tb/minhkhoi/hcmc-traffic-rl/
  ├── artifacts/          # symlink hoặc copy graph+density
  ├── marl_runs/          # checkpoints + summary
  └── .cache/             # pip/torch cache nếu cần
```

## Liên kết

- Train từng bước: [TRAIN_NOW.md](./TRAIN_NOW.md)
- Nâng data sau v0: [ENV_UPGRADE_L1_L5.md](./ENV_UPGRADE_L1_L5.md)
