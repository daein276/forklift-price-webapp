import pandas as pd
import streamlit as st

import sheets
from auth import require_login, current_user
from parser import mask_company_name

st.set_page_config(page_title="시세검색", page_icon="🔎", layout="wide")
require_login()
user = current_user()

st.title("🔎 통합 시세 검색")

df = sheets.load_data()

if df.empty:
    st.info("아직 업로드된 데이터가 없습니다. '업로드' 메뉴에서 리스트를 올려주세요.")
    st.stop()

show_real_company = user["is_admin"]

def options(col):
    if col not in df.columns:
        return ["전체"]
    vals = sorted([v for v in df[col].dropna().unique().tolist() if str(v).strip() != ""])
    return ["전체"] + vals

def company_options():
    names = df["업체명"].dropna().unique().tolist()
    if show_real_company:
        return ["전체"] + sorted(names)
    return ["전체"] + sorted({mask_company_name(n) for n in names})

c1, c2, c3, c4, c5 = st.columns(5)
company = c1.selectbox("업체", company_options())
brand = c2.selectbox("브랜드", options("브랜드"))
kind = c3.selectbox("장비종류", options("장비종류"))
ton = c4.selectbox("톤수", options("톤수"))
year = c5.selectbox("년식", options("장비년식"))

c6, c7, c8 = st.columns(3)
price_man = c6.text_input("금액(만원, 예: 1500)")
model_query = c7.text_input("모델검색")
status = c8.selectbox("상태", ["판매중", "판매완료", "전체"])

result = df.copy()
if company != "전체":
    if show_real_company:
        result = result[result["업체명"] == company]
    else:
        result = result[result["업체명"].apply(mask_company_name) == company]
if brand != "전체":
    result = result[result["브랜드"] == brand]
if kind != "전체":
    result = result[result["장비종류"] == kind]
if ton != "전체":
    result = result[result["톤수"] == float(ton)]
if year != "전체":
    y = int(float(year))
    result = result[(result["장비년식"] >= y - 2) & (result["장비년식"] <= y + 2)]
if price_man.strip():
    try:
        p = int(price_man.strip()) * 10000
        result = result[(result["금액"] >= p - 1_000_000) & (result["금액"] <= p + 1_000_000)]
    except ValueError:
        st.warning("금액은 숫자로 입력해주세요.")
if model_query.strip():
    s = model_query.strip().upper()
    result = result[result["원본모델"].astype(str).str.upper().str.contains(s, na=False)]
if status != "전체":
    result = result[result["상태"] == status]

if result.empty:
    st.warning("조건에 맞는 데이터가 없습니다.")
else:
    st.markdown(
        f"**검색 {len(result)}대** | 평균가 {result['금액'].mean():,.0f}원 | "
        f"중간값 {result['금액'].median():,.0f}원 | 최저 {result['금액'].min():,.0f}원 | "
        f"최고 {result['금액'].max():,.0f}원 | 평균년식 {result['장비년식'].mean():.1f}년 | "
        f"평균배터리 {result['배터리년식'].mean():.1f}년 | 평균시간 {result['가동시간'].mean():,.0f}h"
    )
    show_cols = ["업체명", "브랜드", "모델", "원본모델", "시리얼", "장비종류", "톤수", "마스트",
                 "마스트종류", "마스트높이", "장비년식", "배터리년식", "배터리용량", "가동시간",
                 "금액", "상태", "비고", "파일명", "업로드일시"]
    result = result.sort_values("금액", na_position="last")
    display = result[show_cols].copy()
    if not show_real_company:
        display["업체명"] = display["업체명"].apply(mask_company_name)
    st.dataframe(display, use_container_width=True, height=550)
