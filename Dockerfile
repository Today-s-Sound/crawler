# Python 3.11 슬림 이미지 사용
FROM python:3.11-slim

# 필요하면 시스템 패키지 설치
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 복사 + 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 환경변수 (예시) - 실제 값은 Fargate Task 정의에서 override 가능
# ENV BACKEND_BASE_URL=https://www.todaysound.com

# 컨테이너가 실행될 때 실행할 커맨드
CMD ["python", "main.py"]