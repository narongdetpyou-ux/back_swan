# รายงานตรวจสอบโค้ดด้วยข้อมูลฝึกฝน Black Swan v7

วันที่ตรวจสอบ: 2026-09-04 (UTC)

## ขอบเขตและวิธีทดสอบ

การตรวจสอบครั้งนี้ใช้ตัวสร้างข้อมูลสังเคราะห์ที่มากับโครงการ ไม่ใช่ข้อมูลเหตุการณ์จริง โดยแบ่งหน้าที่ของข้อมูลดังนี้

- ชุดปรับเทียบ (calibration/training) 900 สถานการณ์ benign ใช้เรียนรู้ตัวปรับสเกลของช่องสัญญาณและ threshold ที่ quantile 0.99
- ชุดประเมินแยกจากชุดปรับเทียบ ใช้ seed คนละช่วง จำนวน 200 รอบต่อ 19 scenario รวม 3,800 รอบต่อ engine
- เปรียบเทียบ `v7` กับ `v6_baseline` ด้วยคำสั่ง benchmark เริ่มต้นของโครงการ
- รัน unit test 9 รายการ และตรวจ syntax/bytecode ของไฟล์ Python หลัก

คำสั่ง benchmark ที่ใช้:

```bash
python black_swan_v7_benchmark.py \
  --output-dir /tmp/back_swan_training_check
```

## ผลการประเมิน

| ตัวชี้วัด | v6 baseline | v7 |
|---|---:|---:|
| benign false-alert rate | 7.8333% | **0.8333%** |
| strong-attack recall | 99.9167% | **100.0000%** |
| evasive-observable recall | 4.8333% | **94.0000%** |
| all-attack operational capture | 77.7000% | **99.7000%** |
| overall expected-route rate | 74.1053% | **94.5789%** |
| low-and-slow recall | 5.5000% | **98.5000%** |
| correlated-weak recall | 3.0000% | **84.0000%** |
| suppression-risk capture | 100.0000% | 100.0000% |
| lifecycle-route accuracy | 100.0000% | 100.0000% |

ค่าปรับเทียบของ v7 ที่ได้คือ composite threshold `1.3503934865225848` จาก calibration size 900 และ manifest SHA-256 คือ `1f866cd932ca2593005d549ef417d5c2bb705cecd9bb326dace1e0ae6e57a5a3`

## ผลตรวจโค้ด

### ผ่าน

1. Unit test ทั้ง 9 รายการผ่าน ครอบคลุมความทำซ้ำได้ของ calibration, low-and-slow, correlated signal, stale/approved context, telemetry suppression, lifecycle และ false-alert บน holdout
2. Benchmark ทำซ้ำได้ด้วย seed คงที่ และแยกช่วง seed ของ calibration ออกจาก evaluation
3. v7 มี false-alert 0.8333% บนข้อมูลสังเคราะห์ ซึ่งต่ำกว่าเป้าหมาย 1% ที่กำหนดใน calibration
4. ไฟล์ Python หลักผ่านการ compile เป็น bytecode

### ความเสี่ยงที่พบและแก้ไขแล้ว

- พบไฟล์ชื่อ `openai-api-key.txt` ถูกติดตามใน Git และมีรูปแบบคล้าย credential จึงนำไฟล์ออกจาก repository และเพิ่มกฎ `.gitignore` เพื่อป้องกันการ commit ซ้ำ
- ผู้ดูแลต้อง **เพิกถอน/หมุนเวียน (revoke/rotate) credential เดิมทันที** เพราะการลบจาก commit ล่าสุดไม่ลบ secret ออกจากประวัติ Git ก่อนหน้า

## ข้อจำกัด

- ผลทั้งหมดมาจาก aggregate telemetry สังเคราะห์ จึงยังสรุปประสิทธิภาพบนระบบ IDS/EDR จริงไม่ได้
- ตัวเปรียบเทียบ v6 เป็น implementation ของ gate ที่ตรึงไว้ใน repository ไม่ใช่ implementation ต้นฉบับที่แยกต่างหาก
- context event เป็นข้อมูลสังเคราะห์และไม่พิสูจน์ causal relationship ในโลกจริง
- ต้องปรับเทียบใหม่เมื่อ data distribution, metric set, sampling cadence หรือ production domain เปลี่ยน
- ควรเพิ่ม out-of-distribution, adversarial, missing-not-at-random และ production shadow evaluation ก่อนใช้งานตัดสินใจจริง

## สรุป

ภายใต้ชุดข้อมูลสังเคราะห์ที่กำหนด v7 ผ่าน unit test และให้ผลดีกว่า v6 baseline อย่างชัดเจน โดยเฉพาะ evasive attacks และ false alerts อย่างไรก็ตาม ผลนี้เป็น validation ภายใน generator เดียวกัน ไม่ควรตีความว่าเป็นหลักฐานพร้อมใช้งาน production จนกว่าจะผ่านข้อมูลจริงแบบ holdout และ shadow deployment
