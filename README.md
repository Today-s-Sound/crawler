# TodaySound 크롤러

여러 웹사이트의 공지사항을 크롤링하고, 새 게시글을 요약하여 알림을 생성하는 크롤러입니다.

## 주요 기능

### 1. 크롤러 팩토리 (`factories/crawler_factory.py`)
- **기능**: 구독 정보로부터 적절한 크롤러 인스턴스를 생성
- **동작 방식**:
  - `site_type`이 있으면 해당 타입의 크롤러 생성
  - 없으면 URL 도메인을 분석하여 크롤러 선택
  - 지원 사이트: 동국대 SW교육원, 동국대 컴퓨터·AI학부, 넓은마을, 에이블뉴스, 한국장애인고용공단, 실로암시각장애인복지관, 한국장애인개발원

### 2. 크롤러 (`sites/`)
- **기능**: 웹사이트에서 게시글 정보를 추출
- **제공 메서드**:
  - `fetch_post_list(list_url)`: 게시글 목록 크롤링 (id, url, title, date 반환)
  - `fetch_post_content(post_url)`: 게시글 본문 텍스트 추출
- **구현체**: 각 사이트별로 HTML 구조에 맞춰 구현

### 3. 구독 처리 (`services/subscription_processor.py`)
- **기능**: 구독 하나에 대해 새 게시글을 처리하여 알림 생성
- **처리 과정**:
  1. `last_seen_post_id` 기준으로 새 게시글 필터링
  2. 첫 실행 시 최신 게시글 1개만 처리하고 기준점 설정
  3. 각 새 게시글에 대해 본문 크롤링 → 요약 생성 → 알림 생성
  4. 키워드 매칭 여부 확인 (키워드가 있으면 제목/본문에 포함 여부 체크)
  5. 모든 처리 완료 후 `last_seen_post_id` 업데이트

### 4. 게시글 필터링 (`utils/post_filter.py`)
- **기능**: 새 게시글만 추출
- **로직**:
  - `last_seen_post_id`를 찾아 그 이후 게시글만 반환
  - 찾지 못한 경우: ID 비교를 통해 삭제/공지 전환 여부 판단
  - 페이지 넘어간 경우: 최신 3개만 반환 (안전 장치)

### 5. 요약 서비스 (`services/summarizer_service.py`)
- **기능**: 게시글 본문을 요약하여 핵심 내용만 추출
- **구현**:
  - Gemini API (gemini-2.5-flash) 사용
  - API 실패 시 텍스트 앞부분만 잘라서 폴백
  - 본문이 없고 이미지/첨부파일만 있는 경우 특별 처리

### 6. 알림 서비스 (`services/alert_service.py`)
- **기능**: 알림 생성 및 구독 상태 업데이트
- **제공 메서드**:
  - `create_alert(alert_payload)`: 백엔드에 알림 생성 요청
  - `update_subscription_last_seen(subscription_id, last_seen_post_id)`: 마지막 확인 게시글 ID 업데이트

### 7. 캐시 관리 (`services/cache_manager.py`)
- **기능**: 본문과 요약 결과를 캐싱하여 중복 크롤링 방지
- **캐시 종류**:
  - 본문 캐시: 같은 게시글의 본문을 여러 구독에서 재사용
  - 요약 캐시: 같은 게시글의 요약을 여러 구독에서 재사용
- **생명주기**: 사이트별로 독립적인 캐시 인스턴스 생성

### 8. Orchestrator (`orchestrators/crawler_orchestrator.py`)
- **기능**: 전체 크롤링 흐름을 조율
- **처리 과정**:
  1. 구독 목록을 `site_url` 기준으로 그룹화
  2. 같은 사이트의 구독들은 게시글 목록을 한 번만 크롤링
  3. 각 사이트별로 크롤러 생성 → 게시글 목록 크롤링 → 각 구독 처리
  4. 오류 발생 시 해당 구독만 스킵하고 계속 진행

### 9. DI 컨테이너 (`containers/application_container.py`)
- **기능**: 모든 의존성의 생명주기 관리
- **관리 객체**:
  - 서비스들 (Singleton): AlertService, SummarizerService
  - 팩토리 (Singleton): CrawlerFactory
  - 캐시 매니저 (Factory): 사이트별로 새로 생성
  - 구독 목록 조회 함수 (Callable)

## 전체 실행 흐름

```
main.py
  ↓
ApplicationContainer (의존성 생성)
  ↓
CrawlerOrchestrator (전체 흐름 조율)
  ↓
1. 구독 목록 조회 (subscription_client)
  ↓
2. 사이트별 그룹화
  ↓
3. 각 사이트별:
   ├─ CrawlerFactory로 크롤러 생성
   ├─ 게시글 목록 크롤링
   └─ 각 구독별:
      ├─ 새 게시글 필터링 (post_filter)
      ├─ 본문 크롤링 (캐시 확인)
      ├─ 요약 생성 (캐시 확인)
      └─ 알림 생성 (alert_service)
```

## 프로젝트 구조

```
crawler/
├── main.py                    # 진입점
├── containers/                # DI 컨테이너
├── orchestrators/             # 전체 흐름 조율
├── factories/                 # 크롤러 생성
├── services/                  # 비즈니스 로직
│   ├── alert_service.py      # 알림 생성
│   ├── summarizer_service.py # 요약 생성
│   ├── cache_manager.py       # 캐시 관리
│   └── subscription_processor.py  # 구독 처리
├── sites/                     # 크롤러 구현체
└── utils/                     # 유틸리티
    └── post_filter.py        # 게시글 필터링
```

## 새 크롤러 추가

1. `sites/` 디렉토리에 `SiteCrawler`를 상속한 클래스 생성
2. `factories/crawler_factory.py`에 등록:
   - Import 추가
   - `_initialize_registry()`에 `register()` 호출 추가
   - `_domain_mapping`에 URL 매핑 추가 (선택)
