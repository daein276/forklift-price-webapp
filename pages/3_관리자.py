import pandas as pd
import streamlit as st

import sheets
from auth import require_login, require_admin
from parser import STANDARD_COLUMNS

st.set_page_config(page_title="관리자", page_icon="🛠️", layout="wide")
require_login()
require_admin()

st.title("🛠️ 관리자")

tab_check, tab_sold, tab_edit = st.tabs(["확인필요 검토", "판매완료 처리", "데이터 수정/삭제"])

with tab_check:
    st.subheader("자동 인식 실패 항목")
    checks = sheets.load_checks()
    if checks.empty:
        st.info("확인이 필요한 항목이 없습니다.")
    else:
        st.caption("직접 확인 후, 처리가 끝난 항목은 목록에서 삭제하세요.")
        for _, row in checks.iterrows():
            with st.container(border=True):
                st.write(f"**{row['업체명']}** | {row['파일명']} | {row['업로드일시']}")
                st.code(row["원문"])
                st.caption(row["사유"])
                if st.button("삭제 (처리완료)", key=f"del_check_{row['_row']}"):
                    sheets.delete_check_row(int(row["_row"]))
                    st.rerun()

with tab_sold:
    st.subheader("판매완료 처리")
    df = sheets.load_data()
    active = df[df["상태"] == "판매중"].copy()
    if active.empty:
        st.info("판매중인 항목이 없습니다.")
    else:
        active["선택"] = False
        cols = ["선택", "_row", "업체명", "브랜드", "모델", "톤수", "장비년식", "금액", "파일명"]
        edited = st.data_editor(
            active[cols],
            use_container_width=True,
            height=450,
            disabled=[c for c in cols if c != "선택"],
            hide_index=True,
            key="sold_editor",
        )
        selected_rows = edited[edited["선택"]]["_row"].tolist()
        if st.button(f"선택한 {len(selected_rows)}건 판매완료 처리", type="primary", disabled=not selected_rows):
            for r in selected_rows:
                sheets.update_cell(int(r), "상태", "판매완료")
            st.success("판매완료로 처리했습니다.")
            st.rerun()

with tab_edit:
    st.subheader("데이터 수정 / 삭제")
    df = sheets.load_data()
    if df.empty:
        st.info("데이터가 없습니다.")
    else:
        def make_label(r):
            base = f"[{int(r['_row'])}] {r['업체명']} / {r.get('브랜드', '')} {r.get('모델', '')}"
            return f"{base} / {r['금액']:,.0f}원" if pd.notna(r.get("금액")) else base

        df["_label"] = df.apply(make_label, axis=1)
        choice = st.selectbox("수정할 항목 선택", df["_label"].tolist())
        sel_row = df[df["_label"] == choice].iloc[0]

        with st.form("edit_form"):
            edits = {}
            grid = st.columns(3)
            editable_cols = [c for c in STANDARD_COLUMNS if c not in ("업로드일시", "원문", "인식상태")]
            for i, col in enumerate(editable_cols):
                with grid[i % 3]:
                    val = sel_row.get(col, "")
                    val = "" if pd.isna(val) else val
                    edits[col] = st.text_input(col, value=str(val), key=f"edit_{col}")
            save = st.form_submit_button("저장", type="primary")
        if save:
            for col, new_val in edits.items():
                old_val = sel_row.get(col, "")
                old_val = "" if pd.isna(old_val) else str(old_val)
                if new_val != old_val:
                    sheets.update_cell(int(sel_row["_row"]), col, new_val)
            st.success("저장했습니다.")
            st.rerun()

        st.divider()
        if st.button("이 항목 삭제", key="delete_row_btn"):
            sheets.delete_row(int(sel_row["_row"]))
            st.success("삭제했습니다.")
            st.rerun()
