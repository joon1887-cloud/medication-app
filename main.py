from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
from datetime import date, datetime, timedelta
import secrets
from database import get_db, init_db
import requests
import re

DRUG_API_KEY = "bd7deeffc64e3900eacf5d3ce065ae9fc77345e59fdd29e54692c29e8ef2713e"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_drug_cache: dict = {}

def fetch_drug_detail(name: str) -> dict:
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
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT drug_name FROM prescription_drugs")
    drugs = cur.fetchall()
    cur.close()
    conn.close()
    for row in drugs:
        name = row["drug_name"]
        if name and name not in _drug_cache:
            fetch_drug_detail(name)
    print(f"[캐시] {len(_drug_cache)}개 약 사전 로드 완료")


def fill_missing_ingredients():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, drug_name FROM prescription_drugs WHERE ingredient IS NULL OR ingredient = ''")
    rows = cur.fetchall()
    if not rows:
        cur.close()
        conn.close()
        print("[성분명] 채울 항목 없음")
        return
    print(f"[성분명] {len(rows)}개 약 성분명 자동 채우기 시작...")
    updated = 0
    for row in rows:
        detail = fetch_drug_detail(row["drug_name"])
        ingredient = detail.get("ingredient", "")
        if ingredient:
            cur.execute("UPDATE prescription_drugs SET ingredient = %s WHERE id = %s", (ingredient, row["id"]))
            updated += 1
    conn.commit()
    cur.close()
    conn.close()
    print(f"[성분명] {updated}개 업데이트 완료")


init_db()
preload_drug_cache()
fill_missing_ingredients()


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


@app.get("/")
def home(request: Request):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM prescriptions")
    prescriptions = cur.fetchall()
    result = []
    for p in prescriptions:
        cur.execute("SELECT * FROM prescription_drugs WHERE prescription_id = %s", (p["id"],))
        drugs = cur.fetchall()
        result.append({
            "id": p["id"],
            "hospital": p["hospital"],
            "visit_date": p["visit_date"],
            "drugs": [dict(drug) for drug in drugs]
        })
    cur.close()
    conn.close()
    return templates.TemplateResponse(request, "index.html", {"prescriptions": result})


@app.post("/add")
def add_prescription(data: AddPrescription):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO prescriptions (hospital, visit_date) VALUES (%s, %s) RETURNING id",
        (data.hospital, data.visit_date)
    )
    prescription_id = cur.fetchone()["id"]
    for drug in data.drugs:
        ingredient = drug.ingredient
        if not ingredient:
            detail = fetch_drug_detail(drug.drug_name)
            ingredient = detail.get("ingredient", "")
        cur.execute(
            "INSERT INTO prescription_drugs (prescription_id, drug_name, ingredient, days, dosage, frequency, times, meal_timing, refill_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (prescription_id, drug.drug_name, ingredient, drug.days, drug.dosage, drug.frequency, drug.times, drug.meal_timing, drug.refill_date)
        )
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


@app.delete("/delete/{prescription_id}")
def delete_prescription(prescription_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM prescription_drugs WHERE prescription_id = %s", (prescription_id,))
    drug_ids = [row["id"] for row in cur.fetchall()]
    for drug_id in drug_ids:
        cur.execute("DELETE FROM medication_logs WHERE drug_id = %s", (drug_id,))
    cur.execute("DELETE FROM prescription_drugs WHERE prescription_id = %s", (prescription_id,))
    cur.execute("DELETE FROM prescriptions WHERE id = %s", (prescription_id,))
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


@app.put("/update/{prescription_id}")
def update_prescription(prescription_id: int, data: AddPrescription):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE prescriptions SET hospital = %s, visit_date = %s WHERE id = %s",
        (data.hospital, data.visit_date, prescription_id)
    )
    cur.execute("SELECT id FROM prescription_drugs WHERE prescription_id = %s", (prescription_id,))
    drug_ids = [row["id"] for row in cur.fetchall()]
    for drug_id in drug_ids:
        cur.execute("DELETE FROM medication_logs WHERE drug_id = %s", (drug_id,))
    cur.execute("DELETE FROM prescription_drugs WHERE prescription_id = %s", (prescription_id,))
    for drug in data.drugs:
        ingredient = drug.ingredient
        if not ingredient:
            detail = fetch_drug_detail(drug.drug_name)
            ingredient = detail.get("ingredient", "")
        cur.execute(
            "INSERT INTO prescription_drugs (prescription_id, drug_name, ingredient, days, dosage, frequency, times, meal_timing, refill_date) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (prescription_id, drug.drug_name, ingredient, drug.days, drug.dosage, drug.frequency, drug.times, drug.meal_timing, drug.refill_date)
        )
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


@app.get("/today")
def get_today_drugs():
    conn = get_db()
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute("""
        SELECT pd.*, p.hospital
        FROM prescription_drugs pd
        JOIN prescriptions p ON pd.prescription_id = p.id
    """)
    drugs = cur.fetchall()

    def parse_slots(times_str, frequency):
        times_list = [t.strip() for t in times_str.split('·') if t.strip()]
        if not times_list:
            times_list = ['아침']
        return times_list

    result = []
    for drug in drugs:
        drug_dict = dict(drug)
        slots = parse_slots(drug_dict['times'], drug_dict['frequency'])
        for slot in slots:
            cur.execute(
                "SELECT * FROM medication_logs WHERE drug_id = %s AND taken_date = %s AND time_slot = %s",
                (drug_dict['id'], today, slot)
            )
            log = cur.fetchone()
            result.append({
                **drug_dict,
                'slot': slot,
                'is_taken': log['is_taken'] if log else 0,
                'log_id': log['id'] if log else None,
            })
    cur.close()
    conn.close()
    return result


@app.post("/check/{drug_id}")
def toggle_check(drug_id: int, slot: str = ""):
    conn = get_db()
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute(
        "SELECT * FROM medication_logs WHERE drug_id = %s AND taken_date = %s AND time_slot = %s",
        (drug_id, today, slot)
    )
    existing = cur.fetchone()
    if existing:
        new_status = 0 if existing["is_taken"] else 1
        cur.execute("UPDATE medication_logs SET is_taken = %s WHERE id = %s", (new_status, existing["id"]))
    else:
        cur.execute(
            "INSERT INTO medication_logs (drug_id, taken_date, time_slot, is_taken) VALUES (%s, %s, %s, 1)",
            (drug_id, today, slot)
        )
    conn.commit()
    cur.close()
    conn.close()
    return {"ok": True}


@app.post("/share/{prescription_id}")
def create_share_link(prescription_id: int):
    conn = get_db()
    cur = conn.cursor()
    token = secrets.token_urlsafe(8)
    cur.execute(
        "INSERT INTO share_links (token, prescription_id, created_at) VALUES (%s, %s, %s)",
        (token, prescription_id, datetime.now().isoformat())
    )
    conn.commit()
    cur.close()
    conn.close()
    return {"token": token}


@app.get("/shared/{token}")
def view_shared(token: str, request: Request):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM share_links WHERE token = %s", (token,))
    link = cur.fetchone()
    if not link:
        return {"error": "유효하지 않은 링크입니다"}
    cur.execute("SELECT * FROM prescriptions WHERE id = %s", (link["prescription_id"],))
    prescription = cur.fetchone()
    cur.execute("SELECT * FROM prescription_drugs WHERE prescription_id = %s", (link["prescription_id"],))
    drugs = cur.fetchall()
    drugs_with_logs = []
    for drug in drugs:
        cur.execute("SELECT * FROM medication_logs WHERE drug_id = %s ORDER BY taken_date DESC", (drug["id"],))
        logs = cur.fetchall()
        drug_dict = dict(drug)
        drug_dict["logs"] = [dict(log) for log in logs]
        drug_dict["taken_count"] = sum(1 for log in logs if log["is_taken"])
        drug_dict["total_logs"] = len(logs)
        drugs_with_logs.append(drug_dict)
    cur.close()
    conn.close()
    return templates.TemplateResponse(request, "shared.html", {
        "hospital": prescription["hospital"],
        "visit_date": prescription["visit_date"],
        "drugs": drugs_with_logs
    })


@app.get("/search-drug")
def search_drug(name: str, detail: bool = False):
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
                    _drug_cache[drug_name] = {"ingredient": ingredient, "efficacy": efficacy, "usage": usage}
            results.append({"name": drug_name, "efficacy": efficacy, "usage": usage, "ingredient": ingredient})
    except Exception:
        pass
    return results


@app.get("/drug-info")
def drug_info(name: str):
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
            caution = item.get("atpnQesitm", "")
            side_effect = item.get("seQesitm", "")
            interaction = item.get("intrcQesitm", "")
            storage = item.get("depositMethodQesitm", "")
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
                "name": drug_name, "ingredient": ingredient, "efficacy": efficacy,
                "usage": usage, "caution": caution, "side_effect": side_effect,
                "interaction": interaction, "storage": storage,
            })
    except Exception:
        pass
    return results


@app.get("/weekly")
def get_weekly():
    conn = get_db()
    cur = conn.cursor()
    today = date.today()
    result = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.isoformat()
        cur.execute("SELECT frequency FROM prescription_drugs")
        drugs = cur.fetchall()
        freq_map = {'하루 1회': 1, '하루 2회': 2, '하루 3회': 3, '하루 4회': 4}
        total = sum(freq_map.get(d['frequency'], 1) for d in drugs)
        cur.execute("SELECT COUNT(*) as cnt FROM medication_logs WHERE taken_date = %s AND is_taken = 1", (day_str,))
        taken = cur.fetchone()["cnt"]
        result.append({
            "date": day_str,
            "weekday": ["일", "월", "화", "수", "목", "금", "토"][(day.weekday() + 1) % 7],
            "total": total,
            "taken": taken,
            "rate": round(taken / total * 100) if total > 0 else 0
        })
    cur.close()
    conn.close()
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
