# สถานะ Black Swan

อัปเดต: 4 กันยายน 2026 — งานกู้ไฟล์และจัดโครงสร้าง repository

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
