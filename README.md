# TodaySound 크롤러 개요

이 디렉토리의 크롤러는 **사용자가 구독한 웹사이트(현재: 동국대 SW교육원 공지사항)** 를 주기적으로 크롤링하고, **새로 올라온 게시글의 핵심 내용을 요약해서 백엔드로 전달**하는 역할을 합니다.

### 전체 동작 흐름

1. **구독 정보 조회**
   - `services/subscription_client.fetch_subscriptions()`  
   - 백엔드 `GET /internal/subscriptions` 호출  
   - 각 구독에 대해 `id`, `user_id`, `site_url`, `site_alias`, `keyword`, `urgent`, `last_seen_post_id` 정보를 가져옵니다.

2. **사이트 크롤링**
   - `main.process_subscription(sub)`에서 `DonggukSwBoardCrawler` 사용  
   - `fetch_post_list(site_url)`로 공지 목록(최신→과거)을 가져오고, 각 게시글의 `id`, `url`, `title`, `date`를 수집합니다.

3. **새 게시물 필터링**
   - `last_seen_post_id` 기준으로 이전에 본 게시글까지는 건너뛰고, 그 이후에 올라온 게시글만 `filter_new_posts()`로 추립니다.
   - 첫 실행(`last_seen_post_id == None`)일 때는 **알림을 만들지 않고**, 가장 최신 게시글의 `id`를 기준점으로 저장만 합니다.

4. **키워드 필터 + 요약 생성**
   - 새 게시물들에 대해 `fetch_post_content(post["url"])`로 본문 전체를 크롤링.
   - 구독에 설정된 `keyword`가 제목/본문에 포함될 때만 처리 (`keyword_match`).
   - `services/summarizer.summarize(text)`를 호출해 요약 생성  
     - `GEMINI_API_KEY` 가 설정되어 있으면 **Gemini API(gemini-2.5-flash)** 로 공지 본문에서 제목/시간/장소 중심으로 요약  
     - 키가 없거나 오류 시에는 텍스트 앞부분만 잘라서 폴백.

5. **알림 생성 + last_seen 갱신**
   - `services/notification_client.create_alert(alert_payload)`  
     - 백엔드 `POST /internal/alerts` 호출 → `Summary`/알림 레코드 생성.
   - 모든 새 게시물을 처리한 뒤, 가장 최신 게시글의 ID로  
     `update_subscription_last_seen(subscription_id, latest_id)` 실행  
     → `PATCH /internal/subscriptions/{id}/last_seen` 로 마지막 본 게시물 ID 업데이트.

### 디버그 모드 (단일 게시글 크롤링 테스트)

`main.debug_fetch_first_post()` 를 통해:

- 첫 번째 구독의 `site_url`에서 게시물 목록과 첫 게시물 메타데이터를 가져오고,
- 첫 게시물 본문 일부와 `summarize()` 결과를 콘솔에 출력해서  
  **크롤링 + 요약이 정상 동작하는지** 빠르게 확인할 수 있습니다.
