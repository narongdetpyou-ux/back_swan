# Black Swan Logic v8 — ผลพัฒนาและทดสอบจริง

วันที่ประเมิน: 4 กันยายน 2026 · เริ่มรอบสุดท้าย 03:33:07 UTC

## สรุปผล

พัฒนา v8 ต่อจาก source v7 ที่มีอยู่จริง และจบรอบ implementation → regression → fault injection → performance/load evaluation แล้ว **แก้ข้อบกพร่องที่ทำซ้ำได้ด้าน input, metadata override และ failure isolation สำเร็จในชุดทดสอบที่ระบุ** แต่ **ยังไม่ผ่านเป้าหมาย 10,000–20,000 full decisions/วินาที และยังไม่ใช่ production-ready security system**

คำว่า “ทดสอบจริง” ในรายงานนี้หมายถึง **รันโค้ดและจับเวลาจริงบนเครื่องทดสอบ ด้วยข้อมูลสังเคราะห์** ไม่ใช่ตัวเลขคาดคะเน ไม่ใช่ traffic จากระบบ production และไม่ใช่การโจมตีระบบบุคคลที่สาม

| เกณฑ์รับงานรอบนี้ | ผล | หลักฐาน |
|---|---|---|
| กรณีข้อมูลเสียจาก audit เดิมไม่ทำให้ engine โยน exception ออก และผล serialize เป็น strict JSON ได้ | ผ่าน 27/27 กรณีที่รวม controls/config faults | test และ `resilience.edge_cases` |
| ข้อมูลว่าง/NaN/ข้อมูลไม่ครบไม่กลายเป็น no-alert โดยเงียบ | ผ่านกรณี regression | คืน INVALID_INPUT_REVIEW / HOLD พร้อมเหตุผล |
| metadata ไม่เกี่ยวข้อง/ไม่มีหลักฐานที่เชื่อถือได้ไม่กลบ strong attack | ผ่าน 4 กรณีหลัก | forged context, unrelated lifecycle, failed metric, short-history metric |
| คะแนน/route ของข้อมูลครบถ้วนไม่เปลี่ยนจากการ optimize | ตรง 1,500/1,500 กรณี held-out | `quality.identical_scores`, `identical_routes` |
| งานค้างถูกหยุดได้จริง และงานถัดไปทำงานได้ | ผ่านการ inject stall 3 ครั้ง รวม crash/exception อีก 2 ครั้ง | process kill/restart, explicit terminal REVIEW, recovery alert ทุกครั้ง |
| Regression suite ใหม่ | ผ่าน 24/24 | stdout/stderr และคำสั่งอยู่ใน JSON |
| งาน 1,000 decisions/s ต่อเนื่อง 30 วินาที ใน registered-window mode | ผ่าน 30,000/30,000 | reject 0, timeout 0, pending หลัง drain 0 |
| 10,000–20,000 full decisions/s | **ยังไม่ผ่าน/ยังพิสูจน์ไม่ได้** | ingress/ตัวสร้างโหลดไม่ทัน และมี overload rejections |
| รับรองตรวจทุก zero-day / ไม่มี crash ทุก input / production SLA | **ไม่ได้พิสูจน์** | อยู่นอกข้อสรุปที่ finite synthetic tests รองรับ |

## 1. เวอร์ชันและขอบเขตการเปลี่ยน

v7 เดิมไม่ถูกแก้ไข; SHA-256 engine อ้างอิง:

`9f0d58ebad4f09f7be1be23e7b76520f904472f8e877391d8895c872cedbe663`

v8 engine ที่ประเมิน:

`42d48bee71f42441044c264e85f3b63ee5e97916e4213dd69c7022f446b862d9`

v8 isolated runtime ที่ประเมิน:

`e370659a7cba0a9ee7243c886adbbedcafe67613fb1cdaf93da02c243f0f573d`

ตรวจ hash ของ engine/runtime/tests/evaluation harness ก่อนและหลังรอบสุดท้าย: ไม่เปลี่ยนระหว่างการประเมิน Hash ที่เหลืออยู่ใน `v8_evaluation_results.json`

การใช้ Black Swan workflow ทำให้กำหนดเกณฑ์รับงานจากข้อบกพร่องที่รันซ้ำได้ ตรวจ terminal outcomes แยกกัน และเพิ่มการทดสอบ kill/restart จริง ไม่ถือเพียง agreement หรือข้อความ “ตรวจทานแล้ว” เป็นหลักฐานความถูกต้อง

### สิ่งที่แก้

1. **Validation ก่อน feature extraction:** ชนิดข้อมูล, ขนาด series, finite numbers, numeric limits, status alignment และ calibration ผิดรูปคืน REVIEW
2. **Missing evidence ไม่ใช่ benign:** empty/None/history gaps มีเหตุผล HOLD/REVIEW; fallback uncertainty=1
3. **รักษาหลักฐานที่ยังใช้ได้:** lifecycle/quality ใช้แยกต่อ metric; strong anomaly ใน metric อื่นยังเป็น security alert
4. **Context trust แบบ explicit:** context ต้องตรง registry ที่ผู้ดูแลติดตั้งไว้ มี evidence reference, scope, confidence และช่วงเวลาที่สอดคล้อง; request เพิ่มความน่าเชื่อถือให้ตัวเองไม่ได้
5. **ลดการคำนวณ history ซ้ำ:** seasonal profile และ scale cache โดยใช้ค่าประวัติทั้งหมดเป็น key พร้อม eviction; เปลี่ยน history แล้วคำนวณใหม่
6. **Registered-window mode:** เก็บสำเนา baseline แบบ immutable และ content-addressed; revision ใหม่เพิกถอน token เก่า; validate recent window ทุก decision
7. **Bounded runtime:** จำกัดคิว, คืน OVERLOAD_REVIEW ชัดเจน, watchdog kill/restart งานค้าง, cancellation และ per-worker pipe เพื่อลดผลกระทบข้าม worker
8. **Transport preflight:** ตรวจ container/type/shape ก่อน serialization และไม่ส่ง arbitrary Python object เข้า pickle; มีค่าใช้จ่ายที่รวมในการวัด runtime

นี่ไม่ใช่การฝึก neural model ใหม่ และไม่ได้เปลี่ยน threshold เพื่อทำให้ผลทดสอบผ่าน

## 2. Speed & Latency

เครื่อง: Intel Xeon Platinum 8573C, Linux VM/container, Python 3.12.13, มองเห็น 9 logical CPUs, quota เทียบเท่า 8 cores, memory limit 14 GiB, GC เปิด

Full decision: 10 metrics × (168 history + 12 recent) = **1,800 numeric slots** จาก hourly aggregate generator เดิม เตรียม inputs ก่อนจับเวลา, warm-up 200 calls ต่อโหมด, 3 รอบ × 1,500 calls ต่อโหมด และสลับลำดับโหมดระหว่างรอบ

### Compute latency รวมการตรวจทานภายใน

| โหมด | Calls | Mean | P50 | P95 | P99 | สูงสุดที่พบ |
|---|---:|---:|---:|---:|---:|---:|
| v7 full input | 4,500 | 2.272 ms | 2.081 ms | 3.272 ms | 5.207 ms | 16.864 ms |
| v8 full input, history cache warm | 4,500 | **0.747 ms** | 0.658 ms | 1.086 ms | **2.433 ms** | 6.475 ms |
| v8 registered history + recent window | 4,500 | **0.288 ms** | 0.245 ms | 0.462 ms | **0.889 ms** | 4.088 ms |

v8 แบบ full input เร็วขึ้นประมาณ **3.04 เท่าใน mean** ของ paired run นี้ โดยยัง validate full payload และตรวจทานภายใน โหมด registered-window มีเงื่อนไขเตรียม history ล่วงหน้าต่างกัน จึงไม่ใช้เป็น apples-to-apples speedup ของ full payload

ตัวเลข v7 ใน audit ก่อนหน้าเฉลี่ย 1.660 ms เป็นคนละรอบ/ช่วงเวลา รายงานนี้ใช้ v7 ที่รันคู่กับ v8 รอบเดียวกันในการเปรียบเทียบ ไม่ผสมค่าข้ามรอบเพื่อขยายผลความเร็ว

### เมื่อ cache ไม่ช่วย

| เงื่อนไข v8 | Calls | Mean | P99 |
|---|---:|---:|---:|
| history ใหม่ทุกครั้ง/unique cache misses | 200 | 1.656 ms | 4.960 ms |
| ปิด cache บน mixed pool | 500 | 1.421 ms | 3.574 ms |

จึงไม่ควรนำ 0.747 ms ไปคาดการณ์ workload ที่เปลี่ยน history ทุก decision หรือมีจำนวน entities มากจน cache thrash โดยไม่ทดสอบใหม่ Registered baseline ก็ต้องมีนโยบาย freshness/update จริง; ระบบไม่ได้ freeze history แล้วถือว่าใช้ได้ตลอดไปโดยอัตโนมัติ

เวลาข้างต้น **ไม่รวม network, raw-event ingestion, aggregation, queue, IPC หรือ durable logs** และไม่ใช่เวลาจากเหตุการณ์จริงจนตรวจพบ ระบบเดิมใช้ข้อมูลรายชั่วโมง การมี compute latency ต่ำกว่า 1 ms ไม่ได้แปลว่าตรวจจับหลังเกิดเหตุภายใน 1 ms

## 3. Load test ที่รันจริง

ใช้ local open-loop submissions ที่กำหนดเวลาส่งโดยไม่รอ response, 8 worker processes, queue capacity 256, deadline 500 ms, warm-up 128 calls และ inputs เตรียมไว้แล้ว

วัด actual offering rate และ emitter lag ด้วย เพราะการตั้ง target ไม่รับรองว่าตัวสร้างโหลด/ตัวรับงานจะส่งทัน โดยเฉพาะ full-history payload ที่ต้องตรวจก่อน serialization

### ผลตัวอย่างรอบสุดท้าย

| โหมด / Target | ส่งได้จริงต่อวินาที | Offered | Computed | Reject | Computed throughput รวม drain |
|---|---:|---:|---:|---:|---:|
| Full / 500 | 500 | 1,500 | 1,500 | 0 | 500/s |
| Full / 2,000 | 1,994 | 6,000 | 6,000 | 0 | 1,966/s |
| Full / 10,000 ครั้งที่ 1 | **1,653** | 30,000 | 27,257 | 2,743 | 1,499/s |
| Full / 10,000 ครั้งที่ 2 | **1,819** | 30,000 | 24,220 | 5,780 | 1,458/s |
| Registered / 2,000 | 2,000 | 6,000 | 6,000 | 0 | 1,995/s |
| Registered / 10,000 ครั้งที่ 1 | 9,665 | 30,000 | 7,141 | 22,859 | 2,157/s |
| Registered / 10,000 ครั้งที่ 2 | 9,973 | 30,000 | 10,738 | 19,262 | 3,501/s |
| Registered / 20,000 | **12,912** | 60,000 | 9,513 | 50,487 | 2,008/s |

ทุกแถวข้างต้นมี pending หลัง drain = 0 และ counts ตรงกัน ไม่มี watchdog failure ในรอบสุดท้าย แต่ rejected requests **ไม่ได้ถูกประมวลผลเป็น security decisions** แม้จะได้ OVERLOAD_REVIEW กลับทันที Caller ต้องจัดการ backpressure/retry/การแจ้งผู้ดูแล ไม่ใช่มองว่าเสร็จงานตรวจแล้ว

Full target 10,000 ตั้งจำนวน 30,000 requests สำหรับ 3 วินาที แต่ส่งจริงใช้เวลาประมาณ 16.5–18.1 วินาที จึง **ไม่ใช่หลักฐานว่าได้ยิง full inputs ที่ 10,000/s จริง** เป็นหลักฐานว่าตัวรับงาน/ตัวสร้างโหลดและ transport path ในการตั้งค่านี้ไม่ทัน ใน registered mode ส่งได้ใกล้ 10,000/s แต่ส่วนใหญ่ถูก reject จึงยังไม่ผ่านเป้าหมายเช่นกัน

ผล high-load เปลี่ยนแปลงมากระหว่างรอบ และมี emitter lag จึงไม่ควรนำค่า throughput สูงสุดที่เห็นไปตั้งเป็น sustainable capacity หรือ SLA

### การทดสอบต่อเนื่อง 30 วินาที

Registered-window mode ที่ 1,000 decisions/s:

- ส่งจริง 30,000, computed 30,000, rejected 0, fallback 0, pending หลัง drain 0
- Throughput รวม drain **999.63 decisions/s**
- End-to-end P95 **4.70 ms**, P99 **33.58 ms** — รวม ingress preflight, local transport, queue และ watchdog response path
- นี่เป็น **30-second mini-soak** ไม่ใช่ long-duration production soak

สำหรับ full input ที่ประมาณ 2,000/s รอบสั้นทำครบ 6,000/6,000 แต่ end-to-end P99 **77.73 ms**; registered mode ที่ 2,000/s มี P99 **36.87 ms** แสดงว่าค่า compute latency อย่างเดียวไม่อธิบายความหน่วงของระบบทั้งหมด

### ข้อจำกัดการวัดทรัพยากร

CPU time ของ parent/children ถูกบันทึกแยก แต่รวม setup จึงไม่ใช่ steady-state utilization ล้วน การอ่าน aggregate RSS ผ่าน `/proc` คืนข้อมูลไม่ครบใน environment นี้ หลายรอบได้ 0 ซึ่งต้องตีความว่า **วัดไม่ได้/ไม่ครบ ไม่ใช่ใช้ RAM 0 bytes** ไม่ใช้ค่านี้รับรอง memory safety หรือกำหนดจำนวนเครื่อง

## 4. ความถูกต้องหลัง optimize

ใช้ fixed calibration เดิมและ fresh seeds ที่ไม่ใช้ใน regression development; 19 families × 100 = **1,900 scenarios** แต่ยังเป็น generator เดิม ไม่ใช่ independent real-world corpus

| การวัด | v7 | v8 |
|---|---:|---:|
| False alerts บน benign/control | 1/600 | 1/600 |
| Strong attack alerts | 600/600 | 600/600 |
| Evasive แต่มีสัญญาณที่สังเกตได้ | 286/300 | 286/300 |
| Operational capture รวมทุก attack family | 998/1,000 | 998/1,000 |
| คะแนนและ route ตรงกันใน complete-input subset | — | 1,500/1,500 |
| ผลอัตโนมัติที่ไม่ต้อง operational review ทั้งชุด | 718/1,900 | 518/1,900 |

จำนวน automatic outcomes ลดลง 200 เพราะ lifecycle cases ถูกกำหนดให้ส่งตรวจแทนถือว่าจบงานได้โดยอัตโนมัติ เป็นการเปลี่ยน policy ที่ตั้งใจ ไม่ใช่ accuracy improvement หรือการซ่อนความผิดด้วย review ทุกกรณี

ผล benign ด้านบนใช้ **operator-installed synthetic context fixtures** ตาม benchmark หาก registry ว่างตามค่าเริ่มต้น v8 alert บน benign/control **348/600** เนื่องจากไม่เชื่อคำอ้าง backup/release/migration ที่ยังไม่มี trusted record ดังนั้นต้องเชื่อมแหล่ง context ที่ยืนยันได้จริงก่อนใช้ operationally ไม่ใช่คัดลอก fixtures ไปอนุมัติใน production

คะแนนตรงกับ reference เป็น regression/consistency evidence ไม่ใช่ independent proof ว่าตรรกะ v7 ถูกต้องทุกกรณี

## 5. Edge cases และ Self-verification

### ข้อบกพร่องเดิมที่แก้แล้ว

| กรณี | v7 ที่ audit พบ | v8 ที่รันจริง |
|---|---|---|
| malformed numeric/status/context และ config corruption | 9 กรณีโยน exception | explicit INVALID_INPUT_REVIEW / CONFIGURATION_REVIEW; ไม่มี exception หลุดใน 27-case regression |
| empty input/recent/None/NaN | บางกรณี NO_SECURITY_ALERT หรือ JSON เสีย | REVIEW/HOLD; strict JSON ผ่าน |
| strong attack + forged/unverified context | อาจ BENIGN_EXPLAINED_BREAK | คง SECURITY_ANOMALY_REVIEW |
| strong attack + unrelated lifecycle | อาจ SERIES_LIFECYCLE_CHANGE ไม่ส่งตรวจ | คง security alert |
| strong attack + unrelated failed/short-history metric | HOLD กลบ security classification | คง security alert พร้อม data issues |
| history gaps / window misalignment | ตัด/เลื่อนข้อมูลได้โดยไม่แจ้งครบ | explicit HOLD/INVALID_INPUT_REVIEW |
| nested object/oversized series ผ่าน runtime | เดิมไม่มี bounded runtime | reject ก่อน serialization; ไม่เรียก arbitrary pickle hook |

ชุดใหม่ยังมี malformed fuzz 300 ตัวอย่าง, cache invalidation, immutable snapshot/revocation, concurrency/duplicate stability, trusted-context expiry/scope, verifier exception และ cancellation tests

### ถ้างานค้างหรือ worker ล้ม

ตั้ง fault-test budget 250 ms แล้ว inject งานนอนค้าง 60 วินาที:

- ตัดงานด้วย watchdog และ kill process จริงที่ **250.525, 250.627 และ 250.889 ms**
- คืน `TIMEOUT_REVIEW` พร้อม `HARD_DEADLINE_EXCEEDED`
- งาน strong attack ถัดไปกลับมา alert สำเร็จทั้ง 3 ครั้ง; recovery latency ประมาณ 160–188 ms ซึ่งรวมเวลา restart
- inject process crash และ exception เพิ่มอย่างละหนึ่งครั้ง: ได้ WORKER_ERROR_REVIEW และงานถัดไปสำเร็จ
- หลังปิด fault-test runtime: workers เหลือ 0

นี่พิสูจน์การแยกความผิดพลาดในกรณีที่ inject ไม่ได้พิสูจน์ว่าไม่มี crash ทุกชนิด Deadline มี scheduling overhead และ runtime ไม่ใช่ hard-real-time system; `decide()` ที่เรียกตรงใน process เดียวไม่มี hard cancellation

### รูปแบบใหม่ที่ไม่อยู่ใน benchmark เดิม — fresh seeds

| Pattern สังเคราะห์ | Security alert | ส่งตรวจรวม alert | ไม่ alert/ไม่ส่งตรวจ |
|---|---:|---:|---:|
| coordinated drop 80% | 100/100 | 100/100 | 0/100 |
| intermittent outbound ×1.8 | 100/100 | 100/100 | 0/100 |
| weak signals สลับ 4 metrics | 45/100 | 70/100 | **30/100** |
| outbound เพิ่มเพียง 2% ต่อเนื่อง | 0/100 | 0/100 | **100/100** |
| ไม่มี footprint ใน metrics ที่ส่งเข้า | 0/100 | 0/100 | **100/100** |

ไม่มี exception ใน valid-pattern tests เหล่านี้ แต่ไม่ได้ตรวจพบทุก pattern กรณีไม่มี footprint ใช้ข้อมูลเหมือน normal control ทุกค่า; ไม่อาจรู้เหตุการณ์ที่ sensors ไม่ได้วัดได้จากข้อมูลชุดนี้

Self-verification ของ engine เป็นกฎตรวจ input/quality/context/score แบบจำกัดขั้นตอน ไม่ใช่ LLM ที่คิดวนหรือเรียนรู้รูปแบบใหม่เอง ค่า uncertainty ของ numeric detector ยังเป็นสูตรระยะห่างจาก threshold ไม่ใช่ calibrated confidence หรือ OOD detector

## 6. สถานะส่งมอบและงานที่ยังเหลือ

**จบรอบพัฒนา v8 และส่งมอบโค้ด/ผลทดสอบที่ตรวจสอบซ้ำได้ แต่ไม่ได้ปิดเป้าหมาย production หรือ 10,000/s** ไม่มี deployment, external API, live policy change หรือการโจมตีภายนอกเกิดขึ้น

งานถัดไปที่มีหลักฐานรองรับ:

1. ลดต้นทุน front door และ IPC โดยออกแบบ ingestion/batching และ load generator แยกจาก process ที่รับงาน แล้ววัดใหม่พร้อม accounting เดิม
2. กำหนด entity count, baseline update cadence, freshness และแยก raw events/s จาก decisions/s ก่อนตั้ง capacity target
3. เชื่อม trusted context กับระบบอนุมัติจริง พร้อม access control/revocation ที่ตรวจสอบได้
4. เพิ่มข้อมูลที่วัดได้และชุด real-data replay ที่เข้ากับ schema เพื่อประเมิน weak/unseen attacks; ไม่ใช้ consistency กับ v7 แทน independent accuracy
5. เพิ่ม long-duration soak, resource telemetry ที่เชื่อถือได้, network/durable-output integration และ failure cases ที่ยังไม่ได้ทดสอบ

หาก 10,000 raw events/s ถูก aggregate เหลือ 1,000 decisions/s อาจตรงกับ workload ที่รอบ mini-soak ทำได้ แต่ **ระบบ aggregate/raw ingest นั้นยังไม่ได้สร้างหรือวัดในงานนี้** และไม่สามารถย้าย hourly calibration ไปใช้กับ buckets ระดับมิลลิวินาทีโดยไม่ประเมินใหม่

## 7. หลักฐานและการทำซ้ำ

ดู `README.md` สำหรับ contract และคำสั่งทั้งหมด คำสั่งหลัก:

```bash
python3 -m unittest discover -s black_swan_v8 -p test_black_swan_v8.py -v
python3 black_swan_v8/evaluate_black_swan_v8.py --output black_swan_v8/rerun_results.json
```

`v8_evaluation_results.json` เก็บ environment, code hashes, calibration, test output, actual timing samples, labels/seeds, route counts, offered/accepted/computed/rejected/fallback/pending และ fault-recovery outcomes รองรับการตรวจตัวเลขในรายงานนี้ซ้ำ
