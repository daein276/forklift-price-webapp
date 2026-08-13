"""
중고지게차 시세표(PDF/엑셀) 파싱 로직.
기존 데스크톱 프로그램(main.py)의 검증된 로직을 그대로 이식했다.
차이점: 업체명은 파일명 추정이 아니라 "로그인한 업체 계정"을 그대로 사용한다.
"""
import io
import os
import re
from datetime import datetime

import pandas as pd
import pdfplumber

STANDARD_COLUMNS = [
    "업체명", "브랜드", "모델", "원본모델", "시리얼",
    "장비종류", "톤수", "마스트", "마스트종류", "마스트높이",
    "장비년식", "배터리년식", "배터리용량", "가동시간",
    "금액", "금액구분", "상태", "비고", "파일명", "원문", "인식상태",
    "업로드일시",
]

BRAND_MAP = {
    "NYK": "NICHIYU", "NICHIYU": "NICHIYU", "NICHYU": "NICHIYU",
    "니찌유": "NICHIYU", "니치유": "NICHIYU", "닛유": "NICHIYU",
    "TOYOTA": "TOYOTA", "토요타": "TOYOTA",
    "SUMITOMO": "SUMITOMO", "스미토모": "SUMITOMO",
    "UNICARRIERS": "UNICARRIERS", "유니케리어": "UNICARRIERS",
    "NISSAN": "NISSAN", "TCM": "TCM",
    "KOMATSU": "KOMATSU", "코마츠": "KOMATSU",
    "BT": "BT", "RAYMOND": "RAYMOND",
    "DOOSAN": "DOOSAN", "두산": "DOOSAN",
    "HYUNDAI": "HYUNDAI", "현대": "HYUNDAI",
    "수성": "SUSUNG", "SUGIKUNI": "SUGIKUNI",
}
BRAND_KEYS = sorted(BRAND_MAP.keys(), key=len, reverse=True)


def to_number(value):
    if value is None:
        return None
    s = str(value).replace(",", "").replace("₩", "").replace("원", "").strip()
    s = s.replace("年", "").replace("년", "")
    if s in ["", "-", "?", "None", "nan"]:
        return None
    try:
        return float(s)
    except Exception:
        return None


def to_int(value):
    n = to_number(value)
    if n is None:
        return None
    return int(n)


def normalize_year(value):
    if value is None:
        return None
    text = str(value)
    m = re.search(r"(19\d{2}|20\d{2})", text)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d{2})", text)
    if m2:
        y = int(m2.group(1))
        return 2000 + y if y < 80 else 1900 + y
    return None


def normalize_brand(value):
    if value is None:
        return None
    raw = str(value).strip()
    up = raw.upper()
    if raw in BRAND_MAP:
        return BRAND_MAP[raw]
    if up in BRAND_MAP:
        return BRAND_MAP[up]
    for key in BRAND_KEYS:
        if key.upper() in up or key in raw:
            return BRAND_MAP[key]
    return up


def find_brand_index(tokens):
    valid = set(BRAND_MAP.values())
    for i, tok in enumerate(tokens):
        if normalize_brand(tok) in valid:
            return i
    return None


def parse_price(line):
    nums = re.findall(r"(?:₩\s*)?\d{1,3}(?:,\d{3})+(?:원)?", str(line))
    if not nums:
        return None
    return to_int(nums[-1])


def normalize_price_by_company(price, company, line):
    if price is None:
        return None
    if "디피엘" in str(company) and price < 100000:
        return price * 1000
    if price < 100000:
        return price * 1000
    return price


def extract_battery(text):
    t = str(text)
    cap = None
    byear = None
    m_cap = re.search(r"(\d{2,4})\s*AH", t, re.I)
    if m_cap:
        cap = int(m_cap.group(1))
    m_year1 = re.search(r"AH\s*\((\d{2})\)", t, re.I)
    if m_year1:
        byear = normalize_year(m_year1.group(1))
    m_year2 = re.search(r"(\d{2})\s*년\s*\d{2,4}\s*AH", t, re.I)
    if m_year2:
        byear = normalize_year(m_year2.group(1))
    return byear, cap


def extract_ton(model, explicit=None):
    if explicit is not None:
        n = to_number(explicit)
        if n:
            return round(n, 1)
    t = str(model).upper()
    m = re.search(r"(?:FB|FBR|FBRM|FBRMW|FBRMAW|FBRMA|FBRW|FBT|RB|RBC|BR|PLD|LPE|LWE|FD)[A-Z]*[-]?\D*(\d{1,2})", t)
    if m:
        v = int(m.group(1))
        if 5 <= v <= 35:
            return round(v / 10, 1)
    for v in [35, 30, 25, 20, 18, 16, 15, 14, 13, 12, 10, 9, 7, 5]:
        if str(v) in t:
            return round(v / 10, 1)
    return None


def extract_type(model, type_token=None, line=""):
    tt = str(type_token or "").upper()
    raw = str(type_token or "")
    m = str(model).upper()
    l = str(line).upper()
    if tt == "R" or "입승" in raw or "입승" in line:
        return "리치"
    if tt == "C" or "좌승" in raw or "좌승" in line:
        return "좌식"
    if any(x in m for x in ["LPE", "LWE", "PLD"]):
        return "전동파렛트"
    if any(x in m for x in ["FBR", "RB", "RBC", "FRB", "BR"]):
        return "리치"
    if any(x in m for x in ["FB", "FD"]):
        return "좌식"
    if "STACKER" in l:
        return "스태커"
    return "기타"


def clean_model(model):
    if model is None:
        return None
    t = str(model).upper().strip()
    t = re.sub(r"[-_]\d{3,}.*", "", t)
    return t


def extract_mast(text, mast_stage=None, mast_height=None):
    t = str(text).upper()
    if mast_stage is not None and mast_height is not None:
        st = str(mast_stage).strip()
        h = to_number(mast_height)
        if h and 1 <= h <= 15:
            height = int(h * 1000)
            mast_type = f"{st}단" if st in ["2", "3"] else "기타"
            return f"{mast_type} {h}M", mast_type, height
    m = re.search(r"(3단|2단|FF3)\s*(\d+(?:\.\d+)?)\s*M", t)
    if m:
        h = float(m.group(2))
        if 1 <= h <= 15:
            mast_type = "3단" if "3" in m.group(1) else "2단"
            return m.group(0).strip(), mast_type, int(h * 1000)
    m2 = re.search(r"\b(\d+(?:\.\d+)?)\s*M\b", t)
    if m2:
        h = float(m2.group(1))
        if 1 <= h <= 15:
            mast_type = "3단" if "3단" in t or "FSV3" in t or "FF3" in t else "2단/표준"
            return f"{h:g}M", mast_type, int(h * 1000)
    m3 = re.search(r"\b(\d+(?:\.\d+)?)\s+(FSV3|FF3|2|3)\b", t)
    if m3:
        h = float(m3.group(1))
        if 1 <= h <= 15:
            code = m3.group(2)
            mast_type = "3단" if code in ["FSV3", "FF3", "3"] else "2단/표준"
            return f"{h:g}M {code}", mast_type, int(h * 1000)
    m4 = re.search(r"(FSV|FSW|FV|SV|V)(\d{3,5})", t)
    if m4:
        raw = m4.group(0)
        h = int(m4.group(2))
        if 1000 <= h <= 15000:
            mast_type = "3단" if raw.startswith(("FSV", "FSW")) else "2단/표준"
            return raw, mast_type, h
    return "", "기타", None


def split_lines_from_pdf(file_obj):
    text_all = ""
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            text_all += (page.extract_text() or "") + "\n"
    return text_all, [x.strip() for x in text_all.splitlines() if x.strip()]


def row_base(filename, company, line, upload_time):
    return {col: None for col in STANDARD_COLUMNS} | {
        "업체명": company, "금액구분": "판매가", "상태": "판매중",
        "파일명": filename, "원문": line, "인식상태": "자동",
        "업로드일시": upload_time,
    }


def remove_photo_tokens(tokens):
    return [t for t in tokens if str(t).strip() not in ["사진", "PHOTO", "이미지"]]


def parse_lotte_line(line, filename, company, upload_time):
    price = normalize_price_by_company(parse_price(line), company, line)
    if not price or not re.match(r"^\d+\s+", line):
        return None
    tokens = remove_photo_tokens(line.split())
    bidx = find_brand_index(tokens)
    if bidx is None:
        return None
    try:
        brand = normalize_brand(tokens[bidx])
        ton = to_number(tokens[bidx + 1])
        year = normalize_year(tokens[bidx + 2])
        model = tokens[bidx + 3]
        serial = tokens[bidx + 4]
        mast_stage = tokens[bidx + 5]
        mast_height = tokens[bidx + 6]
        mast_raw, mast_type, mast_h = extract_mast(line, mast_stage, mast_height)
        byear, bcap = extract_battery(line)
        r = row_base(filename, company, line, upload_time)
        r.update({
            "브랜드": brand, "모델": clean_model(model), "원본모델": model, "시리얼": serial,
            "장비종류": extract_type(model, tokens[bidx - 1] if bidx >= 1 else None, line),
            "톤수": ton, "마스트": mast_raw, "마스트종류": mast_type, "마스트높이": mast_h,
            "장비년식": year, "배터리년식": byear, "배터리용량": bcap,
            "가동시간": None, "금액": price, "비고": " ".join(tokens[bidx + 7:-1]),
        })
        return r
    except Exception:
        return None


def parse_generic_brand_line(line, filename, company, upload_time):
    price = normalize_price_by_company(parse_price(line), company, line)
    if not price or not re.match(r"^\d+\s+", line):
        return None
    tokens = remove_photo_tokens(line.replace("￾", "-").replace("\t", " ").split())
    bidx = find_brand_index(tokens)
    if bidx is None:
        return None
    try:
        brand = normalize_brand(tokens[bidx])
        model = tokens[bidx + 1]
        serial = tokens[bidx + 2] if bidx + 2 < len(tokens) else None
        type_token = None
        start = bidx + 3
        if start < len(tokens) and tokens[start].upper() in ["C", "R"]:
            type_token = tokens[start]
            start += 1
        year = None
        year_idx = None
        for i in range(start, min(len(tokens), start + 7)):
            y = normalize_year(tokens[i])
            if y and 1980 <= y <= datetime.now().year + 1:
                year = y
                year_idx = i
                break
        hour = None
        possible_hours = []
        if year_idx is not None:
            for j in range(year_idx + 1, min(len(tokens), year_idx + 10)):
                n = to_int(tokens[j])
                if n is not None and 0 <= n <= 200000 and n not in [2, 3, 4, 5, 6, 7]:
                    possible_hours.append(n)
        if possible_hours:
            bigs = [x for x in possible_hours if x >= 100]
            hour = bigs[-1] if bigs else possible_hours[-1]
        byear, bcap = extract_battery(line)
        mast_raw, mast_type, mast_h = extract_mast(line)
        r = row_base(filename, company, line, upload_time)
        r.update({
            "브랜드": brand, "모델": clean_model(model), "원본모델": model, "시리얼": serial,
            "장비종류": extract_type(model, type_token, line), "톤수": extract_ton(model),
            "마스트": mast_raw, "마스트종류": mast_type, "마스트높이": mast_h,
            "장비년식": year, "배터리년식": byear, "배터리용량": bcap,
            "가동시간": hour, "금액": price, "비고": line,
        })
        return r
    except Exception:
        return None


def parse_pdf_bytes(file_bytes, filename, company, upload_time):
    """PDF 파일(bytes)을 표준 행 목록으로 변환. company는 로그인한 업체명."""
    text, lines = split_lines_from_pdf(io.BytesIO(file_bytes))
    rows, checks = [], []
    for line in lines:
        if not re.match(r"^\d+\s+", line):
            continue
        parsed = parse_lotte_line(line, filename, company, upload_time) if "롯데" in company else None
        if parsed is None:
            parsed = parse_generic_brand_line(line, filename, company, upload_time)
        if parsed:
            rows.append(parsed)
        elif parse_price(line):
            checks.append({"업체명": company, "파일명": filename, "원문": line,
                            "사유": "가격은 있으나 표준 항목 자동 추출 실패", "업로드일시": upload_time})
    return rows, checks


def parse_excel_bytes(file_bytes, filename, company, upload_time):
    """엑셀/CSV 파일(bytes)을 표준 행 목록으로 변환. company는 로그인한 업체명."""
    rows, checks = [], []
    try:
        buf = io.BytesIO(file_bytes)
        df = pd.read_csv(buf) if filename.lower().endswith(".csv") else pd.read_excel(buf)
    except Exception:
        checks.append({"업체명": company, "파일명": filename, "원문": "",
                        "사유": "엑셀 읽기 실패", "업로드일시": upload_time})
        return rows, checks
    for _, rec in df.iterrows():
        text = " ".join([str(x) for x in rec.values if pd.notna(x)])
        if not text.strip():
            continue
        parsed = parse_generic_brand_line("1 " + text, filename, company, upload_time)
        if parsed:
            rows.append(parsed)
        else:
            checks.append({"업체명": company, "파일명": filename, "원문": text,
                            "사유": "엑셀 행 자동 추출 실패", "업로드일시": upload_time})
    return rows, checks


def parse_uploaded_file(filename, file_bytes, company, upload_time=None):
    """업로드된 파일 하나를 파싱. 확장자에 따라 PDF/엑셀 처리기로 분기."""
    upload_time = upload_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lower = filename.lower()
    if lower.endswith(".pdf"):
        rows, checks = parse_pdf_bytes(file_bytes, filename, company, upload_time)
    elif lower.endswith((".xlsx", ".xls", ".csv")):
        rows, checks = parse_excel_bytes(file_bytes, filename, company, upload_time)
    else:
        raise ValueError("지원하지 않는 파일 형식입니다 (PDF, XLSX, XLS, CSV만 가능)")
    return rows, checks


def rows_to_dataframe(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)
    for col in STANDARD_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[STANDARD_COLUMNS]
    for col in ["톤수", "마스트높이", "장비년식", "배터리년식", "배터리용량", "가동시간", "금액"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["브랜드"] = df["브랜드"].apply(normalize_brand)
    return df
