# Credential cleanup status

วันที่ตรวจล่าสุด: 20 กันยายน 2026

ไฟล์ `openai-api-key.txt` เคยถูกติดตามใน repository ส่วนตัว และถูกนำออกจาก current files ตั้งแต่ PR #1

## Git history cleanup

วันที่ 20 กันยายน 2026 ได้ทำ one-time history rewrite บน `main` ด้วย `git-filter-repo` โดยลบ path:

- `openai-api-key.txt`
- workflow ชั่วคราวที่ใช้ทำ history purge

หลัง force-push ตรวจซ้ำผ่าน GitHub API:

- current tree: ไม่พบ `openai-api-key.txt`
- commit query `commits?path=openai-api-key.txt`: คืนค่าเป็นรายการว่าง `[]`
- one-time purge workflow: ไม่อยู่ใน current tree แล้ว

ผลนี้ยืนยันว่า path ดังกล่าวถูกลบออกจากประวัติ Git ที่เข้าถึงได้จาก `main` ปัจจุบัน อย่างไรก็ตาม สำเนาที่เคย clone/fork/cache ไว้นอก repository ไม่สามารถถูกลบจากที่นี่ได้

## Revoke / rotate status

**ยังไม่สามารถยืนยันการ revoke key เดิมที่บัญชีผู้ออก key ได้จาก repository หรือ GitHub**

การลบ current file และ rewrite Git history ไม่ได้เพิกถอน credential ที่ผู้ให้บริการต้นทาง หาก key เดิมยังมีอยู่ในบัญชีต้นทาง ต้อง revoke ที่ผู้ให้บริการนั้นโดยตรงก่อนเปลี่ยน repository เป็น public หรือถือว่า incident ปิดสมบูรณ์

Black Swan Logic v8 runtime ปัจจุบันไม่ต้องใช้ API key ใน quickstart/runtime หลัก จึงไม่มีเหตุผลให้เพิ่ม key ใหม่เข้า repository

## Prevention

- `.gitignore` ยังคงใช้ป้องกันไฟล์ credential ที่ทราบชื่อ
- snapshot exporter ไม่รวม `.git`, credentials, private data และ local runs
- ห้าม commit API keys, tokens หรือ credential files ลง repository แม้ repository จะเป็น private

อ้างอิง: GitHub documentation — Removing sensitive data from a repository
