"""
간단한 로그인 처리.
st.secrets["users"]에 등록된 계정(아이디/비밀번호 해시)으로만 로그인 가능.
새 업체 계정을 추가하려면 README_운영가이드.md의 안내를 따를 것.
"""
import bcrypt
import streamlit as st


def _check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def _do_login(username: str, password: str) -> bool:
    users = st.secrets.get("users", {})
    user = users.get(username)
    if not user:
        return False
    if not _check_password(password, user["password_hash"]):
        return False
    st.session_state["user"] = {
        "username": username,
        "company": user.get("display_name", username),
        "is_admin": bool(user.get("is_admin", False)),
        "can_upload": bool(user.get("can_upload", True)),
    }
    return True


def login_form():
    st.title("대인리프트 중고지게차 시세 공유")
    st.caption("협력업체 전용 시스템입니다. 발급받은 아이디/비밀번호로 로그인해주세요.")
    with st.form("login_form"):
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")
    if submitted:
        if _do_login(username, password):
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")


def current_user():
    return st.session_state.get("user")


def logout_button():
    user = current_user()
    if not user:
        return
    with st.sidebar:
        st.write(f"**{user['company']}** 님으로 로그인됨" + (" (관리자)" if user["is_admin"] else ""))
        if st.button("로그아웃"):
            del st.session_state["user"]
            st.rerun()


def require_login():
    """로그인 안 되어 있으면 로그인 폼을 보여주고 실행을 멈춘다."""
    if not current_user():
        login_form()
        st.stop()
    logout_button()


def require_admin():
    """관리자가 아니면 접근을 막는다. require_login() 이후에 호출할 것."""
    user = current_user()
    if not user or not user["is_admin"]:
        st.error("관리자만 접근할 수 있는 페이지입니다.")
        st.stop()


def require_upload_permission():
    """업로드 권한이 없는 계정(구경/검색 전용)은 접근을 막는다. require_login() 이후에 호출할 것."""
    user = current_user()
    if not user or not user.get("can_upload", True):
        st.error("이 계정은 시세검색만 가능합니다. 업로드 권한이 필요하면 관리자에게 문의해주세요.")
        st.stop()
