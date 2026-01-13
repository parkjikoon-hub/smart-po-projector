
import streamlit as st

# --- Page Config (Must be first) ---
st.set_page_config(
    page_title="스마트 발주서 관리자",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
from pdf_parser import PRExtractor
from excel_handler import create_excel_with_tabs, flatten_json_to_rows
import data_manager
import time
from datetime import datetime
import google.generativeai as genai

# --- CONFIGURATION (TEAM SETTINGS) ---
# [팀 공유용 설정] 클라우드 배포 시 Streamlit Secrets에서 키를 가져옵니다.
# 로컬에서 테스트할 때는 .streamlit/secrets.toml 파일을 생성하여 관리하세요.
try:
    if "GOOGLE_API_KEY" in st.secrets:
        TEAM_API_KEY = st.secrets["GOOGLE_API_KEY"]
    else:
        TEAM_API_KEY = None
except:
    TEAM_API_KEY = None

# ==========================================
# 🔐 로그인 기능 (Security)
# ==========================================
def check_login():
    """로그인 성공 여부를 반환하는 함수"""
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if st.session_state.logged_in:
        return True

    # 로그인 화면 디자인
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.title("🔒 로그인")
        st.caption("관계자 전용 시스템입니다.")
        
        username = st.text_input("아이디")
        password = st.text_input("비밀번호", type="password")

        if st.button("로그인", type="primary", use_container_width=True):
            # secrets.toml 파일에 저장된 비밀번호와 대조
            if "passwords" in st.secrets:
                correct_password = st.secrets["passwords"].get(username)
                if correct_password and password == correct_password:
                    st.session_state.logged_in = True
                    st.toast("로그인 성공!", icon="✅")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
            else:
                # 비밀번호 설정이 없는 경우 (개발용 비상구)
                if password == "1234":
                     st.session_state.logged_in = True
                     st.rerun()
                else:
                    st.error("설정 파일 오류 또는 비밀번호 불일치")
        
        st.markdown("---")
        st.caption("비밀번호 분실 시 관리자에게 문의하세요.")
        
    return False

# 로그인이 안 되어 있으면 여기서 멈춤 (앱 내용 숨김)
if not check_login():
    st.stop()

# ==========================================
# 🎬 메인 앱 시작
# ==========================================

# [디버깅] 라이브러리 버전 확인
try:
    st.warning(f"🛠️ 현재 설치된 구글 라이브러리 버전: **{genai.__version__}** (권장: 0.8.0 이상)")
except:
    st.error("구글 라이브러리 버전을 확인할 수 없습니다.")

# --- Custom CSS for Premium Design & Visibility ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Pretendard', sans-serif;
        font-size: 20px !important; /* 22px -> 20px로 소폭 축소 */
        color: #E0E0E0 !important;
    }
    
    /* 헤더 스타일 */
    .main-header {
        font-size: 2.8rem !important; /* 3.8rem -> 2.8rem (부담스럽지 않게 축소) */
        font-weight: 800;
        background: linear-gradient(90deg, #6aa5ff 0%, #4b6cb7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        padding-top: 1rem;
    }
    
    .sub-header {
        font-size: 1.3rem !important; /* 1.8rem -> 1.3rem (축소) */
        color: #A0A0A0 !important;
        margin-bottom: 2.5rem;
    }
    
    /* 버튼 스타일 */
    .stButton>button {
        font-size: 1.3rem !important;
        padding: 0.8rem 2.2rem !important;
        border-radius: 12px;
        font-weight: 700;
        height: auto !important;
    }
    
    /* 파일 업로더 크기 확대 */
    div[data-testid="stFileUploader"] {
        padding: 40px 20px !important; 
        border: 3px dashed #6aa5ff !important;
        border-radius: 15px;
        background-color: rgba(255, 255, 255, 0.05);
        transition: all 0.3s ease;
    }
    
    div[data-testid="stFileUploader"] section {
        min-height: 220px !important;
        display: flex;
        align-items: center;
        justify_content: center;
    }

    div[data-testid="stFileUploader"]:hover {
        background-color: rgba(255, 255, 255, 0.1);
        border-color: #8bb8ff !important;
    }
    
    /* 데이터 에디터 (표) 스타일 */
    div[data-testid="stDataEditor"] {
        font-size: 1.15rem !important;
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 8px;
    }

    /* [User Request] 데이터프레임 툴바 버튼 확대 */
    [data-testid="stElementToolbarButton"] {
        transform: scale(1.4);
        margin: 0 6px;
    }
    
    [data-testid="stElementToolbarButton"]:hover {
        transform: scale(1.6);
        background-color: rgba(255, 255, 255, 0.2) !important;
    }
    
    /* 탭 스타일 (가독성 대폭 향상) */
    /* 탭 스타일 완전 재정의 (사각 박스 & 대형 폰트) */
    button[data-baseweb="tab"] {
        background-color: #262730 !important;
        border: 2px solid rgba(255,255,255,0.2) !important;
        border-radius: 4px !important; /* 각진 사각형 */
        margin-right: 20px !important;
        height: 70px !important;
        padding: 0 30px !important;
        transition: all 0.2s ease !important;
    }

    /* 선택된 탭 스타일 */
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #4b6cb7 !important;
        border-color: #6aa5ff !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5) !important;
    }

    /* 탭 텍스트 크기 (헤더 1:1 매칭 시도 - 30px) */
    button[data-baseweb="tab"] div[data-testid="stMarkdownContainer"] p {
        font-size: 30px !important; /* 아주 큰 폰트 적용 */
        font-weight: 800 !important;
        color: inherit !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
    }
    
    /* 탭 컨테이너 정렬 */
    div[data-baseweb="tab-list"] {
        gap: 20px !important;
        padding-bottom: 20px !important;
    }
    
    /* [데이터베이스 저장] 버튼과 같은 Secondary 버튼 강조 */
    .stButton > button[kind="secondary"] {
        font-size: 1.6rem !important;
        font-weight: 900 !important;
        border: 2px solid #ff4b4b !important; 
        color: #ff4b4b !important;
        height: 4.0rem !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: #ff4b4b !important;
        color: white !important;
    }
    
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    # 아이콘 삭제됨
    # 회사 이름 (헤더와 동일한 크기 2.8rem 적용)
    st.markdown('<div style="font-size: 2.8rem; font-weight: 800; margin-bottom: 20px; color: #ffffff;">(주)피엘에스</div>', unsafe_allow_html=True)
    st.markdown("---")
    
    if TEAM_API_KEY:
        api_key = TEAM_API_KEY
        st.success("✅ 공용 라이선스 키 적용됨")
    else:
        api_key = st.text_input("Google API Key", type="password")
    
    # [임시 프로그램용] 저장소 상태 확인
    st.markdown("---")
    st.markdown("**🛡️ 데이터 저장소 상태**")
    try:
        if data_manager.get_google_sheet_client():
             st.success("☁️ 구글 시트 연동됨 (안전)")
        else:
             st.warning("💾 로컬 저장소 사용 중")
             st.caption("주의: 앱이 재시작되면 데이터가 사라질 수 있습니다. 작업 후 반드시 엑셀을 다운로드하세요.")
    except:
        st.warning("상태 확인 불가")
    st.markdown("---")
    st.caption("Auto PLS Converter v2.0 (DB Mode)")


# --- Main Content ---
st.markdown('<div class="main-header">📑 스마트 발주서 자동화 시스템</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">데이터베이스 기능을 통해 날짜별 발주 내역을 누적 관리합니다.</div>', unsafe_allow_html=True)

if not api_key:
    # 키가 없으면 화면을 가리지 않고 경고만 띄움 (사이드바에서 확인 가능)
    st.warning("⚠️ API Key가 필요합니다. (설정 메뉴 확인)")
    st.stop()

# 메인 탭 분리
main_tab1, main_tab2 = st.tabs(["발주서 등록 & 저장", "누적 데이터 조회 & 다운로드"])

# ==========================================
# 탭 1: 발주서 등록 및 분석 (기존 기능)
# ==========================================
with main_tab1:
    st.markdown("### 📄 새로운 발주서 파일 업로드")
    
    # Session State 초기화
    if 'current_processed_data' not in st.session_state:
        st.session_state.current_processed_data = []
    
    uploaded_files = st.file_uploader("PDF 발주서를 업로드하세요", type=['pdf'], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("🚀 분석 시작", type="primary", use_container_width=True):
            st.session_state.current_processed_data = []
            extractor = PRExtractor(api_key)
            progress_bar = st.progress(0)
            status_text = st.empty()
            all_rows = []
            
            for idx, file in enumerate(uploaded_files):
                status_text.text(f"📸 이미지 스캔 및 분석 중: {file.name}...")
                try:
                    file.seek(0)
                    file_bytes = file.read()
                    parsed_json = extractor.parse_with_llm(file_bytes)
                    
                    if "error" in parsed_json:
                        st.error(f"{file.name}: {parsed_json['error']}")
                        continue
                        
                # [성공 피드백] 사용된 모델 표시 (원활한 탐색 결과 표시)
                    used_model = parsed_json.pop('_used_model', 'Unknown Model')
                    status_text.success(f"✅ 분석 완료: {file.name} (엔진: {used_model})")
                    
                    rows = flatten_json_to_rows(parsed_json, file.name)
                    all_rows.extend(rows)
                    
                except Exception as e:
                    st.error(f"오류 발생 ({file.name}): {e}")
                    
                progress_bar.progress((idx + 1) / len(uploaded_files))
                
                # [속도 복원] 지정 모델 연결로 속도 최적화
                if idx < len(uploaded_files) - 1:
                    status_text.text(f"⏳ 모델 연결 중: 5초 대기 (최적화 완료) ({idx+1}/{len(uploaded_files)})")
                    time.sleep(5)
            
            st.session_state.current_processed_data = all_rows
            status_text.success("✅ 분석 완료! 아래에서 데이터를 확인하고 저장하세요.")
    
    # 데이터 검토 및 저장
    if st.session_state.current_processed_data:
        st.markdown("---")
        st.markdown("#### 📝 분석 결과 확인 및 수정")
        st.info("데이터를 수정한 후, 반드시 **[💾 데이터베이스에 저장]** 버튼을 눌러야 누적됩니다.")
        
        df = pd.DataFrame(st.session_state.current_processed_data)
        if '일자' in df.columns:
            df['일자'] = pd.to_datetime(df['일자'], errors='coerce')

        # 엑셀 출력을 위한 컬럼 순서
        base_cols = ['일자', '거래처명', '품목명(규격)', '수량', '수화주', '전화번호', '주소지', '지불유형', '비고', '파일명']
        view_cols = [c for c in base_cols if c in df.columns]
        
        edited_df = st.data_editor(
            df[view_cols],
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="editor_new_upload",
            column_config={
                "일자": st.column_config.DateColumn("일자", format="YYYY-MM-DD", step=1),
                "수량": st.column_config.NumberColumn("수량", format="%d")
            }
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 데이터베이스에 저장 (누적)", type="secondary", use_container_width=True):
                # 데이터베이스에 Append
                data_manager.append_to_database(edited_df)
                st.success(f"✅ {len(edited_df)}건의 데이터가 성공적으로 저장되었습니다!")
                st.balloons()
                # 저장 후 세션 초기화 (옵션)
                # st.session_state.current_processed_data = [] 
                # st.rerun()

# ==========================================
# 탭 2: 누적 데이터 관리 및 조회
# ==========================================
with main_tab2:
    st.markdown("### 📊 기간별 발주 내역 조회")
    
    # 상단 컨트롤 패널: 기간 선택
    col_filter1, col_filter2, col_dummy = st.columns([1, 1, 2])
    
    with col_filter1:
        # 이번 달 1일 계산
        today = datetime.now()
        first_day = today.replace(day=1)
        start_date = st.date_input("시작일", value=first_day)
    with col_filter2:
        end_date = st.date_input("종료일", value=today)
        
    # 데이터 로드
    db_data = data_manager.get_filtered_data(start_date, end_date)
    
    if not db_data.empty:
        st.markdown(f"**검색 결과: 총 {len(db_data)}건**")
        
        # 엑셀 변환을 위해 날짜 포맷 정리, 컬럼 순서 정리
        display_df = db_data.copy()
        
        # 날짜 포맷팅 (보기 좋게)
        if '일자' in display_df.columns:
            display_df['일자'] = pd.to_datetime(display_df['일자']).dt.date
        if '등록일시' in display_df.columns:
            display_df['등록일시'] = pd.to_datetime(display_df['등록일시']).dt.strftime('%Y-%m-%d %H:%M')
            
        # 컬럼 순서 재배치
        priority_cols = ['일자', '거래처명', '품목명(규격)', '수량', '수화주', '전화번호', '주소지', '비고']
        other_cols = [c for c in display_df.columns if c not in priority_cols]
        final_cols = priority_cols + other_cols
        
        final_cols = [c for c in final_cols if c in display_df.columns]
        
        # 메인 테이블 표시
        st.dataframe(
            display_df[final_cols], 
            use_container_width=True, 
            hide_index=True,
            height=500
        )
        
        st.markdown("---")
        
        # 엑셀 다운로드 버튼
        # data_manager에서 불러온 DF를 excel_handler 형식(list of dict)으로 변환
        excel_ready_data = db_data.to_dict('records')
        excel_file = create_excel_with_tabs(excel_ready_data)
        
        col_down1, col_down2 = st.columns([1, 3])
        with col_down1:
            file_name_str = f"발주내역_누적_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
            st.download_button(
                label="📥 조회된 내역 엑셀 다운로드",
                data=excel_file,
                file_name=file_name_str,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )
            
    else:
        st.info("🔍 해당 기간에 저장된 데이터가 없습니다.")
        
    # Danger Zone
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    with st.expander("⚠️ 데이터 관리 (전체 삭제)"):
        st.warning("주의: 저장된 모든 발주 내역이 영구적으로 삭제됩니다. 이 작업은 되돌릴 수 없습니다.")
        if st.button("🗑️ 모든 데이터 초기화 (Reset Database)"):
            data_manager.reset_database()
            st.error("모든 데이터가 삭제되었습니다.")
            time.sleep(1)
            st.rerun()
