# Logic v8 input/output and execution contract

Logic v8 คือ deterministic anomaly triage บน metric windows ซึ่งใช้ math ของ v7 ร่วมกัน ไม่มี network call/LLM/API key ใน decision path

## Input

ใช้ `ScenarioInput` ที่ export จาก `black_swan`: ประวัติและ recent ของแต่ละ metric, statuses, lifecycle และ context รับ built-in dict/list กับ numeric int/float/None ตาม validation; bool/numeric strings ไม่ถูกแปลงเป็นข้อมูลตัวเลขโดยปริยาย

ค่าตั้งต้น: metrics 256, history/metric 4,096, recent/metric 256, scalar slots 262,144, contexts 32, text length 256, ค่าสัมบูรณ์ตัวเลขไม่เกิน 1e100 และต้อง finite; calibration และ metric distribution ต้องเหมาะกับข้อมูลจริง แม้ schema รองรับ input ใหญ่กว่าชุด benchmark ก็ไม่ได้รับรอง accuracy ที่ขนาดนั้น

`TrustedContext` ติดตั้งโดยผู้ดูแลผ่าน constructor; request ไม่ได้มีสิทธิ์ประกาศตัวเองว่าผ่านการอนุมัติ ต้องผูกกับแหล่ง change record ที่ตรวจสอบและสิทธิ์เข้าถึงจริงก่อนใช้ production

`register_baseline()` ลงทะเบียนประวัติ immutable และคืน baseline ID; `decide_update()` รับ recent window ของ baseline เดิม การแก้ history/revision ต้องลงทะเบียนใหม่ Caller รับผิดชอบ timestamps, hourly alignment, freshness และ entity authorization

## Output

ตรวจ `final_route`, `security_alert`, `operational_escalation` และ `reason_code` แยกกัน ชื่อ route เท่ากันไม่ได้แปลว่า review flag เท่ากัน

| ผล | ความหมาย |
|---|---|
| `NO_SECURITY_ALERT` | ไม่พบสัญญาณตามข้อมูลและ threshold ที่มี; ไม่ใช่ข้อพิสูจน์ว่าปลอดภัย |
| `SECURITY_ANOMALY_REVIEW` | พบความผิดปกติที่ต้องตรวจสอบ |
| `MODEL_REVIEW` / context review | หลักฐานก้ำกึ่ง/บริบทไม่พอ |
| `INVALID_INPUT_REVIEW` | รูปแบบ/ค่าข้อมูลไม่ถูกต้อง |
| `TELEMETRY_HOLD` / security risk hold | ข้อมูลไม่ครบหรือมีความเสี่ยงจากการ suppression |
| `CONFIGURATION_REVIEW` / `BASELINE_REVIEW` | config/baseline ไม่สามารถใช้ตัดสินใจได้ |
| `TIMEOUT_REVIEW` / `WORKER_ERROR_REVIEW` | คำนวณไม่สำเร็จภายใน runtime contract |
| `OVERLOAD_REVIEW` / `CANCELLED_REVIEW` | งานเกินขีดจำกัดหรือถูกยกเลิก; ไม่ใช่ negative finding |

Uncertainty ของ detector เป็น threshold distance ไม่ใช่ calibrated correctness probability/OOD detector; fallback ใช้ uncertainty=1 พร้อมเหตุผล

## Runtime

ใช้ `IsolatedDecisionPool` ผ่าน context manager และปิดด้วย `close()` เมื่อเลิกใช้งาน Direct `decide()` ไม่มี hard wall-clock deadline ใน process เดียว Runtime ใช้ spawn processes, bounded queue, watchdog และ restart; มีค่า scheduling/IPC overhead และไม่ใช่ hard-real-time SLA

OVERLOAD_REVIEW ไม่ retry เอง; caller ต้องจัดการ backpressure/การส่งต่ออย่างชัดเจน รวมถึง durable output และไม่เพิกเฉยต่อ fallback ภายในไม่มี HTTP parser, network authentication หรือ production authorization boundary ห้ามรับ pickle จากเครือข่าย

เอกสารต้นฉบับจาก ZIP ที่รักษาไว้: `docs/history/v8_bundle_README.md` เส้นทางไฟล์ในเอกสารนั้นเป็นโครงสร้างเก่า ใช้ README หลักสำหรับคำสั่งปัจจุบัน
