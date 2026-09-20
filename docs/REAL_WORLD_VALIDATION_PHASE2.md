# Real-World Validation Phase 2 — Experiment & Attack Scenario Contract

สถานะ: **PROPOSED / NOT STARTED**

วันที่กำหนดเกณฑ์: 20 กันยายน 2026

เอกสารนี้กำหนด **Acceptance Criteria** สำหรับ Phase 2 ของ Black Swan โดยต่อจาก Dataset Admission Contract ใน Phase 1

Phase 2 มีหน้าที่ทำให้ข้อมูล แผนการทดลอง และหลักฐานพร้อมสำหรับการประเมินแบบ blind ใน Phase 3 โดยยังไม่เปิดผล `blind_test` และยังไม่ใช้ผลจาก holdout เพื่อแก้ Logic v8, threshold หรือ scoring policy

---

## 1. เป้าหมาย

เปลี่ยนสถานะจาก:

> มีกติกาสำหรับรับ dataset จริงหรือ controlled telemetry แล้ว

ไปเป็น:

> มี dataset ที่ผ่าน contract มีคุณภาพเพียงพอ มี attack/control scenarios ที่ตรวจสอบย้อนกลับได้ และมี protocol ที่ freeze ก่อนเปิด blind test

คำถามที่ Phase 2 ต้องตอบคือ:

> **การทดลองถูกออกแบบดีพอหรือยังที่จะทำให้ผล Phase 3 เชื่อถือได้?**

Phase 2 ไม่ได้มีหน้าที่ตอบว่า Black Swan แม่นเพียงใด

---

## 2. ขอบเขต

Phase 2 รวมงานต่อไปนี้:

- รับ `real_security_telemetry` หรือ `controlled_security_telemetry`
- ตรวจ dataset ด้วย Phase 1 contract
- ตรวจ data quality และ metric compatibility
- แบ่งข้อมูลตามเวลาเป็น `baseline → calibration → blind_test`
- lock และ hash ชุด `blind_test`
- แยก hidden labels ออกจาก engine inputs และ predictions
- ออกแบบ attack/control scenarios
- map scenario กับ ATT&CK technique เมื่อเกี่ยวข้อง
- ระบุ expected observable footprint ที่ระบบมีโอกาสเห็นจริง
- freeze Logic v8, configuration, threshold, metric mapping และ evaluation protocol
- บันทึก provenance และ reproducibility evidence
- รัน regression tests ของ repository

Phase 2 **จบก่อนเปิดหรือประเมิน blind test**

---

## 3. สิ่งที่ไม่ทำใน Phase 2

- ไม่รายงาน accuracy, recall หรือ false-alert rate จาก blind test
- ไม่เปิดผล `blind_test`
- ไม่ใช้ blind-test outcome ปรับ threshold, calibration หรือ Logic v8
- ไม่ถือ synthetic fixture หรือ benchmark เดิมว่าเป็น real telemetry
- ไม่โจมตีระบบบุคคลที่สามหรือ environment ที่ไม่ได้รับอนุญาต
- ไม่ commit credentials, direct identifiers หรือ raw private telemetry เข้า Git
- ไม่อ้าง production readiness, zero-day coverage หรือ SLA
- ไม่ถือว่า attack ที่ sensor มองไม่เห็นเป็นสิ่งที่ detector ควรตรวจพบได้โดยอัตโนมัติ

---

## 4. Phase 2 Acceptance Gates

Phase 2 จะเป็น **PASS** ได้ต่อเมื่อทุก gate ด้านล่างผ่านครบ หาก gate ใดไม่ผ่าน สถานะรวมต้องเป็น **BLOCKED** หรือ **FAIL** และห้ามเปิด blind test

| Gate | Acceptance criterion | Required evidence |
|---|---|---|
| **G01 Dataset Admission** | ใช้ `real_security_telemetry` หรือ `controlled_security_telemetry` จริง ไม่ใช่ fixture/synthetic benchmark เดิม | Dataset manifest, source identity, authorization, SHA-256 และ byte size |
| **G02 Phase 1 Contract** | Dataset manifest ผ่าน `scripts/validate_real_world_dataset.py` โดยไม่มี error | Validator output, exit code `0` |
| **G03 Split Isolation** | ใช้ chronological split ตามลำดับ `baseline → calibration → blind_test` และไม่มี overlap | Split timestamps, split hashes และ validation output |
| **G04 Blind-test Lock** | `blind_test_locked=true` ก่อน calibration/evaluation และผู้พัฒนาไม่ใช้ผล blind test เพื่อปรับระบบ | Lock record, hash, UTC timestamp และผู้อนุมัติ |
| **G05 Data Quality** | Timestamp, cadence, missingness, duplicates, ordering, schema และ metric coverage ถูกตรวจ; missing/suppressed/failed ไม่ถูกแทนด้วย 0 โดยพลการ | Data-quality report และ machine-readable summary |
| **G06 Metric Compatibility** | ทุก signal ที่ส่งเข้า engine map กลับไปยัง canonical metric catalog ของ Black Swan ได้อย่างชัดเจน | Source-to-metric mapping พร้อม transformation ID/version |
| **G07 Ground Truth** | Labels ถูกสร้าง/ตัดสินแยกจาก predictions, ซ่อนจาก engine และเก็บคนละ artifact | Hidden label manifest, adjudication record และ separation check |
| **G08 Attack Scenarios** | ทุก attack scenario ระบุ preconditions, authorized environment, injection method, expected result และ ATT&CK mapping เมื่อเกี่ยวข้อง | Versioned scenario manifest และ injection-log hash |
| **G09 Observable Footprint** | ทุก scenario แยกสิ่งที่ sensor ควรเห็นออกจากผลที่ sensor มองไม่เห็น | Expected observable/unobservable mapping ต่อ scenario |
| **G10 Control Cases** | มี benign/control periods ที่สมจริง ครอบคลุม normal operation และ approved operational changes | Control manifest และ trusted-context evidence |
| **G11 Protocol Freeze** | Logic v8, threshold, calibration output, trusted-context policy, metric mapping และ scoring protocol ถูก freeze ก่อน Phase 3 | Git commit SHA และ configuration/artifact hashes |
| **G12 Evaluation Freeze** | Metrics, denominators, exclusions, review treatment และ failure accounting ถูกกำหนดก่อนเห็น blind result | Preregistered evaluation plan |
| **G13 Runtime Evidence Plan** | Protocol บังคับเก็บ timeout, crash, rejected input, overload, fallback, HOLD/REVIEW และ pending work โดยไม่ซ่อนเป็น negative | Run-manifest schema และ terminal-outcome accounting rules |
| **G14 Reproducibility** | บันทึก code commit, environment, commands, dataset hashes, config hashes, seeds (ถ้ามี) และ UTC timestamps | Reproducibility manifest |
| **G15 Regression Safety** | Infrastructure/เอกสาร/validator ที่เพิ่มใน Phase 2 ไม่ทำให้ repository regression เดิมเสีย | Full test output และ CI success |

### Decision rule

```text
PASS    = G01–G15 ผ่านครบ และ BLIND_TEST_EXECUTED=false
BLOCKED = หลักฐานหรือ authorization ยังไม่ครบ โดยยังไม่พบ contract violation ที่แก้ไม่ได้
FAIL    = มี contract violation, data leakage, split overlap, label leakage,
          unauthorized activity หรือ blind test ถูกใช้ปรับระบบ
```

ผล `PASS` ของ Phase 2 หมายถึง **พร้อมเริ่ม Phase 3** เท่านั้น ไม่ใช่หลักฐานว่า detector มีประสิทธิภาพในโลกจริงแล้ว

---

## 5. Dataset และ Split Contract

ใช้ contract เดิมจาก:

- `configs/real_world_validation_v1.json`
- `docs/REAL_WORLD_VALIDATION_PHASE1.md`
- `scripts/validate_real_world_dataset.py`

Canonical metrics ปัจจุบัน:

- `auth_failures`
- `unique_failed_accounts`
- `unique_source_ips`
- `successful_logins`
- `privileged_changes`
- `outbound_mb`
- `api_5xx`
- `endpoint_alerts`
- `file_rename_events`
- `inbound_requests`

Dataset ไม่จำเป็นต้องมีครบทุก metric แต่ metric ที่ใช้ทุกตัวต้องมี mapping และ transformation ที่ตรวจสอบย้อนกลับได้

### Split roles

1. **baseline** — ใช้สร้าง history/reference baseline
2. **calibration** — ใช้กำหนดค่าที่ protocol อนุญาตเท่านั้น
3. **blind_test** — final holdout ที่ lock และห้ามเปิดจน Phase 3

### Leakage prohibitions

- ห้ามใช้ blind labels ใน feature engineering
- ห้ามเลือก scenario/metric/threshold หลังเห็น blind outcome
- ห้ามคัดกรอง blind examples เพราะระบบทำผลได้ไม่ดี
- ห้ามรัน blind test ซ้ำแล้วเรียกทุกครั้งว่า independent holdout
- หาก blind test ถูกเปิดก่อน protocol freeze ต้อง invalidate split และสร้าง holdout ใหม่

---

## 6. Data Quality Requirements

Data-quality report ต้องตรวจอย่างน้อย:

- collection start/end เป็น UTC
- expected cadence เทียบกับ observed cadence
- missing windows และ missing fields
- duplicate records
- out-of-order timestamps
- schema/type violations
- non-finite numeric values
- impossible/out-of-range values
- status alignment ของ `missing / suppressed / failed`
- coverage ต่อ canonical metric
- transformation failures
- source clock drift หากตรวจได้
- split overlap และ boundary errors
- label coverage และ unresolved adjudication
- direct identifiers/credentials scan ก่อน commit artifacts

ทุกค่าที่วัดไม่ได้ต้องรายงานเป็น `unknown`, `missing`, `suppressed` หรือ `failed` ตามสาเหตุ ห้ามเปลี่ยนเป็นศูนย์เพียงเพื่อให้ engine รับ input ได้

---

## 7. Attack Scenario Contract

แต่ละ scenario ต้องมี field อย่างน้อยดังนี้:

```yaml
scenario_id:
scenario_version:
scenario_type: attack | control
title:
description:

authorization:
  environment:
  owner:
  approval_reference:

attack_mapping:
  framework: MITRE ATT&CK | not_applicable
  technique_ids: []

preconditions: []
injection_method:
injection_log_sha256:
start_time_utc:
end_time_utc:

expected_observable_metrics: []
expected_unobservable_effects: []
sensor_dependencies: []

ground_truth:
  label:
  adjudication_method:
  independent_of_predictions: true

split: baseline | calibration | blind_test

frozen_references:
  logic_commit:
  configuration_sha256:
  dataset_manifest_sha256:
  evaluation_plan_sha256:
```

### Observable-footprint rule

Scenario ต้องถูกจัดกลุ่มก่อนประเมิน:

- **Observable** — expected footprint ปรากฏใน metrics/sensors ที่ป้อนให้ engine
- **Partially observable** — มี footprint บางส่วน แต่ไม่ครบ
- **Unobservable** — ผลโจมตีไม่ปรากฏใน input metrics

กรณี `Unobservable` ห้ามรวมกับ false-negative denominator ของ observable detection โดยไม่แยกรายงาน เพราะ Logic v8 ไม่สามารถอนุมานเหตุการณ์จาก signal ที่ไม่ได้วัด

---

## 8. Control Scenario Requirements

Control cases ต้องมีมากกว่า “ช่วงที่ไม่มี attack” และควรครอบคลุม:

- normal daily/weekly variation
- authorized release/deployment
- approved backup or migration
- account lifecycle changes
- benign traffic surge
- telemetry degradation/missingness
- trusted-context expiry หรือ revocation
- operational change ที่มีหลักฐานอนุมัติ

Trusted context ต้องมาจาก record ที่ยืนยันได้ ไม่ใช้ข้อความจาก request ยืนยันตัวเอง และต้องมี scope, confidence, evidence reference และช่วงเวลาที่ตรงกับ scenario

---

## 9. Ground Truth และ Adjudication

Ground truth ต้อง:

- สร้างโดยผู้หรือกระบวนการที่ไม่เห็น prediction เมื่อทำได้
- มี `independent_of_predictions=true`
- ไม่ถูกส่งเข้า engine
- เก็บแยกจาก feature input และ prediction output
- ระบุ adjudication method และผู้รับผิดชอบ
- บันทึก disagreement/unresolved cases
- ห้ามแก้ label เพื่อให้ตรงกับ prediction โดยไม่มี evidence ใหม่

หาก label ถูกแก้หลัง freeze ต้องบันทึก version, เหตุผล, evidence และผลกระทบต่อ split integrity

---

## 10. Evaluation Plan ที่ต้อง Freeze

ก่อน Phase 3 ต้องกำหนดล่วงหน้าอย่างน้อย:

- primary และ secondary metrics
- numerator/denominator ของแต่ละ metric
- handling ของ HOLD/REVIEW
- handling ของ INVALID_INPUT/CONFIGURATION_REVIEW
- timeout/crash/worker error/fallback accounting
- overload/rejected request accounting
- false-alert definition
- attack-family และ observability strata
- latency measurement boundary
- exclusion criteria
- missing-result policy
- confidence intervals หรือ uncertainty reporting ที่จะใช้
- rule สำหรับ invalidating และ replacing a compromised holdout

ห้ามใช้ค่า uncertainty ของ Logic v8 เป็น calibrated probability เพราะหลักฐานปัจจุบันระบุว่าเป็นระยะห่างจาก threshold ไม่ใช่ calibrated confidence หรือ OOD detector

---

## 11. Protocol Freeze Record

Freeze record ต้องระบุ:

```yaml
freeze_id:
frozen_at_utc:
approved_by:

logic:
  version: v8
  git_commit:
  engine_sha256:
  runtime_sha256:

configuration:
  files: []
  combined_sha256:

dataset:
  manifest_path:
  manifest_sha256:
  blind_split_sha256:
  blind_test_locked: true

evaluation:
  plan_path:
  plan_sha256:

prohibited_after_freeze:
  - threshold changes
  - metric remapping
  - label exposure to engine
  - scenario selection using blind outcomes
  - logic changes based on blind outcomes
```

การแก้ไขสิ่งที่ freeze แล้วต้องสร้าง freeze record รุ่นใหม่ หากเคยเปิด blind result แล้ว ห้าม reuse holdout เดิมเป็น independent test

---

## 12. Required Evidence Package

ก่อนปิด Phase 2 ต้องมี artifact อย่างน้อย:

```text
docs/REAL_WORLD_VALIDATION_PHASE2.md
data/manifests/<dataset_manifest>.json
data/manifests/<split_lock>.json
configs/<source_to_metric_mapping>.json
scenarios/<scenario_manifest>.json
reports/<data_quality_report>.md
reports/<data_quality_summary>.json
evaluation/<preregistered_evaluation_plan>.md
evaluation/<protocol_freeze>.json
experiments/<phase2_run>/manifest.json
experiments/<phase2_run>/test_output.txt
```

Path ข้างต้นเป็นโครงสร้างที่เสนอ Artifact ที่มี private telemetry, direct identifiers หรือ credentials ต้องเก็บใน private storage ตามนโยบายของ repository และ commit เฉพาะ manifest/hash ที่ปลอดภัย

---

## 13. Reproducibility Manifest

Run manifest ต้องบันทึกอย่างน้อย:

```json
{
  "phase": 2,
  "run_id": "",
  "started_at_utc": "",
  "finished_at_utc": "",
  "git_commit": "",
  "logic_version": "v8",
  "dataset_manifest_sha256": "",
  "configuration_sha256": "",
  "scenario_manifest_sha256": "",
  "evaluation_plan_sha256": "",
  "environment": {},
  "commands": [],
  "random_seeds": [],
  "terminal_outcome_counts": {},
  "artifacts": [],
  "phase2_gate_results": {}
}
```

ทุก artifact ต้องมี path/URI, byte size และ SHA-256 เพื่อให้ตรวจ identity ได้

---

## 14. Phase 2 Definition of Done

```text
PHASE 2 ACCEPTANCE

[ ] G01 Real/controlled telemetry admitted
[ ] G02 Phase-1 dataset contract passed
[ ] G03 Chronological split isolation passed
[ ] G04 Blind test locked
[ ] G05 Data-quality inspection passed
[ ] G06 Source-to-metric mapping verified
[ ] G07 Independent hidden labels verified
[ ] G08 Attack scenario manifest complete
[ ] G09 Observable-footprint mapping complete
[ ] G10 Benign/control scenarios complete
[ ] G11 Logic/configuration/protocol frozen
[ ] G12 Evaluation metrics preregistered
[ ] G13 Runtime evidence plan complete
[ ] G14 Reproducibility manifest complete
[ ] G15 Full regression suite passed

BLIND TEST EXECUTED: NO
BLIND LABELS EXPOSED TO ENGINE: NO
LOGIC v8 MODIFIED FROM BLIND RESULTS: NO
PHASE 2 STATUS: NOT STARTED
```

ผู้ปิด Phase 2 ต้องแนบหลักฐานของ G01–G15 และยืนยันสามบรรทัดท้าย หากยืนยันไม่ได้ ห้ามเปลี่ยนสถานะเป็น PASS

---

## 15. Entry Criteria สำหรับ Phase 3

เริ่ม **Phase 3 — Blind Real-World Evaluation** ได้เมื่อ:

1. G01–G15 ผ่านครบ
2. Phase 2 status ถูกเปลี่ยนเป็น `PASS`
3. blind test ยังไม่เคยถูกใช้เพื่อปรับ Logic v8 หรือ protocol
4. protocol freeze และ hashes ตรวจซ้ำได้
5. ผู้รับผิดชอบอนุมัติการเปิด holdout อย่างชัดเจน

Phase 3 จึงเป็นจุดแรกที่อนุญาตให้เปิด holdout, รัน Logic v8 และคำนวณ detection rate, false-alert rate, review burden, failure rate, latency และผลแยกตาม attack family/observability โดยต้องไม่ย้อนกลับมาแก้ระบบแล้วใช้ holdout เดิมอ้างเป็น independent evidence อีก

---

## 16. หลักฐานฐานอ้างอิง

เอกสารนี้กำหนดเกณฑ์จากหลักฐานใน repository ต่อไปนี้:

- `docs/REAL_WORLD_VALIDATION_PHASE1.md`
- `configs/real_world_validation_v1.json`
- `reports/v8/v8_validation_report_th.md`
- `PROJECT_STATUS.md`

ข้อจำกัดสำคัญที่สืบทอดมา:

- ยังไม่มี real cybersecurity traffic replay ที่ผ่าน contract พร้อม labels อิสระ
- synthetic results เดิมไม่ใช่ independent proof ของ real-world accuracy
- 10,000–20,000 full decisions/s ยังไม่ผ่าน
- uncertainty ไม่ใช่ calibrated probability
- attack ที่ไม่มี footprint ใน input metrics ตรวจพบไม่ได้จาก metrics ชุดนั้น
- fixture ของ trusted context ไม่ใช่หลักฐานว่า production integration พร้อมใช้งาน
