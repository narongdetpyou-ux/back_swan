# การเก็บไฟล์และกู้คืน Black Swan

แหล่งอ้างอิงโค้ดหลักคือ private GitHub repository `narongdetpyou-ux/back_swan` ข้อมูลดิบและรายงานต้องมีแหล่งที่มา ชื่อ run และ checksum ที่ตรวจย้อนกลับได้

| สิ่งที่เก็บ | ตำแหน่ง |
|---|---|
| Engine/runtime รุ่นหลัก | `src/black_swan/` |
| v7 reference math | `src/black_swan_v7_engine.py` |
| Tests และ fixtures เล็ก | `tests/` |
| ตัวสร้างข้อมูล/benchmark | `benchmarks/` |
| Calibration เดิม | `configs/` |
| ข้อมูลต้นฉบับที่กู้จาก bundle | `data/raw/medicare/`, `data/raw/cybersecurity/` |
| ข้อมูลที่แปลงแล้ว | `data/processed/` พร้อม script/hash ของต้นทาง |
| การแบ่งชุดข้อมูล | `data/splits/` |
| ผลรันที่เก็บเป็น baseline | `experiments/<run_id>/` |
| ผลทดลองใหม่ชั่วคราว | `experiments/local/<run_id>/` ซึ่ง Git ignore |
| ผลสรุปสำหรับอ่าน | `reports/` |
| ZIP รุ่นเดิม | `archive/releases/` |
| Private telemetry/credentials | เก็บนอก Git; `data/private/` ถูก ignore; ใช้ environment/secret store สำหรับ credentials |

## ข้อมูลที่มีอยู่จริง

- Medicare CSV จาก v6 bundle เดิมเป็นชุด aggregate ที่เคยใช้ประเมิน 13 codes ช่วง 2013–2024 การจัดไฟล์ครั้งนี้ไม่ได้ดึง CMS ใหม่หรือยืนยัน coverage/payment rules ใหม่
- Cybersecurity CSV ที่กู้ได้เป็น **synthetic**; generator ของ v7 อยู่ใน benchmark การมีข้อมูลทดสอบไม่ใช่หลักฐานว่าเป็น production replay
- `data/manifests/recovered_files.json` บันทึกต้นฉบับ → ปลายทาง ขนาดและ SHA-256 ของไฟล์ที่คัดลอกโดยไม่แก้ bytes
- v7 run results ฉบับเต็ม 7.67 MB มีอยู่ในไฟล์ส่วนตัวจากงานเดิม ตำแหน่งและ hash อยู่ใน `data/manifests/v7_full_results_external.json` จึงไม่ทำสำเนาเพิ่มใน Git; สร้างใหม่ได้ด้วยคำสั่งที่บันทึก

## กติกาแต่ละ run

ใช้ชื่อ UTC + รุ่น + วัตถุประสงค์/seed ไม่เขียนทับผลเดิม เก็บ command, Python/platform/hardware, calibration, seed/split, source SHA-256, counts, failures และ exclusions ควบคู่ผล

แยก raw data, transformed features, ground-truth labels และ predictions อย่ารวม prediction เป็น label โดยไม่ระบุขั้นตรวจสอบ เก็บ calibration และ final holdout คนละ seed/time range

## สำรองและกู้คืน

`python3 scripts/export_snapshot.py --output backups/black_swan_snapshot.zip` ตรวจ current files แล้วส่งออก ZIP พร้อม `SNAPSHOT_CHECKSUMS.json`; ไม่รวม Git history, credentials, private data, local experiments หรือ backups เดิม

ย้าย ZIP ไปพื้นที่ส่วนตัวอีกแห่งหนึ่งที่คุณควบคุม และเก็บข้อมูลภายนอกที่อ้างใน manifest ด้วย การมี ZIP ใน GitHub เดียวกันไม่ใช่สำเนานอกระบบ ไม่ได้ตั้ง recurring backup หรือปลายทาง cloud ใหม่ในงานนี้

หลังแตก snapshot ให้รัน `python3 scripts/run_checks.py` จาก clean directory และเทียบ checksums การสำรองประวัติ Git หรือ LFS ในอนาคตต้องวางแผนแยก โดยคำนึงถึง credential ที่เคยอยู่ใน history

เมื่อข้อมูลโต ใช้ private data/object storage หรือ Git LFS ตามความจำเป็น เก็บ manifests/config/summaries ใน Git; [GitHub แนะนำเรื่องไฟล์ใหญ่](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
