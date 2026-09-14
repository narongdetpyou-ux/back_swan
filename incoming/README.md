# ZIP ของ General Decision Lab

อัปโหลด `Black_Swan_Colab_Review_2026-09-14.zip` ไว้ในโฟลเดอร์นี้บน branch
`codex/colab-verified-runs` เพื่อให้เครื่องมือตรวจโค้ดใน ZIP ผ่าน GitHub Actions ได้

Workflow `Inspect General Lab archive` จะทำงานเมื่อไฟล์มาถึง:

1. ตรวจ SHA-256, ขนาด และชื่อไฟล์ภายใน archive
2. แสดงรายการไฟล์และโค้ดส่วน Core, tests, experiments และ NEXT_EXPERIMENT.md ที่อ่านได้
3. เก็บผลไว้ใน log ของ repository ส่วนตัวเพื่อให้ตรวจโค้ดและวาง patch จากไฟล์จริงได้

ขั้นนี้ยังไม่ execute โค้ดใน ZIP ผล `core_executed` จะเป็น false เสมอ
หากไม่มี ZIP ผลจะเป็น `awaiting_archive` ไม่ใช่ผลทดสอบ Core สำเร็จ

ไฟล์แนบใน ChatGPT ไม่ถูกคัดลอกมาที่ GitHub โดยอัตโนมัติ
ในเซสชันที่ไม่มีเครื่องมืออ่านไฟล์ workspace การอัปโหลด ZIP มาที่โฟลเดอร์นี้เป็นทางส่ง bytes
ให้ส่วนตรวจสอบที่รันได้อยู่แล้ว โดยไม่ต้องสร้าง public link

งานถัดไปหลังตรวจ source คือทำซ้ำปัญหาข้อความผิด 10 เคสและการแก้คำตอบจนแย่ลง 5 เคส
จาก Core 0.2.1 แล้วแก้ด้วยชุดพัฒนาและประเมินชุดสุดท้ายชุดใหม่
