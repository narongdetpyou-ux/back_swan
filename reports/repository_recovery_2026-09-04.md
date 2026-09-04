# ผลกู้ไฟล์และจัดระเบียบ Black Swan

วันที่: 4 กันยายน 2026

## ผลลัพธ์

นำ Logic v8 จาก ZIP เดิมมาเป็น package หลัก `black_swan` และจัด source, tests, benchmarks, configs, data, experiments, reports และ archive แยกกัน กู้เนื้อหาที่เคยเป็นไฟล์ว่างบน main และเก็บ source/ผลเดิมไว้ตรวจย้อนกลับ

PR #1 รวมเข้า main ที่ `287a269e79364343193bd2c1253883ef32622e89` แล้ว จึงไม่มีไฟล์ credential ใน current tree แต่ยังไม่ยืนยันว่า key ถูกเพิกถอน และไม่ได้ล้างประวัติ Git

## การตรวจที่ทำจริง

- ZIP v8 ตรงกับ Git blob ที่บันทึกไว้; source SHA-256 ทั้ง 4 ไฟล์ตรงกับผลประเมินเดิม
- ก่อนจัดโครงสร้าง tests v8 เดิมผ่าน 24/24
- หลังจัดโครงสร้าง tests v7 + v8 ผ่าน **33/33** ใน 7.585 วินาทีบนเครื่องครั้งนี้
- สร้าง ZIP พร้อม checksum และแตกลงโฟลเดอร์ว่าง; ตรวจ hashes ทุกไฟล์ และรัน tests ผ่าน **33/33** อีกครั้งใน 7.808 วินาที โดยปิด user site-packages เพื่อไม่พึ่ง package ที่ติดตั้งไว้
- ตรวจ AST: functions/classes ของ engine และ runtime ไม่เปลี่ยน; test classes v8 คงเดิมทุก assertion
- ติดตั้ง package แบบ offline สำเร็จ และ import จาก directory อื่นได้
- ประเมิน v8 ใหม่ด้วย `--skip-load`: ผลคุณภาพและข้อมูลรายกรณี **1,900 แถวตรงกับผลเดิมทั้งหมด**
- Fault injection ครบ 5 กรณี: stalls 3, crash 1, exception 1; คืน explicit REVIEW และกลับมาประมวลผล control ได้; หลัง close เหลือ worker 0
- ตรวจ current files/ZIP และ hashes ของไฟล์ที่กู้ ไม่มีไฟล์ว่างหรือรูปแบบ key ที่ตัวตรวจค้นพบ

การตรวจรอบแรกพบปัญหา import ตำแหน่ง `__future__` ของ test v7 หลังย้ายไฟล์ และไฟล์ชั่วคราวว่างจากขั้นกู้ข้อมูล ทั้งสองแก้ก่อนรอบทดสอบที่ผ่าน ไม่ได้เปลี่ยน threshold/labels/assertions เพื่อให้ผลผ่าน

## ผลการตัดสินใจที่ทำซ้ำได้

| ตัวชี้วัด | จำนวน |
|---|---:|
| Benign false alerts | 1/600 |
| Strong attack alerts | 600/600 |
| Observable evasive alerts | 286/300 |
| Attack operational capture รวม review | 998/1,000 |

ยังใช้ข้อมูลสังเคราะห์และ synthetic trust fixtures เดิม ไม่ใช่ข้อมูลจริงชุดใหม่ และไม่ได้รัน load sweep ใหม่ การจัดไฟล์ไม่ใช่การเพิ่มความสามารถตรวจจับของรุ่นโมเดล

## หลักฐานและคำสั่ง

- `experiments/20260904_repository_recovery_02/summary.json`: คำสั่ง tests, environment และ hashes
- `experiments/20260904_repository_recovery_02/regression.log`: รายละเอียด 33 tests
- `experiments/20260904_repository_recovery_02/evaluation_summary.json`: ผลประเมินใหม่และข้อจำกัด
- `experiments/20260904_repository_recovery_02/core_results.json.gz`: JSON ผลดิบครบถ้วน บีบอัดแบบไม่สูญเสียข้อมูล พร้อม hash ใน summary
- `data/manifests/recovered_files.json`: รายการต้นฉบับ/ปลายทางและ checksums

```bash
python3 scripts/run_checks.py
python3 benchmarks/evaluate_black_swan_v8.py --skip-load
python3 scripts/export_snapshot.py --output backups/black_swan_snapshot.zip
```

## งานที่ยังต้องทำ

ผู้ดูแลต้องยืนยันการ revoke/rotate key เดิม และเลือกที่เก็บสำรองส่วนตัวนอก GitHub สำหรับใช้งานต่อเนื่อง ยังไม่มี production data replay, external context authorization หรือ end-to-end load/soak test ของ service จริงในงานจัดโครงสร้างนี้
