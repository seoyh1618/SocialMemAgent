# SocialMemAgent 기능 테스트 가이드

> **스택**: FastAPI + Google ADK (Gemini 2.5 Flash) + React 19
> **테스트 대상**: 인증, MemGPT 3계층 메모리, 세션 동기화, 에이전트 대화
> **전제**: 백엔드 `uvicorn main:app --reload` (포트 8000), 프론트엔드 `npm run dev` (포트 5173) 실행 중

---

## 목차

1. [인증 (Auth)](#1-인증-auth)
2. [메모리 REST API](#2-메모리-rest-api)
3. [세션 생성 & 동기화 (MemGPT 핵심)](#3-세션-생성--동기화-memgpt-핵심)
4. [에이전트 대화 & 메모리 툴 자동 호출](#4-에이전트-대화--메모리-툴-자동-호출)
5. [캠페인 아카이브 & 시맨틱 검색](#5-캠페인-아카이브--시맨틱-검색)
6. [컨텍스트 압축 (Recall Memory)](#6-컨텍스트-압축-recall-memory)
7. [프론트엔드 UI 수동 테스트](#7-프론트엔드-ui-수동-테스트)

---

## 1. 인증 (Auth)

### 1-1. 회원가입

```bash
curl -s -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "display_name": "테스트 유저"
  }' | python3 -m json.tool
```

**기대 응답:**
```json
{
  "userId": "u_testuser",
  "username": "testuser",
  "email": "test@example.com",
  "displayName": "테스트 유저",
  "avatarUrl": null,
  "createdAt": "2026-03-12T..."
}
```

**확인 포인트:**
- `userId`가 `u_{username}` 형식인지
- 같은 username으로 재가입 시 `409 Conflict` 반환되는지

---

### 1-2. 로그인 (기존 SHA-256 사용자 포함)

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }' | python3 -m json.tool
```

**기대 응답:** 회원가입과 동일한 사용자 정보
**확인 포인트:** `ValueError: Invalid salt` 에러가 사라졌는지 (bcrypt/SHA-256 하이브리드 검증)

```bash
# 잘못된 비밀번호 테스트
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "wrong"}' | python3 -m json.tool
# 기대: 401 {"detail": "비밀번호가 올바르지 않습니다."}
```

---

### 1-3. 사용자 정보 조회

```bash
curl -s http://localhost:8000/auth/me/u_testuser | python3 -m json.tool
# 기대: 동일한 사용자 정보
# 없는 userId: 404
```

---

## 2. 메모리 REST API

> **변수 설정** (이후 예제에서 재사용)
> ```bash
> USER_ID="u_testuser"
> ```

### 2-1. 메모리 초기 조회 (빈 상태)

```bash
curl -s http://localhost:8000/memory/$USER_ID | python3 -m json.tool
```

**기대 응답 구조:**
```json
{
  "user_id": "u_testuser",
  "memory": {
    "core_profile": {
      "display_name": "",
      "twitter_handle": null,
      "instagram_handle": null,
      "industry": "",
      "target_platforms": [],
      "brand_voice": {
        "tone": "",
        "preferred_styles": [],
        "avoid_topics": [],
        "signature_hashtags": [],
        "content_pillars": []
      },
      "extra_fields": {}
    },
    "campaign_archive": [],
    "asset_archive": [],
    "recall_log": [],
    "working_summary": "",
    "total_campaigns": 0
  }
}
```

---

### 2-2. Core Memory 업데이트 (PUT)

```bash
curl -s -X PUT http://localhost:8000/memory/$USER_ID \
  -H "Content-Type: application/json" \
  -d '{
    "core_profile": {
      "display_name": "테스트 유저",
      "industry": "패션",
      "target_platforms": ["instagram", "tiktok"],
      "brand_voice": {
        "tone": "트렌디하고 친근한",
        "preferred_styles": ["릴스", "캐러셀"],
        "avoid_topics": ["정치", "논란"],
        "signature_hashtags": ["#OOTD", "#패션그램"],
        "content_pillars": ["스타일링 팁", "신상 소개", "데일리룩"]
      }
    }
  }' | python3 -m json.tool
```

**기대 응답:** `{"status": "ok", "user_id": "u_testuser"}`

```bash
# 업데이트 확인
curl -s http://localhost:8000/memory/$USER_ID \
  | python3 -c "import sys,json; m=json.load(sys.stdin); print(json.dumps(m['memory']['core_profile'], ensure_ascii=False, indent=2))"
```

---

### 2-3. 부분 업데이트 (기존 필드 보존 확인)

```bash
# industry만 변경 → brand_voice는 유지되어야 함
curl -s -X PUT http://localhost:8000/memory/$USER_ID \
  -H "Content-Type: application/json" \
  -d '{"core_profile": {"industry": "뷰티"}}' | python3 -m json.tool

# brand_voice가 여전히 있는지 확인
curl -s http://localhost:8000/memory/$USER_ID \
  | python3 -c "import sys,json; m=json.load(sys.stdin); \
    cp=m['memory']['core_profile']; \
    print('industry:', cp['industry']); \
    print('brand_voice 유지:', cp['brand_voice']['tone'])"
```

**기대:** `industry: 뷰티`, `brand_voice 유지: 트렌디하고 친근한`

---

### 2-4. 캠페인 아카이브 직접 저장 & 페이지네이션

```bash
# 캠페인 3개 생성 (에이전트 없이 직접 PUT으로)
for i in 1 2 3; do
curl -s -X PUT http://localhost:8000/memory/$USER_ID \
  -H "Content-Type: application/json" \
  -d "{
    \"campaign_archive\": [{
      \"campaign_id\": \"cam_$i\",
      \"timestamp\": \"2026-03-$((10+i))T10:00:00\",
      \"goal\": \"캠페인 $i 목표\",
      \"selected_trend\": \"트렌드 $i\",
      \"target_audiences\": [\"MZ세대\"],
      \"selected_styles\": [\"릴스\"],
      \"guideline_summary\": \"가이드라인 $i\",
      \"platforms_used\": [\"instagram\"],
      \"performance_notes\": \"\"
    }]
  }" > /dev/null
done
echo "캠페인 3개 추가 완료"
```

```bash
# 페이지네이션 테스트 (limit=2, page=0)
curl -s "http://localhost:8000/memory/$USER_ID/campaigns?limit=2&page=0" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('total:', d['total']); \
    print('page 0 count:', len(d['campaigns'])); \
    [print(' -', c['campaign_id']) for c in d['campaigns']]"

# 다음 페이지 (page=1)
curl -s "http://localhost:8000/memory/$USER_ID/campaigns?limit=2&page=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('page 1 count:', len(d['campaigns'])); \
    [print(' -', c['campaign_id']) for c in d['campaigns']]"
```

**기대:** `total: 3`, page 0에 2개, page 1에 1개 (offset 버그 수정 확인)

---

## 3. 세션 생성 & 동기화 (MemGPT 핵심)

### 3-1. 새 세션 생성 (영구 메모리 → 대화 세션 복사)

```bash
SESSION_RESP=$(curl -s -X POST http://localhost:8000/sessions/create/$USER_ID)
echo $SESSION_RESP | python3 -m json.tool

SESSION_ID=$(echo $SESSION_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
echo "세션 ID: $SESSION_ID"
```

**기대 응답:**
```json
{
  "session_id": "s_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "user_id": "u_testuser",
  "memory_loaded": true
}
```

**확인 포인트:**
- `memory_loaded: true` — 영구 메모리가 새 세션에 복사됐는지
- `memory_loaded: false`면 게스트 세션으로 시작 (정상, 단 메모리 없음)

---

### 3-2. 세션 동기화 (대화 세션 → 영구 메모리)

```bash
# 대화 후 동기화 (실제로는 에이전트 응답 후 자동 호출됨)
curl -s -X POST http://localhost:8000/sessions/sync/$USER_ID/$SESSION_ID \
  | python3 -m json.tool
```

**기대 응답:**
```json
{
  "status": "ok",
  "synced": true
}
```

---

### 3-3. 세션 생명주기 전체 흐름 검증

```bash
# 1. 메모리에 데이터 저장
curl -s -X PUT http://localhost:8000/memory/$USER_ID \
  -H "Content-Type: application/json" \
  -d '{"core_profile": {"display_name": "세션테스트유저", "industry": "테크"}}' \
  > /dev/null

# 2. 새 세션 생성 (메모리가 세션으로 복사되어야 함)
NEW_SESSION=$(curl -s -X POST http://localhost:8000/sessions/create/$USER_ID)
echo "세션 생성:" $(echo $NEW_SESSION | python3 -c "import sys,json; d=json.load(sys.stdin); print('memory_loaded='+str(d['memory_loaded']), 'session='+d['session_id'][:12]+'...')")

# 3. 동기화 (수동)
SID=$(echo $NEW_SESSION | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
curl -s -X POST http://localhost:8000/sessions/sync/$USER_ID/$SID | python3 -m json.tool
```

---

## 4. 에이전트 대화 & 메모리 툴 자동 호출

> 이 섹션은 **프론트엔드 채팅 UI** 또는 SSE 직접 호출로 테스트합니다.

### 4-1. 브라우저 콘솔에서 SSE 테스트

브라우저 개발자 도구 콘솔에서 실행:

```javascript
// 먼저 세션 생성
const sessionResp = await fetch('/api/sessions/create/u_testuser', {method: 'POST'});
const {session_id} = await sessionResp.json();
console.log('세션:', session_id);

// SSE 스트리밍으로 에이전트 호출
const es = new EventSource(
  `/api/agent/stream?session_id=${session_id}&user_id=u_testuser&message=${encodeURIComponent('안녕하세요! 저는 패션 브랜드를 운영하고 있어요.')}`
);
es.onmessage = (e) => console.log(JSON.parse(e.data));
es.onerror = () => es.close();
```

---

### 4-2. 프로필 자동 업데이트 테스트

**채팅 UI에서 입력:**
```
저는 @fashionista_kr 라는 인스타 계정을 운영하고 있고, 주로 20대 여성을 타겟으로 하는 스트리트 패션 브랜드예요.
```

**에이전트 응답 후 확인:**
```bash
curl -s http://localhost:8000/memory/u_testuser \
  | python3 -c "import sys,json; m=json.load(sys.stdin)['memory']; \
    cp=m['core_profile']; \
    print('instagram:', cp.get('instagram_handle')); \
    print('industry:', cp['industry'])"
```

**기대:** `instagram: @fashionista_kr`, `industry: 패션` (또는 에이전트가 파악한 값)

---

### 4-3. 브랜드 보이스 자동 업데이트 테스트

**채팅 UI에서 입력:**
```
우리 브랜드는 밝고 에너지 넘치는 톤을 선호하고, 정치적 내용이나 논란거리는 절대 피해요. #OOTD #스트리트패션 해시태그를 자주 써요.
```

**확인:**
```bash
curl -s http://localhost:8000/memory/u_testuser \
  | python3 -c "import sys,json; m=json.load(sys.stdin)['memory']; \
    bv=m['core_profile']['brand_voice']; \
    print('tone:', bv['tone']); \
    print('avoid:', bv['avoid_topics']); \
    print('hashtags:', bv['signature_hashtags'])"
```

---

### 4-4. 메모리 툴 호출 로그 확인

백엔드 터미널에서 다음 로그 패턴이 보여야 함:
```
[MemGPT] memory_update_user_profile called
[MemGPT] memory_update_brand_voice called
[MemGPT] memory_archive_conversation called
```

프론트엔드에서는 SSE 이벤트 스트림에 `tool_call` 타입 이벤트로 표시됩니다.

---

## 5. 캠페인 아카이브 & 시맨틱 검색

### 5-1. 에이전트를 통한 캠페인 자동 아카이브

**채팅 UI에서 캠페인 생성 후 완료 요청:**
```
여름 세일 캠페인을 위한 인스타 릴스 콘텐츠 만들어주세요. 타겟은 20대 여성이고 트렌드는 Y2K 스타일이에요.
```

**콘텐츠 생성 후 추가 메시지:**
```
이 캠페인 기록해줘요.
```

**아카이브 확인:**
```bash
curl -s http://localhost:8000/memory/u_testuser/campaigns \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('총 캠페인:', d['total']); \
    [print(f\" - {c['campaign_id']}: {c['goal'][:30]}\") for c in d['campaigns']]"
```

---

### 5-2. 시맨틱 캠페인 검색 (에이전트 대화)

과거 캠페인이 2개 이상 아카이브된 상태에서:

**채팅 UI에서 입력:**
```
예전에 Y2K 관련 캠페인 했던 거 기억나요? 비슷한 스타일로 다시 해보고 싶어요.
```

**백엔드 로그에서 확인:**
```
[MemGPT] memory_search_campaigns called, query="Y2K"
[MemGPT] Found 1 campaigns matching query
```

**또는 직접 API 테스트 (curl):**
```bash
# 이 엔드포인트는 내부 툴용이지만 검증 목적으로 메모리 조회 후 확인
curl -s http://localhost:8000/memory/u_testuser \
  | python3 -c "import sys,json; \
    camps=json.load(sys.stdin)['memory']['campaign_archive']; \
    [print(c['campaign_id'], c['selected_trend']) for c in camps]"
```

---

### 5-3. 캠페인 페이지네이션 정확성 검증

```bash
USER_ID="u_testuser"

# 캠페인 5개 수동 추가
python3 << 'EOF'
import requests, json

base = "http://localhost:8000"
uid = "u_testuser"

for i in range(1, 6):
    payload = {
        "campaign_archive": [{
            "campaign_id": f"test_cam_{i:03d}",
            "timestamp": f"2026-03-{i:02d}T10:00:00",
            "goal": f"테스트 캠페인 {i}번",
            "selected_trend": ["Y2K", "레트로", "미니멀", "보헤미안", "아방가르드"][i-1],
            "target_audiences": ["MZ세대"],
            "selected_styles": ["릴스"],
            "guideline_summary": f"캠페인 {i} 가이드",
            "platforms_used": ["instagram"],
            "performance_notes": ""
        }]
    }
    # 기존에 있으면 덮어쓰지 않도록 GET 후 append 로직이 백엔드에 있어야 함
    resp = requests.put(f"{base}/memory/{uid}", json=payload)
    print(f"캠페인 {i}: {resp.json()}")
EOF

# 페이지 0 (limit=2)
echo "=== Page 0 ==="
curl -s "http://localhost:8000/memory/$USER_ID/campaigns?limit=2&page=0" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('count:', len(d['campaigns'])); \
    [print(' ', c['campaign_id']) for c in d['campaigns']]"

# 페이지 1
echo "=== Page 1 ==="
curl -s "http://localhost:8000/memory/$USER_ID/campaigns?limit=2&page=1" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('count:', len(d['campaigns'])); \
    [print(' ', c['campaign_id']) for c in d['campaigns']]"

# 페이지 2 (나머지 1개)
echo "=== Page 2 ==="
curl -s "http://localhost:8000/memory/$USER_ID/campaigns?limit=2&page=2" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('count:', len(d['campaigns'])); \
    [print(' ', c['campaign_id']) for c in d['campaigns']]"
```

**기대:** Page 0=2개, Page 1=2개, Page 2=1개 (중복 없음)

---

## 6. 컨텍스트 압축 (Recall Memory)

### 6-1. Recall Log 누적 확인

```bash
# 메모리 상태에서 recall_log 조회
curl -s http://localhost:8000/memory/u_testuser \
  | python3 -c "import sys,json; \
    m=json.load(sys.stdin)['memory']; \
    log=m['recall_log']; \
    print(f'recall_log 길이: {len(log)}'); \
    print(f'working_summary: {repr(m[\"working_summary\"][:100])}'); \
    [print(f'  [{e[\"role\"]}] {e[\"content\"][:50]}...') for e in log[-3:]]"
```

---

### 6-2. Working Summary 수동 업데이트 테스트

**채팅 UI에서 입력:**
```
지금까지 대화 내용을 요약해서 기억해줘요.
```

**백엔드 로그 확인:**
```
[MemGPT] memory_update_working_summary called
```

**메모리에서 확인:**
```bash
curl -s http://localhost:8000/memory/u_testuser \
  | python3 -c "import sys,json; \
    m=json.load(sys.stdin)['memory']; \
    print('working_summary:', m['working_summary'])"
```

---

### 6-3. 자동 압축 트리거 테스트 (부하 시뮬레이션)

```python
# simulate_compression.py
# 백엔드 폴더에서 실행: python3 simulate_compression.py
import asyncio
import sys
sys.path.insert(0, 'agents/src')

from agents.memory_tools import memory_append_recall, _MEMORY_KEY
from agents.schemas import MemoryState

class FakeToolContext:
    def __init__(self):
        self.state = {_MEMORY_KEY: MemoryState().model_dump()}

async def test_compression():
    ctx = FakeToolContext()

    # recall_log에 30개 항목 추가 (기본 한도: 40 turns)
    for i in range(30):
        result = await memory_append_recall(
            tool_context=ctx,
            role="user" if i % 2 == 0 else "assistant",
            content=f"테스트 메시지 {i}: 안녕하세요 이것은 컨텍스트 압축을 테스트하기 위한 긴 메시지입니다. " * 5
        )
        if i % 10 == 9:
            print(f"[{i+1}/30] {result[:80]}...")

    # 최종 상태 확인
    from agents.schemas import MemoryState
    final = MemoryState(**ctx.state[_MEMORY_KEY])
    print(f"\n최종 recall_log 길이: {len(final.recall_log)}")
    print(f"working_summary 길이: {len(final.working_summary)}")
    print(f"working_summary: {final.working_summary[:200]}")

asyncio.run(test_compression())
```

**실행:**
```bash
cd /Users/kusrc/Desktop/SocialMemAgent/SocialMediaBrandingAgent
python3 simulate_compression.py
```

**기대:** recall_log가 20개 이하로 유지되고 working_summary에 압축 내용이 담김

---

## 7. 프론트엔드 UI 수동 테스트

### 7-1. 로그인 & 메모리 초기화 플로우

1. `http://localhost:5173` 접속
2. 오른쪽 상단 또는 사이드바에서 **"로그인"** 클릭
3. `testuser` / `password123` 입력 후 로그인
4. **확인 포인트:**
   - 사이드바가 "로그인 전 CTA 카드" → "프로필 카드 + 메모리 스냅샷"으로 전환되는지
   - 브라우저 Network 탭에서 `GET /memory/u_testuser` 요청이 발생하는지
   - `POST /sessions/create/u_testuser` 요청이 발생하는지

---

### 7-2. ProfileBlock 탭 테스트 (Identity / Brand Voice / History)

1. 우측 패널에서 **"✦ 프로필"** 탭 클릭
2. **Identity 탭:**
   - Display Name, Industry, Target Platforms 수정
   - "저장" → `PUT /memory/u_testuser` 요청 확인 (Network 탭)
3. **Brand Voice 탭:**
   - Tone, Hashtags, Avoid Topics 수정 후 저장
4. **History 탭:**
   - 과거 캠페인 목록이 표시되는지
   - `GET /memory/u_testuser/campaigns` 요청 확인

---

### 7-3. 채팅 후 메모리 자동 동기화 확인

1. 채팅 입력창에 메시지 입력 후 전송
2. 에이전트 응답 완료 후:
   - Network 탭에서 `POST /sessions/sync/u_testuser/{session_id}` 요청이 자동 발생하는지 확인
3. ProfileBlock History 탭을 새로고침 없이 확인
   - recall_log나 캠페인이 업데이트 됐는지

---

### 7-4. 메모리 영속성 테스트 (새로고침 후 유지)

1. 채팅으로 브랜드 정보 입력 (`저는 카페 브랜드 운영해요. @mycafe_official`)
2. 에이전트 응답 완료까지 대기
3. **브라우저 새로고침 (F5)**
4. ProfileBlock Identity 탭 확인
   - `instagram_handle`에 `@mycafe_official`이 유지되는지

**백엔드 직접 확인:**
```bash
curl -s http://localhost:8000/memory/u_testuser \
  | python3 -c "import sys,json; \
    cp=json.load(sys.stdin)['memory']['core_profile']; \
    print('instagram:', cp.get('instagram_handle'))"
```

---

## 빠른 전체 검증 스크립트

```bash
#!/bin/bash
# quick_test.sh — 핵심 기능 30초 검증

BASE="http://localhost:8000"
UNAME="quicktest_$(date +%s)"
USER_ID="u_$UNAME"

echo "=== 1. 회원가입 ==="
curl -s -X POST $BASE/auth/signup \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$UNAME\",\"email\":\"$UNAME@test.com\",\"password\":\"pw1234\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('userId:', d.get('userId','ERROR'))"

echo ""
echo "=== 2. 로그인 ==="
curl -s -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$UNAME\",\"password\":\"pw1234\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('login OK:', 'userId' in d)"

echo ""
echo "=== 3. 메모리 초기 상태 ==="
curl -s $BASE/memory/$USER_ID \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('memory exists:', 'memory' in d)"

echo ""
echo "=== 4. Core Memory 업데이트 ==="
curl -s -X PUT $BASE/memory/$USER_ID \
  -H "Content-Type: application/json" \
  -d '{"core_profile":{"display_name":"퀵테스트","industry":"테크"}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('update status:', d.get('status'))"

echo ""
echo "=== 5. 업데이트 반영 확인 ==="
curl -s $BASE/memory/$USER_ID \
  | python3 -c "import sys,json; cp=json.load(sys.stdin)['memory']['core_profile']; print('industry:', cp['industry'])"

echo ""
echo "=== 6. 세션 생성 ==="
SESSION=$(curl -s -X POST $BASE/sessions/create/$USER_ID)
echo $SESSION | python3 -c "import sys,json; d=json.load(sys.stdin); print('session_id:', d.get('session_id','ERROR')[:16]+'...', '| memory_loaded:', d.get('memory_loaded'))"

echo ""
echo "=== 7. 세션 동기화 ==="
SID=$(echo $SESSION | python3 -c "import sys,json; print(json.load(sys.stdin).get('session_id',''))")
if [ -n "$SID" ]; then
  curl -s -X POST $BASE/sessions/sync/$USER_ID/$SID \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('sync status:', d.get('status'), '| synced:', d.get('synced'))"
else
  echo "세션 ID 없음 - 스킵"
fi

echo ""
echo "=== 8. 캠페인 페이지네이션 ==="
curl -s "$BASE/memory/$USER_ID/campaigns?limit=10&page=0" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('total:', d.get('total',0), '| page:', d.get('page',0))"

echo ""
echo "✅ 기본 검증 완료"
```

```bash
chmod +x quick_test.sh && ./quick_test.sh
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `ValueError: Invalid salt` | 기존 SHA-256 사용자 로그인 | `_check_password` bcrypt/SHA-256 하이브리드 적용 (이미 수정됨) |
| `memory_loaded: false` | 영구 메모리 세션(`memory_u_{userId}`)이 없음 | PUT으로 메모리 먼저 저장 후 세션 생성 |
| 캠페인 페이지 중복/누락 | offset 계산 오류 | `offset = page * limit` (수정됨) |
| 프로필 업데이트 후 소실 | 대화 세션 메모리가 영구 저장소 덮어씀 | sync 엔드포인트가 올바르게 merge하는지 확인 |
| 시맨틱 검색 결과 없음 | Vertex AI 임베딩 API 권한 없음 | `GOOGLE_CLOUD_PROJECT` 환경변수 & 서비스 계정 확인, 키워드 폴백은 동작해야 함 |
| SSE 스트리밍 중단 | 네트워크 타임아웃 | `uvicorn --timeout-keep-alive 120` 옵션 추가 |
