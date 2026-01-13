import pandas as pd
import os
from datetime import datetime
import streamlit as st
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    HAS_GSHEETS_LIB = True
except ImportError:
    HAS_GSHEETS_LIB = False

# 데이터베이스 파일 경로 (로컬 백업/Fallback용)
DB_FILE = "po_database.csv"

# 구글 시트 설정 (Secrets에서 가져오기)
# st.secrets["gcp_service_account"] 안에 JSON 키 내용이 들어있어야 함
try:
    SHEET_URL = st.secrets.get("private_gsheets_url", "") # 공유받은 시트 URL (선택사항)
except:
    SHEET_URL = ""

def get_google_sheet_client():
    """
    Google Sheets 클라이언트를 인증하고 반환합니다.
    Secrets 설정이 없거나 인증 실패 시 None을 반환합니다.
    """
    if not HAS_GSHEETS_LIB:
        return None

    try:
        # Streamlit Cloud의 secrets 관리 기능을 사용
        if "gcp_service_account" in st.secrets:
            # secrets 값을 dict로 변환
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["gcp_service_account"]), scope)
            client = gspread.authorize(creds)
            return client
    except Exception as e:
        # print(f"Google Sheet Auth Error: {e}") # 로그 과다 방지
        pass
    return None

def get_sheet_instance(client):
    """
    작업할 워크시트를 가져옵니다.
    없으면 생성합니다.
    """
    try:
        # 1. URL로 열기 (설정된 경우)
        if SHEET_URL:
            sh = client.open_by_url(SHEET_URL)
        else:
            # 2. 이름으로 열기 (기본값: 'Smart_PO_DB')
            try:
                sh = client.open("Smart_PO_DB")
            except:
                sh = client.create("Smart_PO_DB")
                # 최초 생성 시 헤더 추가
                try:
                    sh.share(st.secrets["admin_email"], perm_type='user', role='writer')
                except:
                    pass
        
        # 첫 번째 시트 사용
        worksheet = sh.get_worksheet(0)
        return worksheet
    except Exception as e:
        # print(f"Sheet Open Error: {e}")
        return None

def load_database():
    """
    데이터베이스를 불러옵니다.
    1순위: Google Sheets
    2순위: 로컬 CSV (Fallback)
    """
    # 1. Google Sheets 시도
    client = get_google_sheet_client()
    if client:
        worksheet = get_sheet_instance(client)
        if worksheet:
            try:
                data = worksheet.get_all_records()
                df = pd.DataFrame(data)
                
                # 날짜 컬럼 형변환
                if '일자' in df.columns:
                    df['일자'] = pd.to_datetime(df['일자'], errors='coerce')
                if '등록일시' in df.columns:
                    df['등록일시'] = pd.to_datetime(df['등록일시'], errors='coerce')
                
                return df
            except Exception as e:
                pass

    # 2. 로컬 CSV (Fallback)
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(DB_FILE)
        if '일자' in df.columns:
            df['일자'] = pd.to_datetime(df['일자'], errors='coerce')
        if '등록일시' in df.columns:
            df['등록일시'] = pd.to_datetime(df['등록일시'], errors='coerce')
        return df
    except Exception as e:
        return pd.DataFrame()

def append_to_database(new_data_df):
    """
    데이터를 추가합니다.
    Google Sheets와 로컬 CSV 모두에 저장을 시도합니다 (이중 백업).
    """
    if new_data_df.empty:
        return

    # 등록일시 추가
    new_data_df['등록일시'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 날짜 필드 문자열 변환 (JSON 호환성)
    if '일자' in new_data_df.columns:
        new_data_df['일자'] = new_data_df['일자'].astype(str)

    # 1. Google Sheets 저장
    client = get_google_sheet_client()
    saved_to_cloud = False
    if client:
        worksheet = get_sheet_instance(client)
        if worksheet:
            try:
                # 헤더가 없으면(빈 시트면) 헤더 추가
                if not worksheet.get_all_values():
                    worksheet.append_row(new_data_df.columns.tolist())
                
                # 데이터 추가
                values = new_data_df.values.tolist()
                worksheet.append_rows(values)
                saved_to_cloud = True
            except Exception as e:
                print(f"Cloud Save Error: {e}")

    # 2. 로컬 CSV 저장 (항상 수행)
    try:
        current_db = pd.DataFrame()
        if os.path.exists(DB_FILE):
            current_db = pd.read_csv(DB_FILE)
        
        if current_db.empty:
            updated_db = new_data_df
        else:
            updated_db = pd.concat([current_db, new_data_df], ignore_index=True)
            
        updated_db.to_csv(DB_FILE, index=False, encoding='utf-8-sig')
    except Exception as e:
        print(f"Local Save Error: {e}")

def reset_database():
    """
    데이터베이스를 초기화합니다.
    """
    # 1. Google Sheets 초기화
    client = get_google_sheet_client()
    if client:
        worksheet = get_sheet_instance(client)
        if worksheet:
            try:
                worksheet.clear()
            except:
                pass

    # 2. 로컬 CSV 초기화
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        
def get_filtered_data(start_date=None, end_date=None):
    """
    기간별 조회
    """
    df = load_database()
    if df.empty:
        return df
        
    if '일자' not in df.columns:
        return df

    # 필터링
    mask = pd.Series([True] * len(df))
    
    # df['일자']가 이미 datetime일 수도 있고 string일 수도 있음
    df['일자'] = pd.to_datetime(df['일자'], errors='coerce')
    
    if start_date:
        mask = mask & (df['일자'] >= pd.to_datetime(start_date))
    if end_date:
        mask = mask & (df['일자'] <= pd.to_datetime(end_date))
        
    return df[mask]
