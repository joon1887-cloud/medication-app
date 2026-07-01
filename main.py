from fastapi import FastAPI, Request               # 앱 만드는 클래스
from fastapi.templating import Jinja2Templates     # HTML 파일 브라우저에 보내줌
from fastapi.staticfiles import StaticFiles        # CSS, JS 같은 정적 파일 제공
from pydantic import BaseModel                     # 입력 데이터 형태 검증 도구
from typing import List                            # 리스트 타입 사용하기 위해
from datetime import date, datetime                # 오늘 날짜, 생성 시각 가져오기 위해
import secrets                                      # 공유 링크용 랜덤 토큰 생성
from database import get_db, init_db               # database.py 에서 함수 불러오기
import requests    # 외부 API 호출용
DRUG_API_KEY = "bd7deeffc64e3900eacf5d3ce065ae9fc77345e59fdd29e54692c29e8ef2713e"    # 공공데이터포털 인증키

app = FastAPI()             # uvicorn이 앱 실행

app.mount("/static", StaticFiles(directory="static"), name="static")    # static 폴더 파일을 돌려줌
templates = Jinja2Templates(directory="templates")                      # templates 폴더에서 HTML 파일을 찾아서 돌려줌

init_db()                          # 서버 시작할 때 테이블 자동 생성

class Drug(BaseModel):             # 약 하나의 데이터 형태 정의
    drug_name: str
    ingredient: str = ""           # 성분명 (선택사항, 기본값 빈 문자열)
    days: int
    dosage: str
    frequency: str
    times: str
    meal_timing: str
    refill_date: str

class AddPrescription(BaseModel):  # 처방전 + 약 리스트 한번에 받는 클래스
    hospital: str
    visit_date: str
    drugs: List[Drug]              # 약 여러 개를 리스트로 받음

@app.get("/")
def home(request: Request):
    conn = get_db()
    prescriptions = conn.execute("SELECT * FROM prescriptions").fetchall()
    result = []
    for p in prescriptions:
        drugs = conn.execute(
            "SELECT * FROM prescription_drugs WHERE prescription_id = ?", (p["id"],)
        ).fetchall()
        result.append({
            "id": p["id"],
            "hospital": p["hospital"],
            "visit_date": p["visit_date"],
            "drugs": [dict(drug) for drug in drugs]  # Row → 딕셔너리로 변환
        })
    return templates.TemplateResponse(request, "index.html", {"prescriptions": result})

@app.post("/add")
def add_prescription(data: AddPrescription):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO prescriptions (hospital, visit_date) VALUES (?, ?)",
        (data.hospital, data.visit_date)
    )
    prescription_id = cursor.lastrowid  # 방금 저장된 처방전 ID 가져오기
    for drug in data.drugs:
        conn.execute(
            "INSERT INTO prescription_drugs (prescription_id, drug_name, ingredient, days, dosage, frequency, times, meal_timing, refill_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (prescription_id, drug.drug_name, drug.ingredient, drug.days, drug.dosage, drug.frequency, drug.times, drug.meal_timing, drug.refill_date)
        )
    conn.commit()       # 저장 확정
    return {"ok": True}

@app.delete("/delete/{prescription_id}")    # id로 특정 처방 삭제
def delete_prescription(prescription_id: int):
    conn = get_db()
    drug_ids = [row["id"] for row in conn.execute(
        "SELECT id FROM prescription_drugs WHERE prescription_id = ?", (prescription_id,)
    ).fetchall()]

    for drug_id in drug_ids:
        conn.execute("DELETE FROM medication_logs WHERE drug_id = ?", (drug_id,))

    conn.execute("DELETE FROM prescription_drugs WHERE prescription_id = ?", (prescription_id,))
    conn.execute("DELETE FROM prescriptions WHERE id = ?", (prescription_id,))

    conn.commit()
    return {"ok": True}

@app.put("/update/{prescription_id}")   # 처방전 + 약 수정
def update_prescription(prescription_id: int, data: AddPrescription):
    conn = get_db()

    conn.execute(
        "UPDATE prescriptions SET hospital = ?, visit_date = ? WHERE id = ?",
        (data.hospital, data.visit_date, prescription_id)
    )

    drug_ids = [row["id"] for row in conn.execute(
        "SELECT id FROM prescription_drugs WHERE prescription_id = ?", (prescription_id,)
    ).fetchall()]

    for drug_id in drug_ids:
        conn.execute("DELETE FROM medication_logs WHERE drug_id = ?", (drug_id,))

    conn.execute("DELETE FROM prescription_drugs WHERE prescription_id = ?", (prescription_id,))

    for drug in data.drugs:
        conn.execute(
            "INSERT INTO prescription_drugs (prescription_id, drug_name, ingredient, days, dosage, frequency, times, meal_timing, refill_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (prescription_id, drug.drug_name, drug.ingredient, drug.days, drug.dosage, drug.frequency, drug.times, drug.meal_timing, drug.refill_date)
        )

    conn.commit()
    return {"ok": True}

@app.get("/today")    # 오늘 복용해야 할 약 목록 가져오기
def get_today_drugs():
    conn = get_db()
    today = date.today().isoformat()  # 오늘 날짜 (예: 2026-06-30)

    drugs = conn.execute("""
        SELECT pd.*, p.hospital,
               COALESCE(ml.is_taken, 0) as is_taken,
               ml.id as log_id
        FROM prescription_drugs pd
        JOIN prescriptions p ON pd.prescription_id = p.id
        LEFT JOIN medication_logs ml ON ml.drug_id = pd.id AND ml.taken_date = ?
    """, (today,)).fetchall()

    return [dict(drug) for drug in drugs]

@app.post("/check/{drug_id}")    # 복용 체크 토글
def toggle_check(drug_id: int):
    conn = get_db()
    today = date.today().isoformat()

    existing = conn.execute(
        "SELECT * FROM medication_logs WHERE drug_id = ? AND taken_date = ?",
        (drug_id, today)
    ).fetchone()

    if existing:
        new_status = 0 if existing["is_taken"] else 1
        conn.execute(
            "UPDATE medication_logs SET is_taken = ? WHERE id = ?",
            (new_status, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO medication_logs (drug_id, taken_date, is_taken) VALUES (?, ?, 1)",
            (drug_id, today)
        )

    conn.commit()       # 저장 확정 — 빠져있던 부분 추가
    return {"ok": True}

@app.post("/share/{prescription_id}")    # 처방전 공유 링크 생성
def create_share_link(prescription_id: int):
    conn = get_db()
    token = secrets.token_urlsafe(8)    # 짧고 랜덤한 문자열 토큰 생성 (URL에 쓰기 안전한 형식)
    conn.execute(
        "INSERT INTO share_links (token, prescription_id, created_at) VALUES (?, ?, ?)",
        (token, prescription_id, datetime.now().isoformat())
    )
    conn.commit()
    return {"token": token}

@app.get("/shared/{token}")    # 공유 링크로 들어왔을 때 전문가 뷰 보여주기
def view_shared(token: str, request: Request):
    conn = get_db()
    link = conn.execute("SELECT * FROM share_links WHERE token = ?", (token,)).fetchone()
    if not link:
        return {"error": "유효하지 않은 링크입니다"}

    prescription = conn.execute("SELECT * FROM prescriptions WHERE id = ?", (link["prescription_id"],)).fetchone()
    drugs = conn.execute("SELECT * FROM prescription_drugs WHERE prescription_id = ?", (link["prescription_id"],)).fetchall()

    drugs_with_logs = []
    for drug in drugs:
        logs = conn.execute(
            "SELECT * FROM medication_logs WHERE drug_id = ? ORDER BY taken_date DESC", (drug["id"],)
        ).fetchall()
        drug_dict = dict(drug)
        drug_dict["logs"] = [dict(log) for log in logs]
        drug_dict["taken_count"] = sum(1 for log in logs if log["is_taken"])  # 복용한 날 수
        drug_dict["total_logs"] = len(logs)  # 기록된 전체 날 수
        drugs_with_logs.append(drug_dict)

    return templates.TemplateResponse(request, "shared.html", {
        "hospital": prescription["hospital"],
        "visit_date": prescription["visit_date"],
        "drugs": drugs_with_logs
    })
@app.get("/search-drug")
def search_drug(name: str, detail: bool = False):
    # detail=True 이면 성분명까지 가져오기 (선택 후 호출)
    # detail=False 이면 약 이름 목록만 빠르게 가져오기 (타이핑 중 호출)
    results = []

    try:
        res = requests.get(
            "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList",
            params={"serviceKey": DRUG_API_KEY, "itemName": name, "type": "json", "numOfRows": 7},
            timeout=5
        )
        data = res.json()
        items = data.get("body", {}).get("items", [])
        for item in items:
            ingredient = ""
            if detail:
                try:
                    res2 = requests.get(
                        "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06",
                        params={"serviceKey": DRUG_API_KEY, "item_name": item.get("itemName", ""), "type": "json", "numOfRows": 1},
                        timeout=5
                    )
                    data2 = res2.json()
                    items2 = data2.get("body", {}).get("items", [])
                    if items2:
                        raw = items2[0].get("MATERIAL_NAME", "")
                        if "성분명 : " in raw:
                            ingredient = raw.split("성분명 : ")[1].split("|")[0].strip()
                except Exception:
                    pass

            results.append({
                "name": item.get("itemName", ""),
                "efficacy": item.get("efcyQesitm", "") if detail else "",
                "usage": item.get("useMethodQesitm", "") if detail else "",
                "ingredient": ingredient
            })
    except Exception:
        pass

@app.get("/weekly")    # 최근 7일 복약 기록 가져오기
def get_weekly():
    conn = get_db()
    from datetime import timedelta
    today = date.today()
    result = []

    for i in range(6, -1, -1):    # 6일 전 ~ 오늘
        day = today - timedelta(days=i)
        day_str = day.isoformat()

        total = conn.execute("SELECT COUNT(*) FROM prescription_drugs").fetchone()[0]
        taken = conn.execute(
            "SELECT COUNT(*) FROM medication_logs WHERE taken_date = ? AND is_taken = 1", (day_str,)
        ).fetchone()[0]

        result.append({
            "date": day_str,
            "weekday": ["일", "월", "화", "수", "목", "금", "토"][day.weekday() % 7 if day.weekday() != 6 else 0],
            "total": total,
            "taken": taken,
            "rate": round(taken / total * 100) if total > 0 else 0
        })

    return result