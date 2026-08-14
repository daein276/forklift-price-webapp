from datetime import datetime

import streamlit as st

import sheets
from auth import require_login, current_user, require_upload_permission
from parser import parse_uploaded_file, rows_to_dataframe

st.set_page_config(page_title="업로드", page_icon="📤", layout="wide")
require_login()
require_upload_permission()
user = current_user()

st.title("📤 리스트 업로드")

if user["is_admin"]:
    existing = sheets.load_data()
    known_companies = sorted(existing["업체명"].dropna().unique().tolist()) if not existing.empty else []
    pick_options = known_companies + ["+ 새 업체명 입력"]
    picked = st.selectbox("이 파일은 어느 업체 것인가요?", pick_options,
                           index=pick_options.index(user["company"]) if user["company"] in pick_options else len(pick_options) - 1)
    if picked == "+ 새 업체명 입력":
        upload_company = st.text_input("업체명 직접 입력", value=user["company"])
    else:
        upload_company = picked
    st.caption("관리자는 어느 업체 파일이든 대신 올릴 수 있어서, 업체명을 직접 선택/입력합니다.")
else:
    upload_company = user["company"]
    st.write(f"업체명: **{upload_company}** (자동으로 이 업체명이 붙습니다)")

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
            rows, checks = parse_uploaded_file(f.name, f.getvalue(), upload_company, upload_time)
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

    replace_existing = st.checkbox(
        f"'{upload_company}' 업체의 기존 목록은 지우고 이번 파일로 교체",
        value=True,
        help="매달 새 리스트를 받을 때 체크해두면, 이 업체의 예전 목록은 삭제되고 이번에 올린 내용으로만 남습니다. "
             "기존 목록에 새 내용을 추가만 하고 싶으면 체크 해제하세요.",
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("전체 협력업체와 공유하기", type="primary", disabled=df.empty and not checks):
            if not df.empty:
                if replace_existing:
                    sheets.replace_company_rows(upload_company, df)
                else:
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
