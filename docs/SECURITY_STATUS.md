# Credential cleanup status

วันที่ตรวจ: 4 กันยายน 2026

ไฟล์ `openai-api-key.txt` เคยถูกติดตามใน repository ส่วนตัว PR #1 นำไฟล์ออกและเพิ่ม `.gitignore`; รวมเข้า main แล้วที่ commit `287a269e79364343193bd2c1253883ef32622e89`

งานนี้ไม่อ่าน เปิดเผย หรือลองใช้ค่า key เดิม และไม่คัดลอกค่าเข้ารายงาน/ชุดส่งมอบใหม่ การตรวจ current files และ ZIP ใช้ตัวค้นหารูปแบบ credential ที่รายงานเฉพาะชื่อไฟล์ ไม่พิมพ์ค่าที่พบ

**สถานะ revoke/rotate: ยังไม่ยืนยัน** ไม่มีช่องทางจัดการบัญชีผู้ออก key ที่ใช้ยืนยันการเพิกถอนได้ในงานนี้ ผู้ดูแลต้องตรวจในบัญชีต้นทางและ revoke/rotate key เดิมหากยังใช้งานได้

การลบไฟล์ปัจจุบันหรือ merge PR ไม่เพิกถอน key และไม่ลบจาก Git history งานนี้ไม่ rewrite/force-push ประวัติ การทำเช่นนั้นมีผลต่อ commit IDs และสำเนาของผู้ร่วมงาน จึงต้องมีแผนที่เจาะจงหลังจัดการ key แล้ว

Snapshot exporter ไม่รวม `.git` หรือ credentials และตรวจเนื้อหา ZIP แต่การตรวจด้วย pattern ไม่ใช่การรับรองว่าไม่มี secrets ทุกชนิด

อ้างอิง: [GitHub — Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
