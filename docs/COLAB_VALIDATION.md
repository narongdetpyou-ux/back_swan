# ตรวจการควบคุมการรัน Black Swan Colab

วันที่ 14 กันยายน 2026 • Core 0.2.1 • notebook revision verified-run-1

สมุดฉบับนี้เพิ่มการตรวจผลการทดลองก่อนให้ใช้คำตอบและ memory จากรอบนั้น
ต้นฉบับคือ Black_Swan_Colab_Reviewed.ipynb และรายงาน Black_Swan_Colab_Review_TH_2026-09-14.md
ที่ส่งมอบวันที่ 14 กันยายน ไม่ใช้ README ของ GitHub รุ่น v8 เป็นสถานะของ Core 0.2.1

## ข้อผิดพลาดที่ทำซ้ำแล้ว

การรันบน GitHub Actions ด้วย Python 3.12.3 ยืนยันว่าเซลล์รันเดิมผ่านเพียง 2/6 contract tests
อีก 4 กรณีไม่หยุดเมื่อควรหยุด: all_checks_passed=false, learning gate ไม่ผ่านแต่ผลรวม=true,
ไม่มี memory_frozen_for_holdout และใช้เลข 1 แทน boolean true

[ผลก่อนแก้](https://github.com/narongdetpyou-ux/back_swan/actions/runs/34881996793)
Commit: 0965251d80bb6dbddd426bf222ba111dac343fd9

การทดสอบเหล่านี้รัน Python จากเซลล์จริงโดยควบคุมผล subprocess
ยืนยันข้อผิดพลาดที่ขอบเขตของสมุดทดลอง ไม่ได้ยืนยันว่า Core เคยสร้างรายงานลักษณะนั้นจริง

## สิ่งที่เปลี่ยน

- ต้องมี all_checks_passed เป็น boolean true และผลตรวจที่จำเป็นทั้ง 11 รายการเป็น true
  ผลตรวจใหม่ที่เพิ่มมาและไม่ผ่านจะไม่ถูกมองข้าม
- เริ่มรันใหม่แล้วล้างสถานะสำเร็จเดิมทันที เซลล์ใช้ memory และรายงานต้องตรวจสถานะก่อนทำงาน
- ผูกผลที่ยืนยันกับโฟลเดอร์รอบนั้นและ SHA-256 ของ summary ปฏิเสธการใช้เมื่อไฟล์หายหรือเปลี่ยน
  การตรวจนี้คุ้มครอง summary ไม่ใช่การรับรองความสมบูรณ์ของทุกไฟล์ใน memory
- บันทึก stdout/stderr เต็มลงไฟล์ทั้งกรณีสำเร็จ ล้มเหลว และ timeout
  ใช้พฤติกรรม timeout ของ subprocess.run; ไม่อ้างว่าเพิ่มระบบกำจัด subprocess ลูกทุกระดับ
- ตรวจ SHA-256 ของ ZIP 0.2.1 ก่อนแตก เมื่อเปิดจากโฟลเดอร์โครงการที่มีอยู่แล้วจะใช้โค้ดในโฟลเดอร์นั้น
  ไม่อ้างว่าโฟลเดอร์ที่แก้เองตรงกับ ZIP
- ส่งออกผลที่ล้มเหลวเพื่อวิเคราะห์ได้ โดยมีสถานะ verified=false และ checksum ของ ZIP ผล
- ล้าง output/metadata การรันเก่า และสร้างป้ายจำนวนโจทย์ในกราฟจาก summary จริง

## ใช้บน Colab

1. เปิด notebooks/Black_Swan_Colab_Verified.ipynb จาก branch นี้หรือดาวน์โหลดแล้วอัปโหลดเข้า Colab
2. เลือก Run all และอัปโหลด Black_Swan_Colab_Review_2026-09-14.zip เมื่อสมุดร้องขอ
3. หากรอบทดสอบไม่ผ่าน เซลล์ใช้ผลและ memory จะหยุด ให้ดู log หรือรันเซลล์ส่งออกท้ายสมุด

ZIP ที่ต้องใช้มี SHA-256:

```text
730472506e90712731589d6633203bd964bdace67d67f26ba5676625b1bc8cb1
```

ยังต้องใช้ ZIP เดิมนี้ GitHub main มี Core v8 ซึ่งเป็นคนละฐานกับ general decision lab 0.2.1

## รันการทดสอบที่เพิ่ม

```bash
python3 -m unittest discover -s tests -p test_colab_notebook.py -v
```

ชุดทดสอบใช้ temporary directories และควบคุม subprocess เพื่อทดสอบกรณีผ่าน/ไม่ผ่าน
การรันซ้ำหลังผิดพลาด timeout ไฟล์หาย ไฟล์เปลี่ยน และการส่งออกหลักฐาน
ตรวจ syntax ของทุกเซลล์ด้วย Python แต่ไม่ได้รัน numerical experiment ทั้งสมุดหรือหน้า Colab

## งาน Core ที่ยังต้องทำต่อ

รายงานก่อนหน้าให้คำตอบถูก 225/235 และระบุว่าข้อความผิด 10 เคส กับการแก้คำตอบจนแย่ลง 5 เคสยังเหลืออยู่
ตัวเลขนี้เป็นผลเดิม ไม่ใช่ผลจากการแก้สมุดครั้งนี้
การแก้สองปัญหานี้ต้องเปิด src/black_swan_general/verifier.py, correction.py และ
 docs/NEXT_EXPERIMENT.md จาก ZIP 0.2.1 ตรวจชุดพัฒนา แล้วใช้ชุดทดสอบสุดท้ายชุดใหม่

ในรอบนี้เข้าถึงข้อความสมุดและรายงานได้ แต่ไม่มีเครื่องมือ Python/แตก ZIP ใน workspace
จึงใช้ GitHub Actions ทดสอบส่วนที่อ่านโค้ดได้ ไม่ได้เปลี่ยนหรือประเมิน Core 0.2.1 ใหม่

เอกสาร API: [subprocess.run](https://docs.python.org/3/library/subprocess.html#subprocess.run),
[unittest](https://docs.python.org/3/library/unittest.html)
