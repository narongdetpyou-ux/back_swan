# ผลดำเนินการข้อ 9–11: ที่เก็บ โครงสร้าง และบันทึกการทดลอง

ฐานงาน: GitHub main `1b79204d674bac79a6481a09276f51f0c5610e13` (PR #2)

## สิ่งที่เปลี่ยน

กำหนด GitHub private `narongdetpyou-ux/back_swan` เป็นแหล่งโค้ดหลักโดยคง Python package `black_swan` แยก raw/processed/splits/manifests, run ชั่วคราว, baseline ที่ตรวจแล้ว, reports และ archive ตามหน้าที่ ไม่มีการย้ายไฟล์เก่าซ้ำหรือเปลี่ยนชื่อ repository และไม่แก้ detector/calibration/threshold

`scripts/experiment_record.py` เพิ่ม run ID UTC ความละเอียด microsecond + รหัสสุ่ม, จองโฟลเดอร์ใหม่, manifest เริ่ม/จบ, command, environment, Git identity เมื่อมีจริง, hashes และสถานะผิดพลาด ไม่บันทึกค่า environment หรือ exception message ทั้งชุด ไม่อ้างว่าการรันจบคือผ่านเกณฑ์ใช้งานจริง

เอกสารใช้งาน: `docs/DATA_STORAGE.md`, `docs/EXPERIMENTS.md`; mapping แบบ machine-readable: `configs/storage_policy.json`

## หลักฐานทดสอบ

| ตรวจ | ผล |
|---|---|
| tests v7/v8 เดิม | 33/33 ผ่าน |
| workflow tests ใหม่ | 13/13 ผ่าน |
| รวม regression | 46/46 ผ่านใน 7.588 s |
| quality เทียบผลเดิมรายแถว | เท่ากันทุกแถว 1,900/1,900 |
| injected faults | timeout 3, crash 1, exception 1; recovery alert กลับมาครบ |
| workers หลังปิด | 0 |
| source เปลี่ยนระหว่าง run | ไม่เปลี่ยน ทั้ง regression และ evaluation |
| evaluator functions เดิมยกเว้น main | AST เหมือนเดิม 7/7 |

Regression run: `20260904T154411280065Z_v8_regression_bd35c955`; evaluation run: `20260904T154412792811Z_v8_evaluation_046da720` แต่ละชุดมี manifest ต้นฉบับและ promotion manifest ซึ่งตรวจ hash ก่อนคัดลอก JSON ขนาดใหญ่บีบอัด gzip แบบ lossless; hash ใน manifest ต้นฉบับหมายถึงข้อมูลหลังคลาย gzip ส่วน `promotion.json` มี hash ไฟล์ที่เก็บจริง

Quality v8: benign false alert 1/600; strong attack alerts 600/600; evasive observable alerts 286/300; attack operational capture 998/1000 ทั้งหมดเป็น synthetic ไม่ใช่ผล production มีงาน regression รันร่วมช่วงต้นของ evaluator จึงไม่ใช้ latency รอบนี้กล่าวอ้างการเพิ่มประสิทธิภาพ

คำสั่ง: `PYTHONNOUSERSITE=1 python3 scripts/run_checks.py` และ `PYTHONNOUSERSITE=1 python3 benchmarks/evaluate_black_swan_v8.py --skip-load` ไม่มีการรัน load sweep ใหม่

## การสำรองและสิ่งที่ยังค้าง

Exporter สร้าง current-file ZIP พร้อม manifest SHA-256 ภายในและ checksum sidecar ภายนอก ตัวกู้คืนตรวจทุกไฟล์ก่อนเริ่มและปฏิเสธปลายทางที่มีอยู่แล้ว ไม่รวม Git history, credentials, private data หรือ run ชั่วคราว

Dropbox เชื่อมแล้วสำหรับงานนี้ แต่ยังต้องยืนยัน path ตามขั้นตอน `organize-dropbox-folder` ก่อนสร้าง `/back_swan/backups/<UTC>/` และคัดลอก ZIP/checksum ไม่มีการอัปโหลด ย้าย ลบ หรือสร้าง public link ณ บันทึกนี้ และยังไม่มี recurring backup ต้องสำรองผล v7 ฉบับเต็มภายนอกที่อ้างใน data manifest แยกด้วย

ข้อจำกัดเดิมยังอยู่: real-data/long-duration production validation ยังไม่ผ่าน และ credential ที่เคยอยู่ใน Git history ยังไม่มีหลักฐาน revoke/rotate
