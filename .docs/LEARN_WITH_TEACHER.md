# Học cùng lúc train — cách đọc số & quyết định

Bạn không cần thuộc hết. Mỗi lần train xong, mở `summary.json` và trả lời **4 câu** bên dưới.  
Gửi mình file đó — mình sẽ cùng bạn đọc như buổi chữa bài.

---

## 1. Bức tranh lớn (1 phút)

Hệ đang học: với thời điểm `t` và cặp (O→D), chọn **prefer đường lớn** hay **prefer hẻm** để travel time thấp.

| Vai | Ý nghĩa đời thực |
|-----|------------------|
| **Oracle** | “Đáp án giáo khoa”: thử cả 2 kiểu chọn, lấy cái nhanh hơn. Đây là **sàn** (không có model nào đánh bại oracle kiểu này trên đúng 1 bit action). |
| **Policy (agent)** | Mạng neural đoán nên chọn 0 hay 1. |
| **Regret** | `travel_policy − travel_oracle` (giây). **Càng gần 0 càng giỏi.** |

Nếu regret ≈ 0 trên test → agent gần như luôn chọn đúng như oracle.  
Nếu regret lớn → agent hay chọn sai (hoặc data/`k` nhiễu).

---

## 2. Đọc log lúc đang train

### Dòng `[train]`
```text
[train] 12/200 | return=-520.3 travel=520.3s | loss=12.4 | lr=3.00e-04 ent=0.0200
```

| Số | Nghĩa | Đọc sao cho đúng |
|----|--------|------------------|
| `return` | Thưởng ≈ **−travel_time** | Tăng dần (ít âm hơn) = đang đi nhanh hơn trên tập train |
| `travel` | Thời gian trung bình (giây) episode train | Giảm = tốt trên train |
| `loss` | Tổn thất PPO | Được phép nhảy; **đừng** chỉ nhìn loss để kết luận “học tốt” |
| `lr` | Learning rate | Nhỏ dần khi adapt plateau — bình thường |
| `ent` | Entropy (độ “tò mò”) | Cao = thử nhiều; thấp = quyết đoán hơn |

**Bẫy học viên:** train travel giảm mạnh nhưng val xấu = **học vẹt** (overfit). Vì vậy phải có `[eval]`.

### Dòng `[eval]`
```text
[eval] val_travel=640.3s | oracle=587.6s | regret=52.7s | acc=53% | best=640.3s
```

| Số | Nghĩa | Quyết định |
|----|--------|------------|
| `val_travel` | Thời gian trung bình trên OD **validation** (chưa dùng để update trực tiếp mỗi step) | Metric chính — **càng thấp càng tốt** |
| `oracle` | Sàn lý thuyết trên cùng OD/val | Không đổi nhiều giữa các update (cùng data) |
| `regret` | `val_travel − oracle` | Mục tiêu thực dụng: kéo xuống |
| `acc` | % lần chọn đúng action của oracle | ~50% ≈ đoán bừa (2 class); >60–70% bắt đầu có tín hiệu |
| `best` | `val_travel` tốt nhất từ đầu | Early-stop dựa vào đây |

### Dòng `[adapt]`
Hệ thấy val không cải thiện → giảm `lr` / `entropy`, hoặc kéo tham số về bản “best”.  
→ Đây là **phanh tự động**, không phải lỗi.

### Kết thúc
- `ROBUST_TRAIN_OK` = pipeline chạy hết, không crash.  
- **Không** đồng nghĩa “model đã đủ paper”. Xem `summary.json`.

---

## 3. Đọc `summary.json` (bài kiểm tra)

Ví dụ các field quan trọng:

```json
{
  "data_tag": "v0_seed120_mixed_day",
  "best_val_travel_time": 640.3,
  "test_travel_time": 559.8,
  "test_oracle_travel_time": 508.4,
  "test_regret": 51.3,
  "test_action_acc": 0.50,
  "stop_reason": "early_stop: ..." ,
  "updates_ran": 85
}
```

### Bốn câu bạn tự hỏi (rồi hỏi thầy)

1. **Regret test bao nhiêu giây?**  
   - &lt; 20s trên OD dài: khá  
   - ~ oracle gap 50–80s và acc ~50%: **chưa học được**, chỉ mới chạy máy  
2. **`stop_reason` là gì?**  
   - `early_stop`: val đứng — đúng ý thiết kế  
   - `max_updates`: hết budget — có thể tăng updates *sau khi* data ổn  
3. **`data_tag` là gì?**  
   - Luôn ghi vào sổ: số này thuộc **môi trường data nào** (v0/v1…)  
4. **Test tốt hơn val nhiều / ngược lại?**  
   - Chênh lệch lớn: split may rủi hoặc data nhiễu → không vội claim

---

## 4. Quyết định bước tiếp (cùng thầy)

| Bạn thấy | Việc nên làm |
|----------|----------------|
| Crash / CUDA OOM / missing file | Sửa môi trường chạy — **chưa** đụng L1–L5 |
| Chạy xong, acc ~50%, regret lớn | Bình thường với **v0**; giữ checkpoint làm baseline, sang **L1** |
| Acc tăng, regret giảm rõ qua các update | Pipeline học được tín hiệu → có thể train dài hơn hoặc sang L1/L2 |
| Train tốt, val xấu | Overfit / data mix → L1 time-bucket, đừng tăng model trước |
| Muốn paper mạnh hơn | Không train thêm 10 buổi trên v0; làm [ENV_UPGRADE_L1_L5.md](./ENV_UPGRADE_L1_L5.md) |

---

## 5. Từ vựng “thầy hay dùng”

- **Baseline:** run v0 đầu tiên — cột mốc để so sau này.  
- **Ablation:** tắt/bật một thành phần (vd. camera secondary) xem số đổi ra sao.  
- **Distribution shift:** data train khác data thật → model “giỏi trên giấy”.  
- **Primary vs secondary signal:** trong hẻm = Mapbox+nội suy; camera = phụ (không nhìn vào hẻm).

---

## 6. Việc của bạn / việc của thầy

**Bạn:** chạy lệnh, gửi `summary.json` + vài dòng log `[eval]` cuối.  
**Thầy (mình):** giải thích số đó nghĩa là gì, khen/phê đúng chỗ, chỉ **một** việc tiếp theo (đừng ôm cả L1–L5 cùng lúc).

Không sao nếu lần đầu “chưa hiểu hết” — hiểu sâu đến từ **nhiều vòng đọc số thật**, không từ đọc lý thuyết một mạch.
