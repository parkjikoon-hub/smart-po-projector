
import fitz  # PyMuPDF
import google.generativeai as genai
from google.api_core import exceptions # 예외 처리용 추가
from PIL import Image
import io
import json
import time

# 우리 회사 키워드 (제외 대상)
OUR_COMPANY_KEYWORDS = ["(주)피엘에스", "피엘에스", "PLS"]

class PRExtractor:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)

    def parse_with_llm(self, file_bytes):
        """
        PDF 이미지를 분석합니다.
        복잡한 재시도 로직 없이, 가장 확실한 모델을 찾아 한 번에 실행합니다.
        """
        # 1. PDF -> 이미지 변환
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            images = []
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                images.append(img)
            
            if not images:
                return {"error": "PDF를 이미지로 변환할 수 없습니다."}
        except Exception as e:
            return {"error": f"PDF 변환 실패: {str(e)}"}

        # 2. Vision 프롬프트
        prompt = f"""
            당신은 발주서 처리 AI입니다. 이미지를 분석하여 아래 정보를 JSON 형식으로 추출하세요.
            마크다운이나 설명 없이 오직 JSON 문자열만 반환해야 합니다.
            
            추출 항목: order_date, client_name({', '.join(OUR_COMPANY_KEYWORDS)} 제외), phone_number, address, consignee, payment_type, remarks, items
            
            ### 예시 JSON:
            {{
                "order_date": "2024-05-20",
                "client_name": "oo건설",
                "items": [
                    {{"item_name": "품명", "spec": "규격", "qty": 10}}
                ]
            }}
        """
        inputs = [prompt] + images

        # 3. 모델 설정 (The "No Number" Strategy)
        # 제미나이 정밀 분석 결과: 서버 목록에 '1.5' 숫자가 없는 'gemini-flash-latest'가 존재함.
        # 따라서 이 정확한 이름을 최우선으로 사용하여 404 에러를 방지합니다.
        
        # [1순위] 숫자 없는 Flash 최신 버전 (로그상 확인된 모델)
        TARGET_MODEL = "models/gemini-flash-latest"
        
        # [2순위] 혹시나 해서 남겨두는 예비용 (1.5 명시 버전)
        FALLBACK_MODEL = "models/gemini-1.5-flash-001"
        
        last_error = None
        current_model_name = TARGET_MODEL
        model = genai.GenerativeModel(current_model_name)
        
        # 재시도 설정 (총 3회 기회)
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = model.generate_content(inputs)
                
                text = response.text
                if text.startswith("```json"):
                    text = text.replace("```json", "").replace("```", "")
                elif text.startswith("```"):
                    text = text.replace("```", "")
                
                result_json = json.loads(text)
                
                # 성공 시 사용된 모델명 기록
                result_json['_used_model'] = current_model_name
                return result_json
                
            except Exception as inner_e:
                err_msg = str(inner_e).lower()
                last_error = f"{current_model_name}: {err_msg}"
                
                # [Case A] 모델 없음(404) -> Fallback 교체
                if "not found" in err_msg or "404" in err_msg:
                    if current_model_name == TARGET_MODEL:
                        # 1순위(이름 없는 것) 실패 시 -> 2순위(1.5 명시) 시도
                        current_model_name = FALLBACK_MODEL
                        model = genai.GenerativeModel(current_model_name)
                        continue
                    else:
                        break
                
                # [Case B] 429(Quota) -> 5초 대기
                if "429" in err_msg or "quota" in err_msg:
                    if attempt < max_retries - 1:
                        time.sleep(5) 
                        continue
                    break
                    
                # [Case C] 500 에러 -> 2초
                if "500" in err_msg or "internal" in err_msg:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    break
                
                break
        
        # 실패 시 에러 리턴
        return {"error": f"분석 실패 ({current_model_name}). (Last Error: {last_error})"}
        
        # 디버깅 정보 (실패 시)
        debug_info = f"\n[최종 선택 시도한 모델]: {target_model_name}"
        return {"error": f"분석 실패. {debug_info}\n(Last Error: {last_error})"}



