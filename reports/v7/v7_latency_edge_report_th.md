# Black Swan Logic v7 — ผลทดสอบ Latency, Throughput และ Edge Cases

วันที่วัด: 3 กันยายน 2026 (UTC) · Audit: `saved-v7-latency-edge-1`

## ข้อสรุปสำหรับตัดสินใจ

v7 ที่บันทึกไว้ใช้เวลาเฉลี่ย **1.660 ms ต่อ decision**, P95 **1.908 ms**, P99 **2.930 ms** บนชุดข้อมูลมาตรฐานที่ระบุด้านล่าง รวมการตรวจทานภายในแล้ว แต่ไม่รวมการรับข้อมูล สร้าง metrics รอคิว เครือข่าย หรือเขียนผลลงฐานข้อมูล

**ยังไม่ผ่านการพิสูจน์ว่ารองรับ 10,000–20,000 decisions/วินาที:** วัดได้ประมาณ 602 decisions/s แบบเรียกต่อเนื่องหนึ่ง worker และ 2,625 decisions/s เมื่อใช้ 8 processes ในเครื่องทดสอบนี้ ถ้าทุก raw event ต้องเรียก decision เต็มชุด อัตราหลักหมื่นต่อวินาทีสูงกว่าที่วัดได้และจะเกิดคิวสะสมหากไม่จำกัดโหลด

**การโจมตีที่ไม่เคยอยู่ใน benchmark ไม่ได้ทำให้ self-verification วนคิดโดยตัวมันเอง** เพราะโค้ดนี้เป็นกฎคำนวณทางสถิติและเลือกเส้นทาง ไม่ใช่ LLM หรือวงจร retry แต่ “ไม่ค้าง” ไม่ได้แปลว่า “ตรวจพบ”: พบทั้งสัญญาณอ่อนที่ไม่ส่งตรวจ ข้อมูลผิดรูปที่โยน exception และข้อมูลที่ทำให้ผลออกมาไม่แจ้งเตือนโดยไม่เกิด exception

สถานะที่เหมาะสม: **prototype สำหรับทดลอง ยังไม่ควรใช้เป็นด่านตัดสินใจด้านความปลอดภัยเพียงตัวเดียวใน production** รายงานนี้ไม่ได้แก้ engine เดิม

## 1. ขอบเขตและวิธีวัด

- ใช้ engine และ calibration ที่บันทึกไว้ ไม่ปรับ threshold ตามผลชุดทดสอบใหม่
- Engine SHA-256: `9f0d58ebad4f09f7be1be23e7b76520f904472f8e877391d8895c872cedbe663`
- ตรวจ hash ก่อนและหลังการทดลอง: ไม่เปลี่ยนแปลง
- CPU: Intel Xeon Platinum 8573C บน Linux VM/container; มองเห็น 9 logical CPUs แต่ CPU quota เทียบเท่า 8 cores; memory limit 14 GiB
- Python 3.12.13, GC เปิดตามปกติ, ไม่มี GPU/LLM/API ภายนอกในเส้นทาง decision
- 1 decision = 10 metrics × (168 ค่าประวัติ + 12 ค่าล่าสุด) = **1,800 ค่าตัวเลข/ช่องข้อมูล**
- ข้อมูลต้นแบบเป็น **hourly aggregate telemetry** ไม่ใช่ packet หรือ log record ดิบ หน้าต่างย้อนหลัง 168 ชั่วโมงและหน้าต่างล่าสุด 12 ชั่วโมง
- เตรียม input pool 84 ชุดก่อนจับเวลา: 7 families แบบน้ำหนักเท่ากัน × 12 seeds; ได้แก่ normal, approved backup, password spray, slow exfiltration, correlated weak signals, planned drift และ stale context
- Warm-up 200 decisions; วัด 3 รอบ × 1,500 = **4,500 calls** ด้วย `perf_counter_ns`; CPU time แยกด้วย `process_time_ns`
- เป็น microbenchmark ระยะสั้นบนเครื่องนี้ ไม่ใช่ SLA, live ingress load test หรือการทดสอบต่อเนื่องหลายชั่วโมง
- input pool ใช้ซ้ำและอยู่ใน memory; ไม่มีค่าใช้จ่ายของ parsing/การดึง baseline จริง การสลับ tenant จำนวนมาก หรือ cache misses แบบ production ครบถ้วน

การวัดนี้แยก compute latency ออกจาก **เวลาตั้งแต่เหตุการณ์เกิดจนตรวจพบ** ซึ่งยังขึ้นกับการรวบรวมและอัปเดต hourly windows การใช้หน้าต่าง 12 ชั่วโมงไม่ได้แปลว่าทุก decision ต้องรอ 12 ชั่วโมงใหม่ แต่ก็ไม่พิสูจน์การตรวจจับในระดับมิลลิวินาทีหลังเกิดเหตุ

## 2. ผล Speed & Latency

| การวัด | ผล |
|---|---:|
| Mean compute latency รวมตรวจทานภายใน | 1.660 ms |
| P50 | 1.596 ms |
| P95 | 1.908 ms |
| P99 | 2.930 ms |
| สูงสุดที่พบใน 4,500 calls | 5.860 ms |
| Throughput ของชุดหลัก | 602 decisions/s |
| Mean เมื่อรวม `as_record()` และ JSON serialization ใน memory | 1.700 ms |

P99 หมายถึงประมาณ 99% ของ calls ในการวัดชุดนี้ใช้เวลาไม่เกินค่านี้ ไม่ใช่เพดาน latency ใน production การทดสอบ serialize 1,000 calls เป็นคนละรอบ จึงไม่ควรเอาค่าเฉลี่ยสองรอบมาลบกันเป็นต้นทุน serialization ที่แน่นอน

### Self-verification เป็นคอขวดหรือไม่?

วัดแยกขั้นตอนอีก 500 calls ด้วย wrapper สำหรับจับเวลา แล้วคืนฟังก์ชันต้นฉบับทันที:

| ขั้นตอน | Mean ต่อ decision |
|---|---:|
| สร้าง features/seasonal profile/คะแนนสถิติ | 1.632 ms |
| ตรวจ context ครอบคลุมหลักฐาน 2 passes รวมกัน | 0.010 ms |
| ส่วนที่เหลือ: guards, policy, ledger, สร้างผล และ overhead ของ wrapper | 0.011 ms |
| รวมรอบ instrumented | 1.653 ms |

ประมาณ **98.7%** ของเวลาในรอบนี้อยู่ที่ feature extraction ไม่ใช่การตรวจ context อย่างไรก็ตาม 0.010 ms ไม่ใช่เวลาของ critic ทั้งหมด เพราะ guard/policy อยู่ในส่วนที่เหลือ และการตรวจ authenticity ของ context ภายนอกยังไม่มีใน engine นี้

### เมื่อขนาด input โตขึ้น

| Metrics | History/metric | Recent/metric | จำนวนค่ารวม | จำนวน calls | Mean |
|---:|---:|---:|---:|---:|---:|
| 10 | 168 | 12 | 1,800 | 100 | 1.611 ms |
| 100 | 168 | 12 | 18,000 | 50 | 15.566 ms |
| 1,000 | 168 | 12 | 180,000 | 12 | 150.193 ms |
| 10 | 1,680 | 12 | 16,920 | 40 | 17.537 ms |
| 10 | 16,800 | 12 | 168,120 | 12 | 179.877 ms |

แถว scaling ใช้ streams ที่ทำสำเนาเพื่อวัดต้นทุนคำนวณเท่านั้น ไม่ใช่ข้อมูล 1,000 metrics ที่เป็นอิสระ และไม่ใช่การพิสูจน์ accuracy หลังเปลี่ยน shape โดยไม่ได้ recalibrate โค้ดคำนวณ seasonal profile และ residuals จากประวัติใหม่ทุก decision; ยังไม่มี baseline cache หรือ incremental update

## 3. ถ้ามีข้อมูลหลักหมื่นรายการต่อวินาที จะทันหรือไม่?

### Throughput ที่วัดจริงเมื่อเพิ่ม workers

| รูปแบบ | Calls รวม | Throughput |
|---|---:|---:|
| 1 process | 1,200 | 606 decisions/s |
| 2 processes | 2,400 | 1,168 decisions/s |
| 4 processes | 4,800 | 1,913 decisions/s |
| 8 processes | 9,600 | 2,625 decisions/s |
| 4 threads ใน process เดียว | 2,400 | 588 decisions/s |

แต่ละ process เตรียม input และ warm-up ก่อนเริ่ม barrier จับเวลา ไม่มี IPC ต่อ decision ไม่มี queue/service I/O การเพิ่ม processes ไม่ได้เพิ่ม throughput แบบเส้นตรงในการทดลองนี้ ส่วน 4 threads ไม่ได้ช่วยใน workload ที่วัด ตัวเลข process แต่ละขนาดเป็นหนึ่งรอบสั้น จึงยังใช้รับประกันกำลังรองรับแบบยั่งยืนไม่ได้

**กรณี A: 10,000 raw events/s ถูกแปลงเป็น 100 decisions/s** เช่น ประมวลผล snapshot ของ 100 entities ทุกวินาที — compute budget ที่วัดชี้ว่ามีโอกาสรองรับ แต่ยังต้องวัด ingest, aggregation และ service จริง และต้องออกแบบ/สอบเทียบให้เหมาะกับเวลาอัปเดตที่เปลี่ยนไป ตัว engine ปัจจุบันไม่มีระบบรับ raw events หรือแปลงข้อมูลนี้ให้

**กรณี B: 10,000 raw events/s = 10,000 full decisions/s** — **ไม่ทันในการตั้งค่าที่ทดสอบ** แม้ 8 processes ยังทำได้ประมาณ 26.2% ของอัตราที่ต้องการ

ตัวอย่างกรณี A เป็นเพียงการอธิบายความต่างระหว่าง event กับ decision ไม่ใช่ configuration ที่ได้ deploy หรือ benchmark จริง จำนวน decisions/s ขึ้นกับจำนวน entities, update cadence และกลไก trigger ไม่ใช่จำนวน raw events อย่างเดียว

### จำลองคิวจากเวลาที่วัดได้

สมมติหนึ่ง worker, FIFO ไม่จำกัด, arrivals สม่ำเสมอเป็นเวลา 1 วินาที แล้วหยุดส่ง; replay service times จากรอบ latency โดยไม่เพิ่มต้นทุน network/queue:

| อัตราเข้า | ทำเสร็จภายใน 1 วินาที | ยังไม่เสร็จ ณ 1 วินาที | เวลารอคิวของรายการสุดท้าย |
|---:|---:|---:|---:|
| 100 decisions/s | 100 | 0 | 0 ms |
| 500 decisions/s | 499 | 1 | 1.710 ms |
| 1,000 decisions/s | 604 | 396 | 659 ms |
| 10,000 decisions/s | 604 | 9,396 | 15.60 s |
| 20,000 decisions/s | 604 | 19,396 | 32.20 s |

นี่คือ **queue simulation ไม่ใช่ live stress test ที่ยิง network 10,000/s** ผลแสดงว่าถ้าอัตราเข้ามากกว่ากำลังบริการอย่างต่อเนื่อง คิวจะโตขึ้นเรื่อย ๆ engine ปัจจุบันไม่ได้กำหนด backpressure, queue cap, overload policy หรือ timeout ให้

การคำนวณแบบอุดมคติจาก mean 1.660 ms จะได้ประมาณ 24 workers สำหรับ 10,000 decisions/s ที่ utilization 70% และ 48 workers สำหรับ 20,000 decisions/s แต่เป็นเพียง arithmetic extrapolation **ไม่ใช่คำแนะนำจำนวนเครื่องที่ยืนยันแล้ว** โดยเฉพาะเมื่อผล 8-process scale ไม่เป็นเส้นตรง

## 4. Edge cases: รูปแบบสัญญาณใหม่ที่ไม่อยู่ใน benchmark เดิม

สร้าง pattern ใหม่จาก normal generator โดยไม่เพิ่ม pattern เหล่านี้เข้า calibration; ใช้ 100 seeds ต่อแบบ รวม 500 calls เกณฑ์และ threshold คงเดิม ผลด้านล่างเป็นการตอบสนองต่อสัญญาณสังเคราะห์ ไม่ใช่อัตราตรวจจับ zero-day จริง

| Pattern ใหม่ | Security alert | ส่งตรวจต่อรวม alert | ไม่ alert และไม่ส่งตรวจ | Exception |
|---|---:|---:|---:|---:|
| outbound และ successful logins ลดลง 80% พร้อมกัน | 100/100 | 100/100 | 0/100 | 0 |
| outbound ×1.8 ทุก 3 จุด สลับช่วงปกติ | 100/100 | 100/100 | 0/100 | 0 |
| สัญญาณเพิ่ม 25% สลับ 4 metrics ทีละจุด | 43/100 | 77/100 | 23/100 | 0 |
| outbound เพิ่มเพียง 2% ต่อเนื่อง | 1/100 | 3/100 | 97/100 | 0 |
| สมมติการโจมตีไม่มีร่องรอยใน metrics ที่ส่งเข้า | 1/100 | 2/100 | 98/100 | 0 |

“ส่งตรวจต่อรวม alert” นับ `operational_escalation=True` ซึ่งรวม security alerts; ไม่ใช่คอลัมน์ที่จะนำไปบวกกับ alert อีกครั้ง และยังไม่มีการส่งให้ผู้ตรวจจริงใน harness

กรณีไม่มีร่องรอยใช้ input เหมือน normal control ทุกค่า จึงได้ผลตรงกับ control **100/100 คู่** หนึ่ง alert ที่เกิดขึ้นเป็น alert บน normal telemetry คู่เดียวกันด้วย ไม่ใช่หลักฐานว่าตรวจพบการโจมตีที่ไม่มีสัญญาณ

ทุก call ในชุด valid patterns จบการทำงาน ไม่มี exception และไม่พบการค้างระหว่างรัน แต่ยังไม่มี fuzz/soak test ที่พิสูจน์ว่า input valid ทุกชนิดมีเวลา/หน่วยความจำจำกัด

### Self-verification ทำอย่างไรเมื่อเจอสิ่งใหม่?

โค้ดไม่ได้รู้ว่า pattern ใด “ไม่เคยเห็น” และไม่มี unknown-attack class โดยเฉพาะ:

1. คำนวณ point, temporal และ collective evidence จาก metrics ที่ได้รับ
2. เลือก route ตาม lifecycle, quality, history, score และ context
3. ถ้าสูงพอจะ alert; ถ้าอยู่ review band จะส่งตรวจ; ถ้าต่ำอาจเป็น `NO_SECURITY_ALERT` แม้ผู้ทดสอบจะทราบว่าเป็นการโจมตี

ค่า `uncertainty` เป็นสูตรระยะห่างจาก threshold ไม่ใช่ความน่าจะเป็นที่สอบเทียบแล้ว และไม่ใช่ตัวตรวจ out-of-distribution ไม่ควรตีความว่า uncertainty=0 แปลว่าปลอดภัยหรือรู้จักรูปแบบนั้นแน่นอน

## 5. ข้อมูลผิดรูปและจุดที่เงียบโดยไม่ล้ม

ทดสอบ 27 กรณีแยก subprocess: 18 คืนผล, **9 โยน engine exception**, ไม่มีกรณี timeout 5 วินาที ข้อจำกัด 512 MiB, CPU 3 วินาที และการจับ exception เป็นของ **test harness เท่านั้น** ไม่ได้มีใน engine เดิม ชุด 27 กรณีรวม control และ config corruption ด้วย ไม่ใช่ 27 การโจมตี

| กรณีสำคัญ | ผลจริง | ความหมาย |
|---|---|---|
| string ที่ไม่ใช่ตัวเลข / dict ใน numeric field | `ValueError` / `TypeError` | engine ไม่คืน Decision |
| ความยาว status ไม่ตรงกับข้อมูล | `ValueError` | ไม่ได้แปลงเป็น safe hold |
| lifecycle มีค่า แต่ numeric เสีย | `ValueError` ก่อน lifecycle route | guard ไม่ได้ป้องกันการ parse ผิด |
| metric หนึ่ง quality failed แต่ history อีก metric เสีย | `ValueError` | quality route ไม่กัน exception นี้ |
| integer ใหญ่เกิน float | `OverflowError` | request ล้มได้ |
| calibration divisor = 0 | `ZeroDivisionError` | config ไม่ถูก validate |
| confidence เป็น string / context เป็น dict ผิด interface | `TypeError` / `AttributeError` | context ผิดชนิดล้มได้ |
| input ว่าง / recent ว่าง / recent เป็น None แต่ marked complete | `NO_SECURITY_ALERT`, ไม่ส่งตรวจ, uncertainty=0 | ไม่ใช่หลักฐานว่าระบบปกติ; ข้อมูลไม่พอแต่ไม่ HOLD |
| recent เป็น NaN ทั้งหมด | `NO_SECURITY_ALERT`, score=NaN; strict JSON ล้ม | มีทั้งการไม่แจ้งเตือนและปัญหาส่งผลออก |
| recent เป็น Infinity หรือค่าจำกัด 1e308 ที่คำนวณ overflow | alert แต่ score=Infinity; strict JSON ล้ม | คืน Decision ได้แต่ downstream serialization อาจล้ม |
| recent แต่ละ metric ยาวไม่เท่ากัน / metric หายจาก recent | ไม่ reject; control ออก no alert | window alignment/การหายไปยังไม่ตรวจครบ |
| status ไม่รู้จัก | `TELEMETRY_HOLD`, ส่งตรวจ | กรณีนี้หยุดใช้ข้อมูลเพื่อ route ต่อได้ |
| caller ระบุ status suppressed | `TELEMETRY_HOLD_SECURITY_RISK`, ส่งตรวจ | engine ใช้สถานะที่ caller ส่ง ไม่ได้สืบหาการ suppress เอง |

การทดสอบซ้ำโดย **ไม่จับ exception** สำหรับ numeric string ทำให้ process จบด้วย **exit code 1** ยืนยันว่ามีเส้นทางให้โปรแกรมที่เรียกตรง ๆ ล้มได้ ส่วนจะล้มเฉพาะ request, worker หรือทั้ง production service ขึ้นกับ error isolation ของระบบห่อหุ้ม ซึ่งยังไม่มีให้ทดสอบ

### Self-verification มีช่องโหว่เชิงตรรกะที่ไม่ก่อ exception

ใช้ exfiltration control เดียวกันทุกค่า ซึ่งได้ composite score 24.671 เทียบ threshold 1.350:

| เปลี่ยนเฉพาะ metadata ของ control | Final route | Alert | ส่งตรวจ |
|---|---|---|---|
| ไม่เพิ่ม metadata | `SECURITY_ANOMALY_REVIEW` | ใช่ | ใช่ |
| เพิ่ม context อ้าง approved/active, confidence .99, ครอบคลุม metrics แต่ `evidence_ref` ว่าง | `BENIGN_EXPLAINED_BREAK` | ไม่ | ไม่ |
| เพิ่ม lifecycle ให้ชื่อ metric ที่ไม่มีใน input และไม่เกี่ยวข้อง | `SERIES_LIFECYCLE_CHANGE` | ไม่ | ไม่ |
| endpoint metric ไม่เกี่ยวข้องมี status failed | `TELEMETRY_HOLD` | ไม่ | ใช่ |
| เพิ่ม metric ใหม่มี history 4 จุด | `INSUFFICIENT_HISTORY_HOLD` | ไม่ | ใช่ |

กรณี context เป็นการทดสอบสมมติว่า caller สามารถส่ง metadata ที่ไม่ถูกต้องได้ ไม่ได้พิสูจน์ว่าผู้โจมตีภายนอกเข้าถึง interface นี้ได้ อย่างไรก็ตาม engine **ไม่ได้ตรวจ `evidence_ref` หรือยืนยันผู้อนุมัติ/แหล่งที่มา** จึงต้องมี trusted boundary ภายนอก การใช้ชื่อ rule ว่า `context_scope_and_provenance` ไม่ได้แปลว่ามี provenance verification จริง

ในทำนองเดียวกัน lifecycle ใด ๆ มี precedence ต่อทั้ง decision จึงกลบหลักฐานโจมตีของ metrics อื่นได้ การ HOLD เมื่อ metric บางตัวเสียยังส่ง operational escalation แต่เสีย security classification ของหลักฐานที่ยังใช้งานได้

## 6. ข้อสรุปที่ต้องแก้จากคำอธิบาย v7 ก่อนหน้า

- ใน source จริง `decide()` เรียก `extract_features()` **ก่อน** lifecycle/quality guards ดังนั้นข้อความว่า “ตรวจ lifecycle/quality ก่อน numerical scoring” ไม่ตรงกับลำดับ execution แม้ชื่อ ledger/comment จะเขียนเช่นนั้น
- Critic ตรวจ context scope และ flags/confidence ที่รับมา แต่ไม่ได้ยืนยัน provenance จริง
- Unit tests เดิมผ่าน 9/9 ในการตรวจครั้งนี้ แต่ไม่ได้ครอบคลุม malformed inputs, NaN, empty input หรือ metadata override ที่พบ จึงไม่ใช่หลักฐานว่าพร้อม production
- การตรวจทานไม่ใช่ independent security oracle, ไม่ได้เรียนรู้ zero-day อัตโนมัติ และไม่สามารถสร้างข้อมูลที่ sensors ไม่ได้วัด

## 7. ลำดับงานสำหรับรุ่นถัดไป — ยังไม่ได้ลงมือแก้ engine

| ลำดับ | งาน | เกณฑ์ยอมรับที่เสนอ |
|---|---|---|
| P0 | ตรวจ schema, finite numbers, nonempty input, status/metric alignment และ calibration ก่อนคำนวณ | malformed inputs คืน explicit invalid/hold route; ไม่ปล่อย NaN/Inf ออก; ไม่มี uncaught request exception ในชุด regression |
| P0 | แยก lifecycle/quality ต่อ metric และรักษาหลักฐานโจมตีจาก metric ที่ยัง valid | unrelated lifecycle/failed metric ไม่เปลี่ยน strong attack เป็น benign/no-action |
| P0 | กำหนด trust boundary และตรวจ context กับแหล่งอนุมัติจริง | context ที่ยืนยันไม่ได้ห้าม suppress alert; scope/เวลา/หลักฐานตรงกับข้อมูล |
| P0 | ใส่ exception isolation, input-size limit, deadline และ bounded queue พร้อม overload policy | malformed/oversized request ไม่พา service ล้ม; overload มีผลลัพธ์ชัดและตรวจสอบได้ |
| P1 | cache seasonal baseline/scale, incremental features และจัดสรร state ต่อ entity | ผลเทียบเท่า reference ภายใต้ tolerance ก่อนวัดความเร็วใหม่ |
| P1 | กำหนด raw-event aggregation และ decision cadence | ระบุ raw events/s, entities, decisions/s, freshness และ latency budget แยกกัน |
| P1 | ทดสอบ service จริงตามอัตราเป้าหมายและ burst พร้อม durable output | วัด end-to-end P95/P99, backlog, loss, recovery และ soak; ห้ามใช้ microbenchmark แทน |
| P2 | ขยาย sensor coverage, novel-pattern tests และแนวทาง abstention/OOD | วัด missed alerts และ silent no-action แยกจาก crash; ไม่ใช้ uncertainty สูตรเดิมเป็นความมั่นใจที่รับรองแล้ว |

ยังไม่กำหนดตัวเลข SLA หรือจำนวนเครื่องแบบรับรอง เพราะไม่มี production payload, decision cadence, hardware target และผล load test ของ service จริง

## 8. ทำซ้ำและตรวจสอบหลักฐาน

ในชุดแนบมี:

- `black_swan_v7_latency_edge_audit.py` — harness ที่ไม่แก้ engine
- `v7_latency_edge_results.json` — raw latencies, seeds, routes, exceptions, environment และ hashes; ค่า nonfinite ถูกเก็บเป็น string ในรายงาน JSON เพื่อให้ไฟล์อ่านได้ตามมาตรฐาน
- `v7_latency_edge_report_th.md` — รายงานนี้
- `sources/black_swan_v7_engine.py`, `sources/black_swan_v7_benchmark.py`, `sources/black_swan_v7_manifest.json`, `sources/test_black_swan_v7.py` — สำเนาต้นฉบับสำหรับทำซ้ำ

หลังแตก bundle ใช้ Python 3.12 บน Linux และรันจากโฟลเดอร์ชุดทดสอบ:

```bash
python3 black_swan_v7_latency_edge_audit.py --output rerun_results.json
python3 -m unittest discover -s sources -p test_black_swan_v7.py -v
```

คำสั่งแรกล็อก source hashes และ fixed calibration แต่เวลาอาจเปลี่ยนตามเครื่อง/โหลด ผล route สำหรับ seeds เดิมควรทำซ้ำได้ ไม่มีการติดตั้ง dependency ภายนอก ส่วน unit tests เดิมมี calibration ของตัวเอง ไม่ใช่การปรับ calibration ของ performance audit
