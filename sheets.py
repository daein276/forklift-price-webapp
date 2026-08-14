"""
Google Sheets를 공유 데이터 저장소로 사용하기 위한 도우미 모듈.
시트 구조 (탭 2개):
  - "표준리스트": parser.STANDARD_COLUMNS 순서의 정상 파싱 데이터
  - "확인필요": 자동 인식 실패 원문 목록 (업체명, 파일명, 원문, 사유, 업로드일시)
필요한 비밀값은 st.secrets["gcp_service_account"], st.secrets["sheet_id"] 에서 읽는다.
"""
import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

from parser import STANDARD_COLUMNS

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

STANDARD_SHEET = "표준리스트"
CHECK_SHEET = "확인필요"
CHECK_COLUMNS = ["업체명", "파일명", "원문", "사유", "업로드일시"]


@st.cache_resource(show_spinner=False)
def _client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds)


def _spreadsheet():
    return _client().open_by_key(st.secrets["sheet_id"])


def _get_or_create_worksheet(name, columns):
    ss = _spreadsheet()
    try:
        ws = ss.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=name, rows=1000, cols=max(len(columns), 10))
        ws.append_row(columns)
    return ws


def _ensure_header(ws, columns):
    values = ws.get_all_values()
    if not values:
        ws.append_row(columns)


def _read_standard_df():
    """표준리스트 탭 전체를 캐시 없이 읽어온다 (내부용)."""
    ws = _get_or_create_worksheet(STANDARD_SHEET, STANDARD_COLUMNS)
    _ensure_header(ws, STANDARD_COLUMNS)
    records = ws.get_all_records(expected_headers=STANDARD_COLUMNS)
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=STANDARD_COLUMNS)
    else:
        for col in STANDARD_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[STANDARD_COLUMNS]
    return df


@st.cache_data(ttl=30, show_spinner=False)
def load_data(_cache_key=0):
    """표준리스트 탭 전체를 DataFrame으로 읽어온다. 시트 행 번호(2부터 시작)를 '_row'로 포함."""
    df = _read_standard_df()
    df["_row"] = range(2, len(df) + 2)
    for col in ["톤수", "마스트높이", "장비년식", "배터리년식", "배터리용량", "가동시간", "금액"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=30, show_spinner=False)
def load_checks(_cache_key=0):
    ws = _get_or_create_worksheet(CHECK_SHEET, CHECK_COLUMNS)
    _ensure_header(ws, CHECK_COLUMNS)
    records = ws.get_all_records(expected_headers=CHECK_COLUMNS)
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=CHECK_COLUMNS)
    df["_row"] = range(2, len(df) + 2)
    return df


def append_rows(df: pd.DataFrame):
    """표준리스트 탭에 새 행들을 추가하고 캐시를 비운다."""
    if df is None or df.empty:
        return
    ws = _get_or_create_worksheet(STANDARD_SHEET, STANDARD_COLUMNS)
    _ensure_header(ws, STANDARD_COLUMNS)
    values = df[STANDARD_COLUMNS].fillna("").astype(str).values.tolist()
    ws.append_rows(values, value_input_option="USER_ENTERED")
    load_data.clear()


def replace_company_rows(company: str, new_df: pd.DataFrame):
    """해당 업체의 기존 표준리스트 데이터를 전부 지우고 new_df로 교체한다 (월간 재업로드용)."""
    ws = _get_or_create_worksheet(STANDARD_SHEET, STANDARD_COLUMNS)
    existing = _read_standard_df()
    remaining = existing[existing["업체명"] != company]
    parts = [remaining]
    if new_df is not None and not new_df.empty:
        parts.append(new_df[STANDARD_COLUMNS])
    combined = pd.concat(parts, ignore_index=True) if len(parts) > 1 else remaining
    ws.clear()
    ws.append_row(STANDARD_COLUMNS)
    if not combined.empty:
        values = combined[STANDARD_COLUMNS].fillna("").astype(str).values.tolist()
        ws.append_rows(values, value_input_option="USER_ENTERED")
    load_data.clear()


def append_checks(records: list):
    if not records:
        return
    ws = _get_or_create_worksheet(CHECK_SHEET, CHECK_COLUMNS)
    _ensure_header(ws, CHECK_COLUMNS)
    values = [[str(r.get(c, "")) for c in CHECK_COLUMNS] for r in records]
    ws.append_rows(values, value_input_option="USER_ENTERED")
    load_checks.clear()


def update_cell(sheet_row: int, column: str, value):
    """표준리스트 탭의 특정 행/열 값을 수정한다 (판매완료 처리, 데이터 수정 등)."""
    ws = _get_or_create_worksheet(STANDARD_SHEET, STANDARD_COLUMNS)
    col_idx = STANDARD_COLUMNS.index(column) + 1
    ws.update_cell(sheet_row, col_idx, str(value))
    load_data.clear()


def delete_row(sheet_row: int):
    ws = _get_or_create_worksheet(STANDARD_SHEET, STANDARD_COLUMNS)
    ws.delete_rows(sheet_row)
    load_data.clear()


def delete_check_row(sheet_row: int):
    ws = _get_or_create_worksheet(CHECK_SHEET, CHECK_COLUMNS)
    ws.delete_rows(sheet_row)
    load_checks.clear()
