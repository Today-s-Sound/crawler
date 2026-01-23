import os
import time
from typing import Optional

import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv
from pathlib import Path

# 프로젝트 루트의 .env 로드 (crawler 기준 상위 디렉터리)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# 환경 변수에서 API 키 읽기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _fallback_summarize(text: str, max_chars: int = 1000) -> str:
    """
    API 실패 시 폴백 로직.
    - 원문에서 메뉴/네비게이션이 아닌 실제 본문 부분만 추출 시도
    - 줄바꿈으로 분리해서 짧은 메뉴 항목들(10자 미만)은 스킵
    """
    lines = text.split("\n")
    content_lines = []
    
    for line in lines:
        line = line.strip()
        # 빈 줄이나 너무 짧은 줄(메뉴 항목)은 스킵
        if len(line) < 10:
            continue
        # 메뉴 키워드가 포함된 줄 스킵
        menu_keywords = ["메뉴", "로그인", "회원가입", "검색", "홈", "공지사항", "자료실", 
                        "갤러리", "커뮤니티", "바로가기", "사이트맵", "개인정보", "이용약관"]
        if any(kw in line for kw in menu_keywords):
            continue
        content_lines.append(line)
    
    result = " ".join(content_lines)
    
    if len(result) <= max_chars:
        return result if result else "[요약 생성 실패]"
    return result[:max_chars] + "..."


def summarize(text: str, max_chars: int = 500) -> str:
    """
    Gemini API를 사용해서 요약을 생성한다.
    - Rate Limit(429) 발생 시 지수 백오프(Exponential Backoff)로 재시도한다.
    """
    if not GEMINI_API_KEY:
        print("[summarizer] GEMINI_API_KEY not set, use fallback summarizer")
        return _fallback_summarize(text, max_chars)

    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = (
        "다음은 웹사이트의 전체 텍스트입니다.\n"
        "- 상단/좌측/우측 메뉴, 풋터, '개인정보처리방침', '이메일 무단수집거부', 저작권 안내 등은 모두 무시하세요.\n"
        "- 오직 실제 공지 본문만 사용해서 요약하세요.\n"
        "- 제목은 이미 별도 필드로 관리하므로, 요약 문장에 제목을 반복해서 쓰지 마세요.\n"
        "- 마크다운 문법(**굵게**, *기울임*, 목록 기호 -, *, 숫자. 등)을 사용하지 말고, 순수한 한국어 문장만 써 주세요.\n"
        "- 특히 다음 정보가 포함되면 좋지만, 자연스러운 한글 문장 3~5줄 내에서 간결하게 정리해 주세요:\n"
        "  - 일시(날짜와 시간)\n"
        "  - 장소\n"
        "  - 누가, 무엇을 하는지(강의/행사/모집 등 핵심 내용)\n"
        "- 개인정보 처리, 이메일 수집 거부, 저작권, 기타 안내 문구는 절대 요약에 포함하지 마세요.\n"
        f"최대 {max_chars}자 이내로 작성해 주세요.\n\n"
        f"--- 원문 시작 ---\n{text}\n--- 원문 끝 ---"
    )

    max_retries = 3  # 최대 3번까지 재시도
    # Rate Limit(15 RPM 기준) 여유를 조금 더 주기 위해 대기 시간 소폭 증가
    base_delay = 30  # 1차 30초, 2차 60초 대기

    for attempt in range(max_retries):
        try:
            # Rate Limit 방지: 매 요청마다 6초 대기 (15 RPM 보다 살짝 느리게)
            if attempt == 0:
                time.sleep(6)
                print(f"[summarizer] Rate Limit 방지: 6초 대기 완료")
            
            print(f"[summarizer] Calling Gemini API... (Attempt {attempt + 1}/{max_retries})")
            response = model.generate_content(prompt)
            summary = (response.text or "").strip()
            
            summary = summary.replace("**", "")  # 마크다운 제거
            
            if not summary:
                return _fallback_summarize(text, max_chars)

            if len(summary) > max_chars:
                summary = summary[:max_chars] + "..."

            print(f"[summarizer] Success! length={len(summary)}")
            return summary

        except exceptions.ResourceExhausted:
            # 429 에러 발생 시 대기 후 재시도
            if attempt < max_retries - 1:
                wait_time = base_delay * (attempt + 1)
                print(f"[summarizer] ⚠️ Quota Exceeded (429). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print("[summarizer] ❌ Max retries reached for Quota Exceeded.")
        
        except Exception as e:
            # 그 외 에러는 바로 폴백
            print(f"[summarizer] ⚠️ Error: {type(e).__name__}: {e}")
            break

    # 모든 시도 실패 시 폴백
    print(f"[summarizer] 폴백 요약 사용 (원문 길이: {len(text)}자)")
    return _fallback_summarize(text, max_chars)