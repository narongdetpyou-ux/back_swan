# Black Swan Logic v8

รุ่นพัฒนาต่อจาก source v7 จริง สำหรับตรวจ anomaly บน metric windows พร้อมการตรวจทานแบบ deterministic ไม่ใช่โมเดล LLM ที่ฝึกใหม่ ไม่ใช่ระบบตรวจจับ zero-day ที่รับรองแล้ว และยังไม่ได้ deploy

## สิ่งที่เปลี่ยน

- ตรวจชนิดข้อมูล, NaN/Infinity, ขนาดข้อมูล, calibration, status alignment และช่องว่าง history ก่อนคำนวณ
- ข้อมูลไม่ครบ/ตรวจไม่ได้เป็น explicit REVIEW พร้อม `reason_code`; ไม่ใช้ no-alert แทนข้อมูลที่ขาด
- lifecycle/quality แยกต่อ metric; หลักฐานโจมตีจาก metric ที่ยัง valid ไม่ถูก metadata ของ metric อื่นกลบ
- context suppress alert ได้เฉพาะเมื่ออยู่ใน registry ที่ผู้ดูแลติดตั้งไว้ และ scope/confidence/ช่วงเวลาตรงกัน
- เก็บ seasonal profile และ scale ใน cache แบบ bounded โดยใช้ค่าประวัติทั้งหมดเป็น key; history เปลี่ยนแล้วไม่ใช้ผลเก่า
- มีโหมด immutable registered baseline สำหรับส่งเฉพาะ recent window; เปลี่ยน revision แล้ว token เก่าถูกเพิกถอน
- runtime ใช้ process และ pipe แยกต่อ worker, bounded queue, watchdog, timeout/cancel ที่ kill งานค้างได้จริง และ restart worker
- ตรวจ transport shape/type ก่อน serialization; ไม่ pickle arbitrary nested objects จาก caller

## โครงสร้างชุดส่งมอบ

```text
black_swan_v8/
  black_swan_v8_engine.py
  black_swan_v8_runtime.py
  test_black_swan_v8.py
  evaluate_black_swan_v8.py
  v8_evaluation_results.json
  v8_validation_report_th.md
  PROJECT_STATUS.md
  README.md
black_swan_v7/                 # reference engine/benchmark/tests, unchanged
v7_latency_audit/              # original reproducible audit support
```

Python 3.12 บน Linux; ใช้ standard library ไม่ต้องติดตั้ง dependency เพิ่ม โครงสร้างโฟลเดอร์ข้างต้นต้องคงไว้เพราะ imports ใช้ reference v7 และ audit fixtures เดิม

## รัน tests และประเมินใหม่

รันจากโฟลเดอร์หลักหลังแตกไฟล์:

```bash
python3 -m unittest discover -s black_swan_v8 -p test_black_swan_v8.py -v
python3 -m unittest discover -s black_swan_v7 -p test_black_swan_v7.py -v
python3 black_swan_v8/evaluate_black_swan_v8.py --output black_swan_v8/rerun_results.json
```

การประเมินครบใช้เวลาหลายนาทีตามเครื่อง; แต่ละ load case เป็นจำนวน requests จำกัด การตั้งเป้า 3 วินาทีอาจใช้เวลาส่งนานกว่านั้นถ้าตัวสร้างโหลดหรือ front door ไม่ทัน ดู `achieved_offer_rate_per_s` และ `emitter_lag` ทุกครั้ง ห้ามนับจำนวนที่ตั้งใจจะส่งเป็นโหลดที่เกิดขึ้นจริง

หากต้องการเฉพาะ correctness/latency หรือเฉพาะ load:

```bash
python3 black_swan_v8/evaluate_black_swan_v8.py --skip-load --output black_swan_v8/rerun_core.json
python3 black_swan_v8/evaluate_black_swan_v8.py --load-only --output black_swan_v8/rerun_load.json
```

## Contract การใช้งาน

### Full input

สร้าง `ScenarioInput` จาก reference module และส่งเข้า `BlackSwanV8(calibration).decide(input)` ได้เหมือนเดิม ใช้ built-in dict/list และ int/float/None เท่านั้น Numeric strings และ bool ไม่ถูกแปลงเป็นค่าตัวเลขโดยปริยาย

`decide()` ป้องกัน exception ที่เกิดจากการคำนวณปกติและคืน fallback แต่ **ไม่มี hard wall-clock deadline ใน process เดียว** ใช้ `IsolatedDecisionPool` เมื่อต้องการ watchdog/cancellation

### Registered baseline

`model.register_baseline(name, complete_scenario)` เป็นงานของผู้ดูแล/ขั้นเตรียมข้อมูล คืน content-addressed `baseline_id` จากนั้นส่ง `WindowUpdate(baseline_id, scenario_id, recent, ...)` ให้ `decide_update()` หรือ runtime ที่ preload baseline เดียวกัน

ระบบเก็บสำเนา history เป็น tuple ที่ไม่เปลี่ยนตาม list ของ caller การลงทะเบียนชื่อเดิมด้วย history ใหม่เพิกถอน id เดิม การลงทะเบียน id ไม่ได้ยืนยันสิทธิ์ของผู้ใช้ภายนอก: caller ยังต้องมี authorization ต่อ entity ของตน ระบบยังไม่รับ timestamps/raw events และไม่ได้อัปเดต baseline ตามเวลาโดยอัตโนมัติ ผู้เชื่อมต่อรับผิดชอบ freshness, revision และการเรียง hourly windows

### Context trust

`TrustedContext` ต้องติดตั้งผ่าน constructor โดยฝ่ายที่เชื่อถือได้ ไม่รับ context ใน request แล้วเพิ่มเข้า registry เอง ค่า `valid_from/valid_until` เป็น Unix timestamps และ `evidence_ref` ต้องไม่ว่าง

Registry ว่างเป็นค่าเริ่มต้น: เหตุการณ์ที่อ้างว่าเป็น backup/release อาจยังเกิด security alert เพราะไม่มีหลักฐานที่เชื่อถือได้มาหักล้าง ผู้ดูแลต้องเชื่อมระบบยืนยัน change records จริงก่อนใช้งาน การมี local registry ไม่ใช่ลายเซ็นดิจิทัลหรือหลักฐานเชิงสาเหตุว่า anomaly นั้นปลอดภัยแน่นอน

Fixtures ใน tests ใช้การอนุมัติสังเคราะห์เท่านั้น ห้ามนำมาเป็นรายการอนุมัติใน production

### Runtime

`IsolatedDecisionPool(calibration, workers=8, queue_capacity=256, deadline_s=.5)` คืน `Ticket` จาก `submit(input)`; `ticket.future.result()` ให้ decision และ timing metadata ใช้ใน `with` block หรือเรียก `close()` เสมอ

- `ticket.accepted=False` ต้องตรวจ final route: อาจเป็น input ผิดหรือ overload ไม่ใช่ decision ที่ประมวลผลสำเร็จ
- `OVERLOAD_REVIEW` ไม่ถูกเก็บไว้ให้ retry อัตโนมัติ caller ต้องกำหนด retry/backpressure/การแจ้งผู้ดูแลเอง ห้ามเพิกเฉยแล้วถือว่าปลอดภัย
- `TIMEOUT_REVIEW` เป็น budget exhaustion ไม่ใช่ negative security finding
- `cancel(ticket.job_id)` คืน `CANCELLED_REVIEW` และหยุด worker ที่กำลังทำงานนั้นถ้ามี
- Deadline เป็น budget ที่ watchdog บังคับด้วยการ kill process พร้อม scheduling/IPC overhead ไม่ใช่ hard-real-time SLA และไม่สามารถรับรองเวลาตายตัวเมื่อ OS หยุด parent process
- ฟังก์ชันนี้เป็น local Python interface ไม่ใช่ HTTP/JSON parser หรือ production authentication boundary ห้ามรับ pickle จากเครือข่าย
- ค่า `queue_ms` ในผลปัจจุบันวัดตั้งแต่เข้า `submit()` จน worker เริ่มคำนวณ จึงรวม ingress preflight, serialization และ IPC ไม่ใช่เวลารอคิวล้วน
- callback ที่ผูกกับ Future เป็นโค้ดของแอปที่เชื่อถือได้; อย่าใส่ blocking callback ในเส้นทาง watchdog

## ขีดจำกัดเริ่มต้น

| สิ่งที่จำกัด | ค่า |
|---|---:|
| Metrics | 256 |
| History ต่อ metric | 4,096 |
| Recent ต่อ metric | 256 |
| Numeric slots รวม | 262,144 |
| Context events ต่อ decision | 32 |
| ความยาว text field | 256 อักขระ |
| ค่าสัมบูรณ์ของตัวเลข | ไม่เกิน 1e100 และต้อง finite |
| History-stat cache | 256 entries ต่อ engine |
| Registered baseline names | 128 ต่อ engine |

ค่าที่ใหญ่กว่าขอบเขตจะถูกส่ง REVIEW/reject ไม่ใช่พยายามประมวลผลไม่จำกัด การส่ง input มากกว่า 10 metrics เปลี่ยน family-wise distribution; แม้ schema รองรับก็ต้องสอบเทียบความแม่นยำใหม่ ไม่ใช้ threshold เดิมอ้าง accuracy โดยอัตโนมัติ

## ข้อจำกัดที่ยังต้องรู้

- เป้าหมาย 10,000–20,000 full decisions/s ยังไม่ถือว่าผ่าน ดูผลวัดและข้อจำกัดตัวสร้างโหลดในรายงาน
- No-alert หมายถึงไม่มี anomaly ที่สังเกตได้ใน metrics ชุดนี้ ไม่ใช่พิสูจน์ว่าไม่มีการโจมตี
- `uncertainty` ของ numeric detector ยังเป็นระยะจาก threshold ไม่ใช่ calibrated probability/OOD detector; fallback ใช้ uncertainty=1 พร้อมเหตุผล
- การทดสอบเป็นการรันโปรแกรมจริงบนข้อมูลสังเคราะห์ ไม่ใช่ replay production traffic และไม่ได้พิสูจน์การตรวจจับทุก zero-day
- windows ต้นแบบเป็นรายชั่วโมง จึงแยก compute milliseconds ออกจากเวลาตั้งแต่เหตุการณ์เกิดจนถูกเก็บและตรวจพบ
