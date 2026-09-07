# กติกาชื่อไฟล์และบันทึกการทดลอง

## ชื่อและตำแหน่ง

ชื่อ repository คือ `back_swan`; Python import คือ `black_swan` และรุ่นตรรกะปัจจุบันคือ `v8` ทั้งสามชื่อมีหน้าที่ต่างกัน ไม่ต้องเปลี่ยนชื่อ repo

- run ใหม่: `<UTC YYYYMMDDTHHMMSSffffffZ>_<version>_<purpose>_<random8>` เช่น `20260904T154100000000Z_v8_evaluation_a1b2c3d4` (ตัวอย่าง ไม่ใช่ผลรัน)
- purpose ใช้ภาษาอังกฤษตัวเล็ก ตัวเลข และขีดกลาง เช่น `evaluation`, `regression`, `realdata-holdout`
- เก็บผลใหม่ใน `experiments/local/<run_id>/` ซึ่งไม่เข้า Git โดยอัตโนมัติ ไม่แก้ชื่อหรือเขียนทับ run เก่า
- ใช้ `manifest.json` สำหรับหลักฐาน, `v8_results.json` หรือ `summary.json` สำหรับผล และ `<stage>.log` สำหรับ log; seed หลายช่วงอยู่ใน manifest ไม่ยัดทุก seed ในชื่อ
- ข้อมูลใหม่ตั้งชื่อ `<dataset>_<start>_<end>_<revision>.<ext>`; รายงาน `<run_id>_report_th.md`; ไม่ใช้ `final_final`, `latest2` เป็นหลักฐานอ้างอิง
- ตัวเลือก `--output` ยังใช้ได้ แต่โฟลเดอร์ run ต้องยังไม่มีอยู่ แม้เป็นโฟลเดอร์ว่างก็ไม่ใช้ซ้ำ

## คำสั่งที่สร้าง manifest อัตโนมัติ

```bash
python3 scripts/run_checks.py
python3 benchmarks/evaluate_black_swan_v8.py --skip-load
```

เมื่อระบุ output เอง:

```bash
python3 scripts/run_checks.py --output experiments/local/my-new-regression-run
python3 benchmarks/evaluate_black_swan_v8.py --skip-load --output experiments/local/my-new-evaluation-run/v8_results.json
```

ใช้โฟลเดอร์ใหม่ทุกครั้ง `--load-only` และ `--skip-load` ใช้พร้อมกันไม่ได้

## สิ่งที่บันทึกจริง

| ฟิลด์ | ความหมาย |
|---|---|
| `run_id`, `model_version`, `purpose` | ตัวตนและวัตถุประสงค์ของ run |
| `command`, `cwd`, เวลาเริ่ม/จบ UTC | วิธีเรียกและเวลารัน |
| `git.commit`, `git.dirty` | HEAD และสถานะ worktree เมื่อมี `.git`; snapshot ไม่มี Git ให้ `null` ไม่เดา SHA |
| `source_sha256` | SHA-256 ของ Python/JSON ใน src, tests, benchmarks, scripts และ configs ที่มีตอนเริ่ม |
| `environment` | Python, OS/platform, architecture, processor เมื่ออ่านได้ และ logical CPU count; ไม่รับรอง quota/hardware ทั้งเครื่อง |
| `metadata` | dataset/generator, seed/split, calibration snapshot, flags และสิ่งที่ไม่รัน |
| `details` | ผลตรวจของ workflow; ผล metric/denominator/fault แต่ละกรณีอยู่ใน result JSON |
| `artifacts` | ขนาดและ SHA-256 ของผล/log แต่ละไฟล์ ยกเว้น manifest เอง |
| `source_unchanged` | ตรวจว่า source/config ที่ติดตามไม่เปลี่ยนระหว่างรัน |

`running` หมายถึงกำลังรันหรือจบไม่สมบูรณ์; `completed` หมายถึง workflow จบเท่านั้น **ไม่ใช่โมเดลผ่านเกณฑ์ production**; `failed` หมายถึงคำสั่งตรวจล้มเหลว, exception หรือ source เปลี่ยน ข้อยกเว้นบันทึกชนิด ไม่บันทึกข้อความซึ่งอาจมีข้อมูลลับ เมื่อถูก SIGKILL/ไฟดับอาจคง `running`; ต้องตรวจและรันใหม่ ห้ามเปลี่ยนเป็นสำเร็จย้อนหลัง

ไม่ส่ง secrets ผ่าน CLI เพราะ command ถูกบันทึก; ใช้ secret store/environment และไม่บันทึกค่า environment ทั้งชุด เมื่อจะเผยแพร่ log ต้องตรวจข้อมูลส่วนตัวและความลับก่อนเสมอ

## ข้อมูล, labels และ holdout

การประเมิน v8 ปัจจุบันใช้ generator สังเคราะห์เดิม ไม่ใช่ dataset CSV ใน `data/raw/` จึงไม่อ้างว่า CSV เหล่านั้นถูกใช้ใน run นี้ แหล่ง generator และ calibration ถูก hash ใน manifest; quality seeds 1421000–1421099 และ novel seeds 1451000–1451099 อยู่ใน source และผลแถวจริง

สำหรับ run ที่ใช้ข้อมูลไฟล์ในอนาคต ต้องเพิ่ม path/URI, byte size, SHA-256, provenance/license และช่วงเวลาของ input จริงลง `metadata.inputs` ก่อนเริ่ม ใช้แยก `features`, `labels`, `predictions`; บันทึก split manifest ที่แยก calibration และ final holdout ตามเวลา/entity/seed ห้ามนำ prediction ไปเป็น ground truth โดยไม่มีขั้นตรวจสอบ และห้ามใช้ผล holdout ปรับ calibration แล้วอ้างว่าเป็น holdout เดิม

## เก็บ run เป็น baseline

1. รอ manifest จบ ตรวจ status, source_unchanged, ข้อผิดพลาดและ exclusions อ่าน metrics กับ denominators ไม่เลือกเฉพาะค่าที่ดี
2. ตรวจ checksum ผล/log และตรวจข้อมูลลับ; บันทึกเหตุผลเลือก baseline และเกณฑ์ตัดสินในรายงาน
3. คัดลอกชุดที่ผ่านการตรวจไป `experiments/<run_id>/` พร้อม manifest/result/log; ผลขนาดใหญ่เก็บที่ส่วนตัวภายนอกแล้วใช้ pointer manifest พร้อม hash ไม่เก็บสำเนาซ้ำหลายโฟลเดอร์
4. เพิ่มผ่าน GitHub review/commit; ไม่ force-add `experiments/local/` ทั้งโฟลเดอร์ ไม่ลบ run ที่ไม่ดีเพื่อทำให้ภาพรวมดูดีขึ้น

ผลเก่าที่ไม่มี manifest schema นี้คงชื่อเดิมและ provenance เดิมไว้ ไม่สร้าง metadata ย้อนหลังที่ไม่มีหลักฐาน ผลซ้ำมีค่า quality ที่เปรียบเทียบได้แต่เวลา/latency ไม่จำเป็นต้องเหมือนกัน
