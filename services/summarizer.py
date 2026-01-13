import os
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv
from pathlib import Path

# 프로젝트 루트의 .env 로드 (crawler 기준 상위 디렉터리)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

# 환경 변수에서 API 키 읽기
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _fallback_summarize(text: str, max_chars: int = 500) -> str:
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
    - GEMINI_API_KEY가 없거나, 호출 실패 시에는 기존처럼 앞부분만 자른다.
    """
    # API 키 없으면 바로 폴백
    if not GEMINI_API_KEY:
        print("[summarizer] GEMINI_API_KEY not set, use fallback summarizer")
        return _fallback_summarize(text, max_chars)

    try:
        print("[summarizer] Calling Gemini API for summarization...")
        model = genai.GenerativeModel("gemini-2.5-flash")
        prompt = (
            "다음은 대학 웹사이트의 전체 텍스트입니다.\n"
            "- 상단/좌측/우측 메뉴, 풋터, '개인정보처리방침', '이메일 무단수집거부', 저작권 안내 등은 모두 무시하세요.\n"
            "- 오직 '공지사항' 영역의 실제 공지 본문만 사용해서 요약하세요.\n"
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
        response = model.generate_content(prompt)
        summary = (response.text or "").strip()
        print(f"[summarizer] Gemini summary received, length={len(summary)}")

        # 혹시 남아 있을 수 있는 마크다운 굵게(**) 표시는 제거
        summary = summary.replace("**", "")

        if not summary:
            return _fallback_summarize(text, max_chars)

        # 혹시 너무 길면 잘라주기
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."

        return summary

    except Exception as e:
        # 로그만 찍고 폴백 (어떤 예외인지 명확히 기록)
        print(f"[summarizer] ⚠️ Gemini 요약 호출 실패: {type(e).__name__}: {e}")
        print(f"[summarizer] 폴백 요약 사용 (원문 길이: {len(text)}자)")
        return _fallback_summarize(text, max_chars)