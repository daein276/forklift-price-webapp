import streamlit as st

from auth import require_login, current_user

st.set_page_config(page_title="대인리프트 중고지게차 시세 공유", page_icon="🚜", layout="wide")

require_login()
user = current_user()

st.title("🚜 대인리프트 중고지게차 시세 공유 시스템")
st.write(f"환영합니다, **{user['company']}** 님.")

st.markdown("왼쪽 메뉴에서 원하는 기능을 선택하세요.")
if user.get("can_upload", True):
    st.markdown(
        "- **업로드** : 우리 회사 중고지게차 리스트(PDF/엑셀)를 올리면 자동으로 표준 형식으로 정리되어 "
        "전체 협력업체와 공유됩니다."
    )
st.markdown("- **시세검색** : 모든 협력업체가 올린 통합 시세를 브랜드/톤수/년식/가격 등으로 검색합니다.")
if user["is_admin"]:
    st.markdown("- **관리자** : 확인필요 항목 검토, 판매완료 처리, 데이터 수정/삭제 (관리자 전용)")
