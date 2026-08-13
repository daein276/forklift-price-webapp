from datetime import datetime

import streamlit as st

import sheets
from auth import require_login, current_user
from parser import parse_uploaded_file, rows_to_dataframe

st.set_page_config(page_title="업로드", page_icon="📤", layout="wide")
require_login()
user = current_user()

st.title("📤 리스트 업로드")
st.write(f"업체명: **{user['company']}** (자동으로 이 업체명이 붙습니다)")

uploaded_files = st.file_uploader(
    "중고지게차 리스트 파일을 올려주세요 (PDF, XLSX, XLS, CSV / 여러 개 가능)",
    type=["pdf", "xlsx", "xls", "csv"],
    accept_multiple_files=True,
)

if "preview_rows" not in st.session_state:
    st.session_state["preview_rows"] = None
    st.session_state["preview_checks"] = None

if uploaded_files and st.button("파일 검사하기", type="primary"):
    upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_rows, all_checks = [], []
    errors = []
    for f in uploaded_files:
        try:
            rows, checks = parse_uploaded_file(f.name, f.getvalue(), user["company"], upload_time)
            all_rows.extend(rows)
            all_checks.extend(checks)
        except Exception as e:
            errors.append(f"{f.name}: {e}")
    st.session_state["preview_rows"] = all_rows
    st.session_state["preview_checks"] = all_checks
    for e in errors:
        st.error(e)

rows = st.session_state.get("preview_rows")
checks = st.session_state.get("preview_checks")

if rows is not None:
    df = rows_to_dataframe(rows)
    st.success(f"자동 인식 성공: {len(df)}건 / 확인필요: {len(checks)}건")
    if not df.empty:
        st.subheader("정상 인식된 항목 (공유 시세 목록에 추가될 내용)")
        st.dataframe(df.drop(columns=["원문", "인식상태"]), use_container_width=True, height=350)
    if checks:
        st.subheader("확인이 필요한 항목 (자동 인식 실패)")
        st.caption("가격은 보이지만 표준 항목으로 자동 정리하지 못한 줄입니다. 관리자가 나중에 검토합니다.")
        st.dataframe(checks, use_container_width=True, height=200)

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("전체 협력업체와 공유하기", type="primary", disabled=df.empty and not checks):
            if not df.empty:
                sheets.append_rows(df)
            if checks:
                sheets.append_checks(checks)
            st.session_state["preview_rows"] = None
            st.session_state["preview_checks"] = None
            st.success("업로드가 완료되었습니다. '시세검색' 메뉴에서 확인할 수 있습니다.")
            st.balloons()
    with col2:
        if st.button("취소"):
            st.session_state["preview_rows"] = None
            st.session_state["preview_checks"] = None
            st.rerun()
