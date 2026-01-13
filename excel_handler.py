
import pandas as pd
import io
from datetime import datetime
from openpyxl.utils import get_column_letter

def create_excel_with_tabs(processed_data):
    """
    처리된 데이터를 받아 일별/주별/월별 탭이 있는 엑셀 파일을 생성합니다.
    processed_data: list of dict (이미 평탄화된 데이터)
    """
    df = pd.DataFrame(processed_data)
    
    # 날짜 형식 변환
    if '일자' in df.columns:
        df['일자'] = pd.to_datetime(df['일자'], errors='coerce')
    
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 1. 전체 데이터 (Raw Data)
        if not df.empty:
            df['일자_str'] = df['일자'].dt.strftime('%Y-%m-%d') # 엑셀 출력을 위한 문자열
            # 출력 컬럼 순서 정리 (사용자 요청: 품목명과 규격 통합)
            cols = ['일자_str', '거래처명', '품목명(규격)', '수량', '수화주', '전화번호', '주소지', '지불유형', '비고']
            # 존재하는 컬럼만 선택
            final_cols = [c for c in cols if c in df.columns]
            
            # 전체 시트
            df[final_cols].to_excel(writer, sheet_name='전체내역', index=False)
            
            # 2. 월별 시트 (예: 2024-05)
            # '일자' 기준 그룹화
            if '일자' in df.columns and not df['일자'].isna().all():
                df['month'] = df['일자'].dt.strftime('%Y-%m')
                for month, group in df.groupby('month'):
                    sheet_name = f"{month}월"
                    group[final_cols].to_excel(writer, sheet_name=sheet_name, index=False)
        
        # [자동 열 너비 조정]
        # 모든 시트를 순회하며 각 열의 너비를 내용에 맞게 조정
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column_cells in worksheet.columns:
                max_length = 0
                if not column_cells:
                    continue
                column = column_cells[0].column_letter # Get the column name
                
                for cell in column_cells:
                    try:
                        if cell.value:
                            # CP949 인코딩 길이 사용 (한글 2바이트, 영문 1바이트)
                            # 엑셀의 열 너비는 바이트 수와 유사하게 작동하므로 더 정확함
                            length = len(str(cell.value).encode('cp949'))
                            if length > max_length:
                                max_length = length
                    except:
                        pass
                
                # 최소 10, 최대 100으로 제한 (여유값 2 추가 및 1.1배)
                adjusted_width = min(max((max_length + 2) * 1.1, 10), 100)
                worksheet.column_dimensions[column].width = adjusted_width

    output.seek(0)
    return output

def flatten_json_to_rows(parsed_json, filename):
    """
    LLM에서 받은 JSON 구조(품목 리스트 포함)를 엑셀 행 단위로 평탄화합니다.
    """
    rows = []
    
    # 기본 정보
    base_info = {
        "일자": parsed_json.get("order_date", ""),
        "거래처명": parsed_json.get("client_name", ""),
        "전화번호": parsed_json.get("phone_number", ""),
        "주소지": parsed_json.get("address", ""),
        "수화주": parsed_json.get("consignee", ""),
        "지불유형": parsed_json.get("payment_type", ""),
        "비고": parsed_json.get("remarks", ""),
        "파일명": filename
    }
    
    items = parsed_json.get("items", [])
    if not items:
        # 품목이 없어도 기본 정보는 한 줄로 추가
        rows.append(base_info)
    else:
        for item in items:
            row = base_info.copy()
            
            # 품목명과 규격 합치기 로직
            item_name = item.get("item_name", "")
            spec = item.get("spec", "")
            
            if spec:
                combined_name = f"{item_name}[{spec}]"
            else:
                combined_name = item_name
                
            row["품목명(규격)"] = combined_name
            row["수량"] = item.get("qty", 0)
            rows.append(row)
            
    return rows
