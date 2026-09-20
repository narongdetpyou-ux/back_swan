# Real-World Validation Phase 1 — Dataset Contract

สถานะ: **COMPLETE — Dataset Contract implemented and validated**

หลักฐานปิด Phase 1:

- commit `69d35a1f6a7e7e6eca6189ede035a0c8f9526428`
- contract unit tests 6/6 ผ่าน
- full repository regression 85/85 ผ่าน
- GitHub Actions run `35483126146` สำเร็จ
- known-good fixture ผ่าน และ overlap fixture ถูก reject

คำว่า COMPLETE หมายถึง dataset admission contract พร้อมใช้งานเท่านั้น ยังไม่ดำเนิน Attack Plan / ATT&CK scenario design, ยังไม่มี admitted real-world dataset และยังไม่เริ่ม Phase 2 execution

## เป้าหมาย

Phase 1 ปิดช่องว่างระหว่าง synthetic benchmark กับการประเมินบน telemetry ที่มาจากระบบจริงหรือ controlled environment โดยยังไม่เปลี่ยน Logic v8 และยังไม่ใช้ผล blind test เพื่อปรับ threshold

หลักฐานเดิมที่ใช้เป็นฐาน:
- benchmark v6 ใช้ deterministic synthetic hourly aggregate telemetry และ metric 10 ตัว
- v8 มี regression/fault/runtime evidence แต่ repository ระบุว่ายังไม่มี real cybersecurity traffic replay ที่เหมาะกับ metric contract และ labels อิสระ
- ดังนั้นขั้นนี้สร้าง **dataset admission contract** ก่อนรับข้อมูลจริง

## Metric compatibility

เพื่อไม่ให้ Phase 1 กลายเป็นการเปลี่ยน model พร้อมกับเปลี่ยน dataset ให้ใช้ metric catalog ที่มีอยู่เดิม:

- auth_failures
- unique_failed_accounts
- unique_source_ips
- successful_logins
- privileged_changes
- outbound_mb
- api_5xx
- endpoint_alerts
- file_rename_events
- inbound_requests

Dataset ไม่จำเป็นต้องมีครบทุก metric แต่ทุก metric ที่เลือกต้อง map กลับมายัง catalog นี้อย่างชัดเจนใน manifest ถ้าไม่มีข้อมูลให้คงสถานะ missing/suppressed/failed ตาม contract ของ v8 แทนการแทนด้วยเลขศูนย์

## Split policy

ใช้ chronological split เท่านั้น:

1. `baseline` — อดีตที่ใช้สร้าง history/baseline
2. `calibration` — ช่วงที่อนุญาตให้กำหนด calibration ตามแผนการทดลอง
3. `blind_test` — final holdout ที่ล็อกก่อนประเมิน

กฎ:
- ช่วงเวลาห้าม overlap
- ต้องเรียง baseline → calibration → blind_test
- `blind_test_locked=true` ก่อน evaluation
- ห้ามนำ blind-test outcome ไปปรับ threshold แล้วรายงานซ้ำว่าเป็น holdout เดิม

ตัว validator ไม่บังคับสัดส่วนวัน 7/3/4; ตัวเลขนั้นเป็นเพียงตัวอย่าง รูปแบบจริงต้องขึ้นกับ cadence และปริมาณข้อมูลจริง

## Ground-truth separation

manifest ต้องมี input แยกสามบทบาท:

- `raw`: source evidence
- `features`: engine input ที่ได้จาก transformation ที่ระบุ version/ID
- `labels`: hidden ground truth

Labels ต้อง:
- ไม่ถูกส่งให้ engine
- มี `independent_of_predictions=true`
- ระบุ `adjudication_method`
- เก็บ predictions แยกจาก labels

Phase 1 **ยังไม่กำหนดชนิด attack, ATT&CK technique หรือ scenario** เพราะเป็นงานส่วนที่ 2 ที่ยังไม่เริ่ม

## Provenance / evidence

ทุก input ต้องบันทึก:
- path หรือ private URI
- byte size
- SHA-256
- source system
- collection start/end เป็น UTC
- provenance
- collection authorization

ข้อมูลจริง, direct identifiers และ credentials ไม่ commit เข้า Git ใช้ `data/private/` หรือ storage ส่วนตัว แล้วเก็บเพียง manifest + hash ใน repository

## Validation

ตรวจ manifest:

```bash
python3 scripts/validate_real_world_dataset.py path/to/manifest.json
```

ผล exit code:
- 0 = contract ผ่าน
- 1 = manifest มี contract violations
- 2 = อ่าน/parse file ไม่สำเร็จ

ตัว validator **ไม่ประกาศว่า dataset มีคุณภาพพอสำหรับ detection** มันตรวจเพียง identity, provenance, split isolation, metric compatibility และ label separation ซึ่งเป็นเงื่อนไขก่อนเริ่มการทดลอง

## สิ่งที่ยังไม่ทำใน Phase 1 นี้

- ไม่สร้าง ATT&CK attack plan
- ไม่ inject attack
- ไม่ดึง public security dataset มาใช้แทนข้อมูลจริงโดยอัตโนมัติ
- ไม่เปลี่ยน threshold/calibration
- ไม่แก้ Logic v8
- ไม่รายงาน accuracy/recall จาก fixture
- ไม่ถือ test fixture ว่าเป็น real telemetry

ขั้นถัดไปหลัง contract ผ่านคือเลือก/รับ telemetry จริงหรือ controlled telemetry และสร้าง manifest ที่มี hashes จริง จากนั้นจึงตรวจ data quality ก่อนเริ่มส่วนที่ 2
