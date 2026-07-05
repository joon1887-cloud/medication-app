from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from datetime import date, datetime
import secrets
from database import get_db, init_db
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor

DRUG_API_KEY = "bd7deeffc64e3900eacf5d3ce065ae9fc77345e59fdd29e54692c29e8ef2713e"

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── 약 캐시 ──────────────────────────────────────────────
_drug_cache: dict = {}  # { drug_name: { "ingredient": "...", "efficacy": "...", "usage": "..." } }

def fetch_drug_detail(name: str) -> dict:
    """단일 약 이름으로 API 호출 → 상세 정보 반환 (캐시에도 저장)"""
    if name in _drug_cache:
        return _drug_cache[name]
    try:
        res = requests.get(
            "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList",
            params={"serviceKey": DRUG_API_KEY, "itemName": name, "type": "json", "numOfRows": 1},
            timeout=5
        )
        data = res.json()
        items = data.get("body", {}).get("items", [])
        if not items:
            return {}
        item = items[0]
        efficacy = item.get("efcyQesitm", "")
        usage = item.get("useMethodQesitm", "")

        ingredient = ""
        try:
            res2 = requests.get(
                "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06",
                params={"serviceKey": DRUG_API_KEY, "item_name": name, "type": "json", "numOfRows": 1},
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

        result = {"ingredient": ingredient, "efficacy": efficacy, "usage": usage}
        _drug_cache[name] = result
        return result
    except Exception:
        return {}


def preload_drug_cache():
    """서버 시작 시 DB에 등록된 약들 미리 캐싱"""
    conn = get_db()
    drugs = conn.execute("SELECT DISTINCT drug_name FROM prescription_drugs").fetchall()
    for row in drugs:
        name = row["drug_name"]
        if name and name not in _drug_cache:
            fetch_drug_detail(name)
    print(f"[캐시] {len(_drug_cache)}개 약 사전 로드 완료")


def fill_missing_ingredients():
    """ingredient 비어있는 기존 약들 자동으로 성분명 채우기"""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, drug_name FROM prescription_drugs WHERE ingredient IS NULL OR ingredient = ''"
    ).fetchall()
    if not rows:
        print("[성분명] 채울 항목 없음")
        return
    print(f"[성분명] {len(rows)}개 약 성분명 자동 채우기 시작...")
    updated = 0
    for row in rows:
        detail = fetch_drug_detail(row["drug_name"])
        ingredient = detail.get("ingredient", "")
        if ingredient:
            conn.execute(
                "UPDATE prescription_drugs SET ingredient = ? WHERE id = ?",
                (ingredient, row["id"])
            )
            updated += 1
    conn.commit()
    print(f"[성분명] {updated}개 업데이트 완료")


# ── 앱 시작 ──────────────────────────────────────────────
init_db()
preload_drug_cache()
fill_missing_ingredients()


# ── 모델 ─────────────────────────────────────────────────
class Drug(BaseModel):
    drug_name: str
    ingredient: str = ""
    days: int
    dosage: str
    frequency: str
    times: str
    meal_timing: str
    refill_date: str

class AddPrescription(BaseModel):
    hospital: str
    visit_date: str
    drugs: List[Drug]


# ── 라우트 ────────────────────────────────────────────────
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
            "drugs": [dict(drug) for drug in drugs]
        })
    return templates.TemplateResponse(request, "index.html", {"prescriptions": result})


@app.post("/add")
def add_prescription(data: AddPrescription):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO prescriptions (hospital, visit_date) VALUES (?, ?)",
        (data.hospital, data.visit_date)
    )
    prescription_id = cursor.lastrowid
    for drug in data.drugs:
        # 성분명 없으면 캐시/API에서 자동 채우기
        ingredient = drug.ingredient
        if not ingredient:
            detail = fetch_drug_detail(drug.drug_name)
            ingredient = detail.get("ingredient", "")
        conn.execute(
            "INSERT INTO prescription_drugs (prescription_id, drug_name, ingredient, days, dosage, frequency, times, meal_timing, refill_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (prescription_id, drug.drug_name, ingredient, drug.days, drug.dosage, drug.frequency, drug.times, drug.meal_timing, drug.refill_date)
        )
    conn.commit()
    return {"ok": True}


@app.delete("/delete/{prescription_id}")
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


@app.put("/update/{prescription_id}")
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
        ingredient = drug.ingredient
        if not ingredient:
            detail = fetch_drug_detail(drug.drug_name)
            ingredient = detail.get("ingredient", "")
        conn.execute(
            "INSERT INTO prescription_drugs (prescription_id, drug_name, ingredient, days, dosage, frequency, times, meal_timing, refill_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (prescription_id, drug.drug_name, ingredient, drug.days, drug.dosage, drug.frequency, drug.times, drug.meal_timing, drug.refill_date)
        )
    conn.commit()
    return {"ok": True}


@app.get("/today")
def get_today_drugs():
    conn = get_db()
    today = date.today().isoformat()

    drugs = conn.execute("""
        SELECT pd.*, p.hospital
        FROM prescription_drugs pd
        JOIN prescriptions p ON pd.prescription_id = p.id
    """).fetchall()

    def parse_slots(times_str, frequency):
        """사용자가 선택한 시간대만 슬롯으로 사용"""
        times_list = [t.strip() for t in times_str.split('·') if t.strip()]
        if not times_list:
            times_list = ['아침']
        return times_list

    result = []
    for drug in drugs:
        drug_dict = dict(drug)
        slots = parse_slots(drug_dict['times'], drug_dict['frequency'])

        for slot in slots:
            log = conn.execute(
                "SELECT * FROM medication_logs WHERE drug_id = ? AND taken_date = ? AND time_slot = ?",
                (drug_dict['id'], today, slot)
            ).fetchone()
            result.append({
                **drug_dict,
                'slot': slot,
                'is_taken': log['is_taken'] if log else 0,
                'log_id': log['id'] if log else None,
            })

    return result


@app.post("/check/{drug_id}")
def toggle_check(drug_id: int, slot: str = ""):
    conn = get_db()
    today = date.today().isoformat()
    existing = conn.execute(
        "SELECT * FROM medication_logs WHERE drug_id = ? AND taken_date = ? AND time_slot = ?",
        (drug_id, today, slot)
    ).fetchone()
    if existing:
        new_status = 0 if existing["is_taken"] else 1
        conn.execute(
            "UPDATE medication_logs SET is_taken = ? WHERE id = ?",
            (new_status, existing["id"])
        )
    else:
        conn.execute(
            "INSERT INTO medication_logs (drug_id, taken_date, time_slot, is_taken) VALUES (?, ?, ?, 1)",
            (drug_id, today, slot)
        )
    conn.commit()
    return {"ok": True}

@app.post("/share/{prescription_id}")
def create_share_link(prescription_id: int):
    conn = get_db()
    token = secrets.token_urlsafe(8)
    conn.execute(
        "INSERT INTO share_links (token, prescription_id, created_at) VALUES (?, ?, ?)",
        (token, prescription_id, datetime.now().isoformat())
    )
    conn.commit()
    return {"token": token}


@app.get("/shared/{token}")
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
        drug_dict["taken_count"] = sum(1 for log in logs if log["is_taken"])
        drug_dict["total_logs"] = len(logs)
        drugs_with_logs.append(drug_dict)
    return templates.TemplateResponse(request, "shared.html", {
        "hospital": prescription["hospital"],
        "visit_date": prescription["visit_date"],
        "drugs": drugs_with_logs
    })


@app.get("/search-drug")
def search_drug(name: str, detail: bool = False):
    """
    detail=False : 약 이름 목록만 (자동완성용, 빠름)
    detail=True  : 성분명 + 효능 + 복용법까지 (약 선택 후 호출)
    """
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
            drug_name = item.get("itemName", "")
            efficacy = item.get("efcyQesitm", "") if detail else ""
            usage = item.get("useMethodQesitm", "") if detail else ""
            ingredient = ""

            if detail:
                # 캐시에 있으면 바로 사용
                if drug_name in _drug_cache:
                    cached = _drug_cache[drug_name]
                    ingredient = cached.get("ingredient", "")
                    efficacy = cached.get("efficacy", efficacy)
                    usage = cached.get("usage", usage)
                else:
                    try:
                        res2 = requests.get(
                            "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06",
                            params={"serviceKey": DRUG_API_KEY, "item_name": drug_name, "type": "json", "numOfRows": 1},
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
                    # 캐시에 저장
                    _drug_cache[drug_name] = {"ingredient": ingredient, "efficacy": efficacy, "usage": usage}

            results.append({
                "name": drug_name,
                "efficacy": efficacy,
                "usage": usage,
                "ingredient": ingredient
            })
    except Exception:
        pass

    return results  # ← 기존 코드에서 빠져있던 return!


@app.get("/drug-info")
def drug_info(name: str):
    """
    검색 페이지용 상세 정보 API
    e약은요 + 제품허가정보 통합 반환
    """
    results = []
    try:
        res = requests.get(
            "http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList",
            params={"serviceKey": DRUG_API_KEY, "itemName": name, "type": "json", "numOfRows": 10},
            timeout=5
        )
        data = res.json()
        items = data.get("body", {}).get("items", [])
        for item in items:
            drug_name = item.get("itemName", "")
            ingredient = ""
            caution = item.get("atpnQesitm", "")          # 주의사항
            side_effect = item.get("seQesitm", "")         # 부작용
            interaction = item.get("intrcQesitm", "")      # 상호작용
            storage = item.get("depositMethodQesitm", "")  # 보관법

            # 캐시 or API로 성분명 가져오기
            if drug_name in _drug_cache:
                ingredient = _drug_cache[drug_name].get("ingredient", "")
                efficacy = _drug_cache[drug_name].get("efficacy", item.get("efcyQesitm", ""))
                usage = _drug_cache[drug_name].get("usage", item.get("useMethodQesitm", ""))
            else:
                efficacy = item.get("efcyQesitm", "")
                usage = item.get("useMethodQesitm", "")
                try:
                    res2 = requests.get(
                        "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06",
                        params={"serviceKey": DRUG_API_KEY, "item_name": drug_name, "type": "json", "numOfRows": 1},
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
                _drug_cache[drug_name] = {"ingredient": ingredient, "efficacy": efficacy, "usage": usage}

            results.append({
                "name": drug_name,
                "ingredient": ingredient,
                "efficacy": efficacy,
                "usage": usage,
                "caution": caution,
                "side_effect": side_effect,
                "interaction": interaction,
                "storage": storage,
            })
    except Exception:
        pass
    return results


@app.get("/search-page")
def search_page(request: Request):
    return templates.TemplateResponse(request, "search.html", {})


@app.get("/weekly")
def get_weekly():
    conn = get_db()
    from datetime import timedelta
    today = date.today()
    result = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        # 슬롯 기준 total 계산 (frequency 합산)
        drugs = conn.execute("SELECT frequency FROM prescription_drugs").fetchall()
        freq_map = {'하루 1회': 1, '하루 2회': 2, '하루 3회': 3, '하루 4회': 4}
        total = sum(freq_map.get(d['frequency'], 1) for d in drugs)        
        taken = conn.execute("""
    SELECT COUNT(*) FROM medication_logs 
    WHERE taken_date = ? AND is_taken = 1
""", (day_str,)).fetchone()[0]
        result.append({
            "date": day_str,
            "weekday": ["일", "월", "화", "수", "목", "금", "토"][(day.weekday() + 1) % 7],
            "total": total,
            "taken": taken,
            "rate": round(taken / total * 100) if total > 0 else 0
        })
    return result
@app.get("/drug-expert")
def drug_expert(name: str):
    try:
        res = requests.get(
            "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06",
            params={"serviceKey": DRUG_API_KEY, "item_name": name, "type": "json", "numOfRows": 3},
            timeout=8
        )
        data = res.json()
        items = data.get("body", {}).get("items", [])
        if not items:
            return {}
        item = items[0]

        import re

        def extract_text(doc):
            if not doc:
                return ""
            matches = re.findall(r'<!\[CDATA\[(.*?)\]\]>', doc, re.DOTALL)
            text = ' '.join(m.strip() for m in matches if m.strip())
            text = re.sub(r'&nbsp;', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text

        def parse_article(doc, *keywords):
            if not doc:
                return ""
            for kw in keywords:
                pattern = rf'<ARTICLE[^>]*title="[^"]*{re.escape(kw)}[^"]*"[^>]*>(.*?)</ARTICLE>'
                match = re.search(pattern, doc, re.DOTALL | re.IGNORECASE)
                if match:
                    cdata = re.findall(r'<!\[CDATA\[(.*?)\]\]>', match.group(1), re.DOTALL)
                    text = ' '.join(c.strip() for c in cdata if c.strip())
                    text = re.sub(r'&nbsp;', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if text:
                        return text
            return ""

        ee = item.get("EE_DOC_DATA", "") or ""
        ud = item.get("UD_DOC_DATA", "") or ""
        nb = item.get("NB_DOC_DATA", "") or ""

        material = item.get("MATERIAL_NAME", "")
        ingredient = ""
        if "성분명 : " in material:
            ingredient = material.split("성분명 : ")[1].split("|")[0].strip()

        return {
            "name": item.get("ITEM_NAME", name),
            "ingredient": ingredient,
            "efficacy": extract_text(ee),
            "usage": extract_text(ud),
            "warning": parse_article(nb, "경고"),
            "contraindication": parse_article(nb, "복용하지 말 것"),
            "caution_before": parse_article(nb, "복용하기 전에"),
            "caution_stop": parse_article(nb, "즉각 중지"),
            "caution_general": parse_article(nb, "기타"),
            "storage": parse_article(nb, "저장"),
        }
    except Exception as e:
        print(f"drug-expert error: {e}")
        return {}