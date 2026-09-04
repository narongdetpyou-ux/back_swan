# รายงานตรวจสอบ Black Swan Logic v6 กับข้อมูล Medicare จริง

## ผลลัพธ์หลัก

- ใช้ข้อมูล CMS รายปี 2013–2024, 13 code, 156 code-year observations
- ชุดทดสอบที่กำหนดไว้: 13/13 case ตรงกับผลที่คาด
- structural break ที่มี baseline ต่อเนื่อง: 100% recall
- lifecycle routing: 100%
- rolling non-event proxy: 0.00% alert, 5.77% model review

## Positive numeric cases ปี 2020

| HCPCS | Actual services | Consensus | Deviation | Classification |
|---|---:|---:|---:|---|
| 66984 | 7,498,575.0 | 0.67 | 30.7% | EXPLAINED_STRUCTURAL_BREAK |
| 94010 | 740,591.0 | 1.00 | 39.7% | EXPLAINED_STRUCTURAL_BREAK |
| G0121 | 211,856.0 | 1.00 | 34.9% | EXPLAINED_STRUCTURAL_BREAK |

## การแก้ category error ของ v5

v5 จะให้ผลผิดเมื่อ upstream แปลง `not_published` เป็นเลขศูนย์ เพราะ code ใหม่และ code ที่เลิกใช้ดูเหมือน shock ทางตัวเลข v6 จึงตรวจ lifecycle ก่อน forecast

| HCPCS | v5 เมื่อเติมศูนย์ | v6 |
|---|---|---|
| 0001A | BLACK_SWAN_CANDIDATE | NEW_CODE_STRUCTURAL_BREAK |
| 99441 | BLACK_SWAN_CANDIDATE | NEW_CODE_STRUCTURAL_BREAK |
| 99201 | BLACK_SWAN_CANDIDATE | CODE_RETIREMENT_STRUCTURAL_BREAK |
| G2211 | BLACK_SWAN_CANDIDATE | NEW_CODE_STRUCTURAL_BREAK |

## สิ่งที่ผลนี้พิสูจน์และยังไม่พิสูจน์

ผลนี้พิสูจน์ว่า v6 แยก anomaly, model disagreement, insufficient history, new/retired code และ known structural break ได้บนชุด Medicare ที่คัดไว้ โดยไม่เปลี่ยน threshold v5 เพื่อให้ผ่าน testcase

ยังไม่พิสูจน์ว่าเป็น production Black-Swan predictor: ชุด code ยังมีขนาดเล็ก, ข้อมูลเป็นรายปี, causal score ยังมาจากหลักฐานและ judgment, และช่วง non-event ยังไม่ได้ตรวจเหตุการณ์ภายนอกครบทุก code-year

## แหล่งข้อมูลหลัก

- [cms_catalog](https://catalog.data.gov/dataset/medicare-physician-other-practitioners-by-geography-and-service)
- [covid_elective](https://www.cms.gov/newsroom/press-releases/cms-releases-recommendations-adult-elective-surgeries-non-essential-medical-surgical-dental)
- [telephone_em](https://www.cms.gov/files/document/mm11805.pdf)
- [covid_vaccine_codes](https://www.cms.gov/files/document/cy-2023-payment-allowances-and-effective-dates-covid-19-vaccines.pdf)
- [99201_retirement](https://www.federalregister.gov/documents/2020/12/28/2020-26815/medicare-program-cy-2021-payment-policies-under-the-physician-fee-schedule-and-other-changes-to-part)
- [g2211_start](https://www.cms.gov/newsroom/fact-sheets/calendar-year-cy-2024-medicare-physician-fee-schedule-final-rule)
- [90739_context](https://www.cms.gov/medicare/regulations-guidance/physician-self-referral/list-cpt-hcpcs-codes)
