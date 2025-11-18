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


def _fallback_summarize(text: str, max_chars: int = 2000) -> str:
    """API 실패 시 기존처럼 앞부분만 자르는 폴백 로직."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


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
            "- 특히 다음 정보는 꼭 포함해 주시고, 5줄 이내의 한국어 문장으로 간결하게 정리해 주세요:\n"
            "  * 공지 제목\n"
            "  * 일시(날짜와 시간)\n"
            "  * 장소\n"
            "- 개인정보 처리, 이메일 수집 거부, 저작권, 기타 안내 문구는 절대 요약에 포함하지 마세요.\n"
            f"최대 {max_chars}자 이내로 작성해 주세요.\n\n"
            f"--- 원문 시작 ---\n{text}\n--- 원문 끝 ---"
        )
        response = model.generate_content(prompt)
        summary = (response.text or "").strip()
        print(f"[summarizer] Gemini summary received, length={len(summary)}")

        if not summary:
            return _fallback_summarize(text, max_chars)

        # 혹시 너무 길면 잘라주기
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."

        return summary

    except Exception as e:
        # 로그만 찍고 폴백
        print(f"[summarizer] Gemini 요약 호출 실패: {e}")
        return _fallback_summarize(text, max_chars)