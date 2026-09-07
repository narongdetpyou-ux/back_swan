# สถานะ Black Swan

อัปเดต: 4 กันยายน 2026 — จัดที่เก็บไฟล์และมาตรฐานการทดลอง (ข้อ 9–11)

## งานจัดเก็บและบันทึก run ล่าสุด

- คง private repository `back_swan` และ package `black_swan`; mapping อยู่ใน README และ `configs/storage_policy.json`
- เพิ่ม manifest ต่อ run, ชื่อ UTC ที่ไม่ซ้ำ, การไม่เขียนทับผลเดิม, source/result hashes และบันทึกสถานะเมื่อ exception/timeout
- tests รวมผ่าน 46/46 (โมเดลเดิม 33 + workflow ใหม่ 13) ใน 7.588 วินาที: `experiments/20260904T154411280065Z_v8_regression_bd35c955/`
- ประเมิน v8 ซ้ำด้วย `--skip-load`: quality 1,900 แถวตรงผลเดิมทั้งหมด; fault recovery 5/5; workers หลังปิด = 0 ผลอยู่ใน `experiments/20260904T154412792811Z_v8_evaluation_046da720/` โดยบีบอัด JSON แบบ lossless และเก็บ hash ต้นฉบับ/ไฟล์บีบอัดใน `promotion.json`
- Source engine/runtime ไม่เปลี่ยน; evaluator เปลี่ยนเฉพาะ CLI และ metadata ไม่เปลี่ยนฟังก์ชันประเมินเชิงตัวเลข 7 ฟังก์ชัน
- Export สร้าง ZIP และ `.sha256`; ตัวตรวจใหม่ตรวจ transport/member hashes และกู้ไปโฟลเดอร์ใหม่โดยไม่เขียนทับ
- Dropbox เชื่อมแล้ว; รอยืนยันปลายทางและการคัดลอก ยังไม่อ้างว่า backup ภายนอกสำเร็จหรือมี recurring backup

รายละเอียด: `docs/DATA_STORAGE.md`, `docs/EXPERIMENTS.md`

## รุ่นหลักและหลักฐาน

- รุ่นหลักคือ **Logic v8** ใน `src/black_swan/`; reference math v7 อยู่ใน `src/black_swan_v7_engine.py`
- กู้จาก `archive/releases/black_swan_v8_verified_bundle.zip`; source hashes เดิม 4/4 ตรงกับผล `v8-evaluation-1`
- การจัด package เปลี่ยน import/path และการบันทึกผลเท่านั้น ไม่เปลี่ยนกฎตัดสินใจ threshold labels หรือ assertions ของ tests
- Baseline GitHub ก่อนจัดโครงสร้าง: `287a269e79364343193bd2c1253883ef32622e89` ซึ่งรวม PR #1 แล้ว
- ผลเดิม: `experiments/20260904T033307Z_v8_original/results.json`
- หลักฐานการกู้: `data/manifests/recovered_files.json`
- ผลทดสอบหลังจัดโครงสร้าง: บันทึกใน `experiments/20260904_repository_recovery_02/` — tests 33/33 ผ่าน; ประเมินใหม่ 1,900 กรณีตรงผลเดิมทุกแถว
- ทดสอบกู้ snapshot ไปโฟลเดอร์ว่างแล้ว: checksums ตรงทุกไฟล์ และ tests ผ่าน 33/33 โดยไม่พึ่ง user site-packages

## ไฟล์ที่กู้และจัดเก็บ

กู้เนื้อหารายงาน v6/v7, audit v7, stress-test script/CSV และ v8 validation report ที่เคยเป็นไฟล์ว่างบน main; เขียนสถานะโครงการนี้ใหม่จากหลักฐานจริง ย้าย source/tests/benchmarks/config/data/results/reports ออกจาก root และเก็บ ZIP เดิมไว้ตรวจย้อนกลับ

## ขอบเขตที่ยังไม่ผ่าน

- Prototype นี้ยังไม่ deploy เป็น production service
- ยังไม่มีผล real cybersecurity traffic replay ที่เหมาะกับ metric contract และ labels อิสระ
- ผล 10,000–20,000 full decisions/s ยังไม่ผ่าน; ไม่ใช้การจัดไฟล์ครั้งนี้กล่าวอ้างว่าประสิทธิภาพเพิ่มขึ้น
- Trust registry ใช้ fixture สังเคราะห์ในการประเมิน; ยังต้องเชื่อม verified change records และ authorization จริง
- ไม่มีหลักฐานยืนยันว่า credential เดิมถูก revoke/rotate; การลบไฟล์ปัจจุบันไม่ลบประวัติ Git
- มีเครื่องมือ export/verify snapshot; ยังไม่ได้เชื่อมที่เก็บสำรองอัตโนมัตินอก GitHub

## งานถัดไป

1. ผู้ดูแลตรวจและเพิกถอน credential เดิมถ้ายังมีผลใช้งาน
2. ระบุ dataset จริงที่มี signals ตรงกับ hourly windows และ labels; แยก calibration/test ตามเวลา
3. ระบุ raw events/s, entity count, decision cadence และ hardware ก่อนทดสอบโหลดระบบครบเส้นทาง
4. ลดภาระ review ใน benign concept drift และเพิ่ม coverage ของสัญญาณอ่อน โดยรักษา holdout ที่ไม่ใช้ปรับแต่ง

รายละเอียด contract: `docs/CONTRACT.md`; วิธีจัดเก็บ/สำรอง: `docs/DATA_STORAGE.md`
