# สถานะ Black Swan

อัปเดต: 20 กันยายน 2026 — repository status, validation phases, CI และงานค้าง

## สรุปสถานะ

| ส่วนงาน | สถานะ | หลักฐาน |
|---|---|---|
| Repository | Private `narongdetpyou-ux/back_swan`; default branch `main` | GitHub repository metadata |
| รุ่นหลัก | **Logic v8** ใน `src/black_swan/` | source/runtime และ v8 validation report |
| Phase 1 — Dataset Contract | **COMPLETE** | commit `69d35a1f6a7e7e6eca6189ede035a0c8f9526428` |
| Phase 2 — Experiment & Attack Scenario Contract | **CRITERIA READY / EXECUTION NOT STARTED** | `docs/REAL_WORLD_VALIDATION_PHASE2.md` |
| Phase 3 — Blind Real-World Evaluation | **NOT STARTED** | blind test ยังไม่ถูกเปิด |
| Production readiness | **NOT READY** | ยังไม่มี admitted real/controlled telemetry และ end-to-end production validation |

## หลักฐานที่ยืนยันล่าสุด

- Repository refresh CI ตรวจ 102 files โดย errors = 0 และ test files มี 6 ไฟล์
- พบ 85 test methods: v7 9, v8 24, Colab 25, archive inspection 8, project workflows 13 และ Phase 1 contract 6
- GitHub Actions run `35483126146` ผ่าน:
  - Phase 1 contract tests 6/6
  - full repository regression 85/85 ใน 10.726 วินาที
  - known-good manifest ผ่าน
  - overlap fixture ถูก reject ตาม contract
  - repository inventory ผ่าน
- การเพิ่มเอกสาร Phase 2 ที่ commit `4275fe5749f414a5ebf3f058db7e6f6d79d6a7b8` ไม่เปลี่ยน source, runtime, threshold หรือ test code
- Repository refresh commit `5a1fe7d2d8aac93a3fd34e38db8da55b8e2a2387` ผ่าน CI ครบ:
  - Repository CI run `35502747378`: inventory 102 files, errors 0, regression 85/85, valid fixture ผ่าน และ overlap fixture ถูก reject
  - Colab validation run `35502747445`: notebook contract 25/25 และ inventory ผ่าน
  - General archive inspection run `35502747389`: inspector tests 8/8; archive SHA-256 `730472506e90712731589d6633203bd964bdace67d67f26ba5676625b1bc8cb1` ตรงกับ archive ที่เคยตรวจ และ core ไม่ถูก execute
- repository-wide CI จะรัน inventory และ full regression บนทุก push เข้า `main` และทุก pull request

## Validation phases

### Phase 1 — COMPLETE

Phase 1 สร้าง Dataset Admission Contract, manifest validator, chronological split checks, hidden-label separation, privacy checks, fixtures และ CI สำเร็จแล้ว

คำว่า COMPLETE ในที่นี้หมายถึง **contract พร้อมใช้งาน** ไม่ได้หมายความว่ามี dataset จริงที่ผ่าน admission หรือพิสูจน์ accuracy ในโลกจริงแล้ว

### Phase 2 — CRITERIA READY / NOT STARTED

เกณฑ์ G01–G15, Attack Scenario Contract, Protocol Freeze, Evaluation Freeze, Reproducibility Manifest และ Definition of Done ถูกบันทึกแล้วใน `docs/REAL_WORLD_VALIDATION_PHASE2.md`

ยังไม่มีหลักฐานว่า:

- real/controlled telemetry ผ่าน G01–G15
- Phase 2 protocol ถูก freeze
- blind test ถูกเปิด
- Logic v8 ถูกประเมินกับ real-world holdout

### Phase 3 — NOT STARTED

Phase 3 เริ่มได้หลัง Phase 2 ผ่านครบเท่านั้น Blind test ต้องไม่ถูกใช้ปรับ logic, threshold, metric mapping หรือ evaluation protocol

## Pull requests

- PR #7 ปิดเป็น **redundant** วันที่ 20 กันยายน 2026 หลังตรวจว่าไฟล์ที่เปลี่ยนทั้ง 7 รายการมี Git blob SHA ตรงกับ `main` ทุกไฟล์ Phase 1 อยู่บน `main` แล้ว จึงไม่มีเนื้อหาใหม่ให้ merge
- PR #6 ยังคง **OPEN / BLOCKED — DO NOT MERGE YET**
  - evidence ระบุ admission decision = `REJECTED`
  - 30 localhost events, ช่วงเก็บต่ำกว่า 1 วินาที, source IP เดียว และ coverage 4/10 metrics
  - branch รายงาน full suite 84/85 โดย timing-sensitive runtime test ล้ม 1 รายการ
  - ยังไม่มี successful status checks บน head commit
  - หลักฐานนี้มีประโยชน์เป็น rejected admission example แต่ยังไม่ทำให้ Phase 2 เริ่ม

## Security

- `openai-api-key.txt` ถูกนำออกจาก current files ตั้งแต่ PR #1
- วันที่ 20 กันยายน 2026 มี one-time history rewrite เพื่อลบ path ดังกล่าวออกจากประวัติ `main` ที่เข้าถึงได้
- GitHub API ตรวจ current tree และ commit query แล้วไม่พบ path
- **ยังยืนยันไม่ได้ว่า key เดิมถูก revoke/rotate ที่ผู้ให้บริการต้นทาง**
- สำเนาที่เคย clone/fork/cache ไว้นอก repository ไม่สามารถลบจาก repository นี้ได้

รายละเอียด: `docs/SECURITY_STATUS.md`

## Backup และ reproducibility

- มี snapshot exporter, SHA-256 sidecar และ restore verifier
- มี run manifests, source/config/artifact hashes และ non-overwriting run directories
- Slack มี verification/restore manifest ของ snapshot ที่ commit `69d35a1f...` แต่ยังไม่ใช่ raw-byte backup และไม่ครอบคลุม commits หลังจากนั้น
- จึงยังไม่ถือว่ามี external backup ของ current `main` ที่กู้ไฟล์จริงได้ครบทั้งหมด

รายละเอียด: `docs/DATA_STORAGE.md` และ `docs/EXPERIMENTS.md`

## ขอบเขตที่ยังไม่ผ่าน

- ยังไม่ deploy เป็น production service
- ยังไม่มี admitted real cybersecurity telemetry พร้อม labels อิสระสำหรับ Phase 2
- ยังไม่มี Phase 3 blind real-world evaluation
- 10,000–20,000 full decisions/s ยังไม่ผ่าน
- Trust registry ยังไม่ได้เชื่อม verified operational change records จริง
- ยังไม่มี long-duration production soak, network/storage integration หรือ production SLA
- uncertainty ของ Logic v8 ไม่ใช่ calibrated probability หรือ OOD detector
- credential revocation ที่ต้นทางยังไม่ยืนยัน
- external raw-byte backup ของ current `main` ยังไม่เสร็จ

## งานถัดไปตามลำดับ

1. รักษา PR #6 เป็น blocked จน full regression ผ่านและ evidence/validator ถูก review
2. จัดหา real หรือ controlled telemetry ที่มี duration, volume, source diversity และ metric coverage เพียงพอ
3. ทำ Phase 2 ตาม G01–G15 โดยยังไม่เปิด blind test
4. Freeze logic/config/evaluation protocol ก่อน Phase 3
5. สร้าง external raw-byte backup ของ current `main` พร้อม checksum และทดสอบ restore
6. ยืนยัน revoke/rotate credential เดิมที่บัญชีผู้ให้บริการต้นทาง

## เอกสารหลัก

- `README.md`
- `docs/CONTRACT.md`
- `docs/REAL_WORLD_VALIDATION_PHASE1.md`
- `docs/REAL_WORLD_VALIDATION_PHASE2.md`
- `reports/v8/v8_validation_report_th.md`
- `docs/SECURITY_STATUS.md`
- `docs/DATA_STORAGE.md`
- `docs/EXPERIMENTS.md`
