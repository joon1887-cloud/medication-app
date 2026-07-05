# Handoff: 약 정보 앱 리디자인 (medication-app)

## Overview
Flask 기반 약 관리 웹앱(https://github.com/joon1887-cloud/medication-app, `templates/index.html` 단일 파일 SPA)의 전면 리디자인.
"클리니컬 라이트" 스타일 — 화이트 + 블루, 깨끗하고 신뢰감 있는 의료 앱 톤.
대상 화면: 대시보드, 약장(일반인/전문가 뷰), 처방 추가 폼(2단계), 약 검색, 약 상세 패널, 모바일 전 화면(하단 탭바).

## About the Design Files
이 폴더의 HTML 파일들은 **디자인 레퍼런스**입니다 — 의도한 룩앤필과 동작을 보여주는 프로토타입이며, 그대로 복사해 쓰는 프로덕션 코드가 아닙니다.
할 일: 기존 codebase(`templates/index.html`의 vanilla JS + 인라인 CSS 구조)에 이 디자인을 **재구현**하는 것. 기존 구조를 유지해도 되고, CSS를 `static/`으로 분리해도 됩니다.

- `약 정보 앱 리디자인.dc.html` — 전 화면 정적 목업 (데스크톱 + 모바일). 시안 번호(1a, 2a, 3a, 4a~c, 5a~b)가 배지로 붙어 있음
- `약 정보 앱 프로토타입.dc.html` — 동작하는 프로토타입 (상태 로직 포함). 인터랙션 동작의 기준

## Fidelity
**High-fidelity.** 색상·타이포·간격·radius 모두 최종값. 픽셀 수준으로 따라 구현하세요.
단, 아이콘은 Tabler Icons webfont(CDN: `@tabler/icons-webfont`)를 사용했습니다. 주의: `ti-capsule` 글리프는 최신 CDN 폰트에 없음 → `ti-pills` 사용.

## Design Tokens

### Colors
```css
:root {
  /* Brand */
  --blue-600: #1B6FD8;   /* primary — 버튼, 활성 상태, 링크 */
  --blue-100: #EAF2FD;   /* primary tint — 활성 nav bg, 아이콘 타일 */
  --blue-50:  #F4F9FF;   /* 선택된 행/슬롯 bg */
  --blue-200: #DCE9F8;   /* 아바타 bg, 차트 비활성 바 */
  --blue-300: #BBD6F5;

  /* Teal (보조 — 영양제/성공) */
  --teal-600: #0E9488;
  --teal-100: #E6F6F3;

  /* Amber (재처방/주의 — 빨강 대신 사용) */
  --amber-600: #C77E1D;
  --amber-100: #FDF6EA;
  --amber-border: #F3E3C2;
  --amber-text: #9B7B3C;

  /* Red (상호작용 경고 전용) */
  --red-600: #D6604D;
  --red-text: #9B3A2B;  /* #B0432F 배지 텍스트 */
  --red-100: #FDF1EE;
  --red-border: #F2CFC5;
  --red-row-bg: #FFFBFA; /* 경고 행 배경 */

  /* Neutrals */
  --navy-900: #14304C;   /* 제목, 본문 강조 */
  --slate-700: #3D5A76;  /* 보조 버튼 텍스트 */
  --slate-500: #5C7186;  /* 본문 보조 */
  --slate-400: #8AA0B5;  /* 캡션, 라벨 */
  --slate-300: #9AAEC0;  /* placeholder, 비활성 아이콘 */
  --border: #E5EBF2;     /* 카드 테두리 */
  --border-strong: #DCE5EE; /* 버튼/인풋 테두리 */
  --divider: #F0F4F9;    /* 행 구분선 */
  --bg: #F6F8FB;         /* 페이지 배경 */
  --card-header-bg: #F8FBFF; /* 펼친 그룹 헤더 */
  --tabbar-border: #EDF1F6;
  --disabled: #B9CDE4;   /* 비활성 CTA */
}
```

### Typography
- 폰트: `-apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Pretendard", sans-serif` + `word-break: keep-all` (한국어 줄바꿈)
- 페이지 제목: 22px / 700 / letter-spacing -0.3px / navy-900
- 카드 제목: 14–15px / 700
- 본문: 13–13.5px / 400–600
- 캡션·라벨: 11–12px / slate-400
- 배지: 10.5–12px / 600–700
- 모바일 제목: 19px / 700

### Spacing & Radius
- 페이지 패딩: 28px 32px (데스크톱), 16–20px (모바일)
- 카드 간격: 14–16px, 카드 내부 패딩: 20–24px
- Radius: 카드 16px · 버튼/인풋 10–11px · 아이콘 타일 10–13px · 칩 6–8px · 필터 칩 pill(20px) · 모바일 카드 18px
- 그림자: `0 1px 3px rgba(20,48,76,.04)` (카드) / 포커스 링: `0 0 0 3px rgba(27,111,216,.1)` + `1.5px solid var(--blue-600)`

## Screens / Views

### 1. 앱 셸
- **데스크톱**: 좌측 사이드바 216px 고정(white, 우측 border). 로고(32px 블루 타일 + "약 정보"), nav 항목(대시보드/약장/검색/공유/설정 — 아이콘 17px + 13.5px 텍스트, 활성: blue-100 bg + blue-600 + 600 weight, radius 10px, padding 10px 12px), 하단 계정 카드
- **모바일 (≤768px)**: 사이드바 제거 → **하단 탭바** (현재 코드는 사이드바를 display:none만 해서 내비가 사라짐 — 반드시 탭바로 교체). 구성: 홈/약장/[+추가 FAB]/검색/내 정보. 탭 아이콘 22px + 10px 라벨, 활성 blue-600 + 700. 중앙 FAB: 48px 원형 blue-600, `margin-top:-18px`로 탭바 위로 돌출, `box-shadow: 0 6px 14px rgba(27,111,216,.35)`. 탭바: white bg, 상단 border, padding 8px 8px 24px(safe-area)

### 2. 대시보드 (시안 1a / 모바일 1c)
- 헤더: 날짜(13px slate-400) + "안녕하세요, 오늘의 복약이에요"(22px) / 우측: 약 검색(보조) + 처방 추가(primary) 버튼
- 그리드: `1fr 340px` gap 16px
- **히어로 카드**: SVG 진행 링 108px (r=46, stroke 10, 트랙 blue-100, 진행 blue-600, `stroke-dasharray:289; stroke-dashoffset:289*(1-완료/전체)`, 중앙에 "1/3" 26px 700) + 우측 안내 문구("저녁 약 2건이 남았어요" 16px 700 + 다음 복용 시간 13px). 아래에 약별 복용 체크 행
- **복용 체크 행**: 아이콘 타일 40px + 약 이름 14px 600 + 출처·용법 12px + 우측 시간 슬롯 버튼들
- **시간 슬롯 버튼 (핵심 컴포넌트)**: 52×44px, radius 10px. 상태 3가지 —
  - 완료: blue-600 bg, white, 체크 아이콘 + 라벨
  - 예정(비활성): 1.5px solid border-strong, slate-500
  - 다음 복용(강조): 1.5px **dashed** blue-600, blue-50 bg, blue-600 700, 시계 아이콘
  - 클릭 시 완료 토글. 모바일에선 flex:1로 늘려 높이 48px
- **우측 컬럼**: ① 재처방 임박 카드 — amber-100 박스, 약 이름 + 날짜, "D-3" 배지(amber-600 bg, white). 절대 빨강/pulse 애니메이션 쓰지 않기 ② 주간 순응도 바 차트 — 바 7개, 과거 blue-200/오늘 blue-600, radius 5px, 높이 72px, 요일 라벨 11px (오늘만 blue 700). **바 최소 높이 6% 보장** (0%일 때 안 보이는 기존 버그 수정) ③ 통계 3칸: 처방전 수/등록된 약/순응도%

### 3. 약장 (시안 2a 일반인 / 3a 전문가 / 모바일 1d)
- 헤더: "내 약장" + 일반인/전문가 세그먼트 토글(bg #EFF3F8 radius 10px, 선택: white bg + blue + shadow) + 처방 추가 버튼
- 필터: 검색 인풋 + 칩(전체/복용 중/재처방 임박/영양제/종료됨 — pill형, 선택 blue-600 bg white)
- **처방 그룹 카드**: 병원 단위로 묶음. 헤더(클릭으로 접기/펼치기): 40px 컬러 타일(병원 blue-600/teal-600, 영양제 회색) + 병원명 15px 700 + 메타(진료일·일수·약 개수) + 상태 배지(재처방 D-3: amber / 복용 중: teal) + 공유·수정·셰브론 아이콘 버튼(34px, border). 펼치면 헤더 bg #F8FBFF
- **일반인 표 컬럼**: 약 이름(아이콘+성분 서브라인) | 1회 용량 | 복용 시간(칩: blue-100 bg blue-600) | 복용법 | 기간 | 상세 보기 버튼
- **전문가 표 컬럼**: 약 이름(+EDI 코드 모노스페이스 10.5px) | 성분/함량(+1일 최대량) | 분류 배지 | 용법 | 상호작용 | 상세
  - 상호작용 셀: 문제 있으면 "⚠ 성분 중복 N" 배지(red-100 bg red-border), 해당 행 배경 #FFFBFA. 없으면 "없음" 회색 배지
  - 그룹 상단에 **상호작용 경고 배너**: red-100 bg, 36px red-600 아이콘 타일, "A ↔ B — 성분 중복, 용량 초과 위험" + 상세 확인 버튼
  - 그룹 푸터: 성분 일일 합산 게이지 (예: "아세트아미노펜 일일 합산 **2,400 / 4,000mg**" + 진행 바 120px)
- **모바일**: 표 금지 → 약 행을 리스트로, 용법 정보는 **칩**으로 표시("1정 ×3회" blue 칩 + "아침·점심·저녁", "식후 30분 · 5일" 회색 칩). 그룹 카드 접기/펼치기 유지, 카드 하단 공유/수정 버튼 2분할

### 4. 처방 추가 폼 (시안 2b 데스크톱 / 4b·5b 모바일)
현재의 1400px 표 형태 폼을 **2단계 스텝 폼**으로 교체. 데스크톱은 중앙 720px 컬럼, 모바일은 풀스크린.
- 스텝 인디케이터: 24px 원형 번호 + 라벨 (활성 blue-600). 모바일은 상단 프로그레스 바 2분할(4px)
- **스텝 1 — 처방 정보**: 병원·약국 이름*(텍스트, 모바일은 최근 병원 칩 제안), 진료일*(date), 처방 일수(3일/5일/7일/직접 프리셋 칩 — 선택: 1.5px blue border + blue-50 bg), 재처방 알림 토글(40×24 스위치, "종료 3일 전 알림")
- **스텝 2 — 약 목록**: 약별 카드 방식
  - 추가된 약 카드: bg #FAFCFE, 아이콘 + 이름 + "✓ 의약품 DB에서 확인됨 · 성분"(teal) + X 제거 버튼. 시간 칩 토글(아침/점심/저녁/취침 전 — 선택 blue-600 bg white), 용량 스테퍼(- 1정 +), 복용법 셀렉트
  - 약 검색 카드(포커스 상태): 1.5px blue border + 포커스 링, 아래 자동완성 리스트(첫 항목 하이라이트 + "선택", 마지막에 "직접 입력으로 추가")
  - "약 추가하기" 버튼: 1.5px dashed #B9CDE4, bg #F8FBFF, blue 텍스트
- 하단: 취소(좌) / "임시 저장됨" 상태 + 저장 CTA(우). 필수값 없으면 CTA 비활성(#B9CDE4). 모바일 CTA는 하단 고정, 높이 52px+
- 저장 시 약장으로 이동 + 새 그룹이 펼쳐진 상태로 표시 + 토스트

### 5. 약 검색 (시안 4c 데스크톱 / 5a 모바일)
- 검색 인풋(포커스: blue border + 링) + 결과 수 필터 칩(전체 12/일반의약품 8/전문의약품 4)
- 그리드 `1fr 380px`: 좌 결과 리스트 / 우 미리보기 패널
- 결과 행: 아이콘 타일 40px + 이름(검색어 부분 blue 하이라이트) + 성분·제조사 + 배지들 — **"✓ 내 약장에 있음"**(teal) 배지가 핵심, 전문의약품은 amber 배지. 선택 행: blue-50 bg + 좌측 3px blue border
- 미리보기 패널: 약 정보 + 낱알 식별(모양·각인) + 효능/용법 + **약장 연동 상호작용 경고**("내 약장의 판콜에이내복액과 성분이 중복돼요") + 전체 정보/약장에 추가 버튼
- 결과 없음 상태: 아이콘 + "'검색어'에 대한 결과가 없어요" 필수
- **모바일**: 결과 행 탭 → **바텀시트** (radius 22px 상단, 드래그 핸들 40×4px, 딤 rgba(20,48,76,.4)), 동일 내용 + 버튼 2개

### 6. 약 상세 패널 (시안 4a)
- 우측 슬라이드오버 440–460px, 딤 배경(클릭 시 닫힘), 애니메이션: translateX 40px→0, 0.25s ease-out
- 헤더: 48px 아이콘 타일 + 이름 17px 700 + 성분·분류 + X 버튼 / 낱알 식별 박스(알약 모양 미니 렌더 + "흰색 장방형 정제 · 각인 TYLENOL 500")
- 본문: 상호작용 경고(있을 때) → 복용 정보 2×2 그리드(bg-100 셀: 1회 용량/시간/복용법/기간) → 효능·효과 → 주의사항(amber 아이콘 + 텍스트 리스트) → 부작용 아코디언
- 푸터: 복용 기록(보조) / 수정하기(primary)

## Interactions & Behavior
- 복용 슬롯 클릭 → 토글 + 진행 링/순응도/히어로 문구 즉시 갱신 (`transition: stroke-dashoffset .4s`)
- 그룹 카드 헤더 클릭 → 접기/펼치기 (셰브론 방향 전환)
- 일반인↔전문가 토글 → 표 컬럼 세트 + 경고 배너/배지 표시 전환
- 검색: 입력마다 실시간 필터 (이름 + 성분 매칭)
- 폼 검증: 병원 이름 비면 다음 버튼 비활성 + 클릭 시 토스트 안내
- 토스트: 하단 중앙, navy-900 bg, white 13px, radius 12px, 2.2초 후 자동 소멸, 등장 애니메이션 translateY(16px)→0 0.25s
- 슬라이드오버/바텀시트: 딤 클릭으로 닫힘
- 모든 터치 타깃 ≥44px (모바일)

## State Management
프로토타입 기준 (vanilla JS면 전역 state 객체 + render 함수로 충분):
- `screen`: 'dashboard' | 'cabinet' | 'search' | 'add'
- `doses`: { [slotId]: boolean } — 오늘 복용 기록 (기존 localStorage 연동 유지)
- `expert`: boolean — 약장 뷰 모드
- `openGroups`: { [groupId]: boolean }
- `query`, `selected` — 검색
- `form`: { step, hospital, date, days, alarm, drugs: [{id, name, times[], dose, method}] }
- `detail`: drugId | null — 슬라이드오버
- 상호작용 감지: 약장 전체에서 성분(성분코드) 중복 검사 → 경고 배너/배지/합산 게이지 데이터

## Assets
- 아이콘: [Tabler Icons](https://tabler.io/icons) webfont — `https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css`
  - 사용 글리프: ti-pill, ti-pills(캡슐 대용 — **ti-capsule은 폰트에 없음**), ti-bottle, ti-layout-dashboard, ti-search, ti-share, ti-settings, ti-plus, ti-x, ti-check, ti-clock, ti-bell, ti-chart-bar, ti-building-hospital, ti-leaf, ti-pencil, ti-chevron-up/down/right, ti-alert-triangle, ti-alert-circle, ti-circle-check, ti-calendar, ti-arrow-left/right, ti-user, ti-history, ti-flask, ti-download, ti-stethoscope
- 이미지 에셋 없음. 낱알 식별 비주얼은 CSS로 그린 알약 모양(pill 모양 div + 각인 텍스트)

## Files
- `약 정보 앱 리디자인.dc.html` — 정적 목업 전체 (턴별 시안: 1a 대시보드, 1c/1d 모바일, 2a 약장, 2b 폼, 3a 전문가 뷰, 4a 상세, 4b 모바일 폼, 4c 검색, 5a 모바일 검색, 5b 모바일 폼 스텝2)
- `약 정보 앱 프로토타입.dc.html` — 동작 프로토타입. 하단 `<script data-dc-script>`의 `Component` 클래스에 전체 상태 로직·스타일 함수·목데이터(DB 객체)가 있음 — 구현 시 그대로 참고 가능

## 기존 코드 관련 수정 권고 (디자인 외)
- 768px 이하에서 사이드바 display:none만 하고 대체 내비 없음 → 탭바 필수
- `drug-table` 모바일 가로 깨짐 → 카드/리스트 전환
- 순응도 차트 바 높이 0px 문제 → 최소 높이
- 인라인 `onclick` + innerHTML에 약 이름 삽입 → 따옴표 이스케이프 취약, addEventListener + textContent 권장
- D-day 빨강 pulse → amber 정적 배지로 교체
