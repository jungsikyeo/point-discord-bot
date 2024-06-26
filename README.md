# Point Discord Bot
## # 개요
- 디스코드 유저들이 활동하면서 포인트를 얻고 마켓(스토어)을 통해 포인트로 경품 래플을 참여할 수 있도록 구현된 디스코드 봇 시스템

## # 전체 구조
### 1. 파일 구조 및 역할
```agsl
/point-discord-bot       // 포인트 봇 루트 폴더
├── .env                 // 전체 프로젝트 공통 환경설정 파일
├── .gitignore           // 이그노어 설정 파일
├── README.md            // 가이드 파일
├── db_pool.py           // DB Pool CLASS 파일
├── db_query.py          // DB Query 
├── lm                   // 프로젝트 폴더
│   ├── .env_lm          // 개별 프로젝트 환경설정 파일
│   ├── lottery_lm.py    // 로또 봇 디스코드 명령어 실행 파일
│   └── point_lm.py      // 포인트 봇 디스코드 명령어 실행 파일
├── lottery_main.py      // 로또 모듈 코어 파일
├── point_main.py        // 포인트 모듈 코어 파일
├── raffle.py            // 스토어 라운드 별 우승자 추첨 로직
└── requirements.txt     // 패키지 설치 버전
```

### 2. 동작 방식
- 루트 하위에 폴더별로 프로젝트를 관리
  - 현재는 LM(Leisure Meta) 프로젝트만 존재
  - 신규 프로젝트 발생 시 루트 폴더 하위에 새로운 폴더를 생성하는 구조
- 프로젝트 폴더 하위의 `.env_{폴더명}`은 해당 프로젝트에만 필요한 환경설정 정의
  - 설정파일은 `.env_{폴더명}`과 같이 네이밍 필요
    - 봇 구동 후 로깅 파일 생성 시 같은 네이밍 구조 사용
- 프로젝트 폴더 하위의 `{모듈}_{폴더명}.py`는 디스코드에서 실행될 명령어의 집합체
  - 실제 프로그래밍은 루트 하위의 `{모듈}_main.py`에 있는 메소드를 실행하여 동작

### 3. 실행
1. 프로젝트 폴더로 이동 (ex: lm)
```bash
$ cd point-discord-bot/lm
```
2. 모듈 별 디스코드 봇 구동(ex: point)
```bash
$ python point_lm.py &
```
3. 로그 확인 (봇 구동 시 point_lm.log 파일 자동 생성)
```bash
$ tail -f point_lm.log
```


## # 마켓 프로세스 및 사용법
### 1. 스토어 세팅
> **실행 명령어: !store-setting**
- 쇼핑을 하려면 스토어를 오픈해야 함
- 스토어 이름, 설명, 이미지 등을 설정 함
- 라운드 시작: 최초 1라운드부터 진행되고, `OPEN` 상태인 경우에만 상품 등록 및 구매가 가능
- 라운드 종료: 래플 당첨자를 추첨하면 해당 라운드가 자동으로 종료되어 `CLOSE`상태가 됨.
- 라운드 재설정: `!store-setting` 를 실행하여 다음 라운드로 설정 후 진행

### 2. 아이템 추가
> **실행 명령어: !add-item**
- `OPEN`된 라운드에 아이템을 등록하는 화면
- RAFFLE: 래플 상품 등록
- FCFS: 선착순 상품 등록
- 선착순 상품은 1개씩만 구매 가능하고 수량이 모두 판매되면 더이상 구매할 수 없음
- 래플 상품은 수량을 선택하여 당첨자 추첨 시 사용하는 티켓을 구매할 수 있음

### 3. 스토어 메인 오픈
> **실행 명령어: !store-main**
- 유저들이 상품을 구매하거나 본인이 구매한 티켓 확인 및 본인의 보유 포인트를 확인할 수 있는 화면

### 4. 당첨자 추첨
> **실행 명령어: !giveaway-raffle**
- 래플 티켓을 구매한 사람을 대상으로 상품 수량에 따른 당첨자를 추첨 함
- 당첨자 추첨이 되면 해당 라운드는 자동으로 `CLOSE` 됨 -> 1번 명령어로 다음 라운드 세팅 진행 필요


## # (옵션) 마켓 래플 자동 추첨 기능
### 1. 추첨 시간 설정
> **DB테이블: stores**
- 팀에서 결정한 시간을 개발자가 최초 한번 설정

### 2. 다음 추첨 주기 설정
> **실행 명령어: !set-auto-raffle-interval <실행 주기(시간)>**
- 실행 주기(시간)을 설정하면 설정한 시간 주기로 추첨 진행

### 3. 자동 추첨 시작
> **실헹 명령어: !start-auto-raffle**
- 자동 추첨 모드 시작
- 1, 2번에 설정대로 자동 추첨 됨

### 4. 자동 추첨 정지
> **실행 명령어: !stop-auto-raffle**
- 자동 추첨 모드 중지

### 자동 추첨 실행 프로세스 예제
1) 추첨 시간을 저녁 8시로 설정
2) 실행 주기를 336(24시간 x 2주)으로 설정
3) 자동 추첨 시작 명령어 실행
4) 현 시간이후 다음번 저녁 8시에 래플 추첨이 자동 실행
5) 래플 추첨 실행 후 2주 뒤 저녁 8시에 래플 추첨 자동 실행 (반복)
6) 자동 추첨 중지 명령어 실행 -> 자동 추첨 중단

## # 포인트 프로세스 및 사용법
### 1. 포인트 부여
> **실행 명령어: !give-rewards <유저 태그> <부여할 포인트>**
- 유저에게 포인트를 수동 부여 함

### 2. 포인트 회수
> **실행 명령어: !remove-rewards <유저 태그> <회수할 포인트>**
- 유저에게 포인트를 수동 회수 함

### 3. 출석체크 포인트 부여
> **실행 명령어: !today**
- 유저가 특정 채널에서 명령어 실행 후 포인트 셀프 부여
- 1일 1회 한정 (KST시간으로 00시에 초기화)


## # Level 포인트 프로세스 및 사용법
### 1. Level Role 조회 및 등록, 수정, 삭제
> **실행 명령어: !level-list**
- 조회: 등록된 Level Role 목록을 확인
- 등록: Level Role 및 포인트 추가 등록
- 수정: Level Role 및 포인트 수정
- 삭제: Level Role 삭제

### 2. Level, Point 초기화
> **실행 명령어: !level-reset**
- 유저에게 부여된 Level Role 제거 및 포인트 초기화 진행
- Level 포인트 부여 기능을 사용하기 전 최초 한번 초기화 필요 (유저에게 포인트를 부여하기 위한 시간대 비교군)
- 10000명마다 진행률 보여 줌

### 3. Level Point Claim
> **실행 명령어: !level-rewards**
- 유저가 보유한 Level Role에 대해 보상 포인트를 `Claim` 함
- 초기화 이후에 각 Role별로 1번만 `Claim` 가능

### 4. Role Point 부여
> **실행 명령어: !give-role-rewards <Role태그> <부여할 포인트>**
- 특정 Role을 가지고 있는 유저에게 포인트 부여
- 10000명마다 진행률 보여 줌


## # 유저 알파콜 프로세스 및 사용법
> **실행: 포인트 봇 실행 시 자동 시작**
- 특정 채널에서 유저들이 알파콜을 올리면 익일 오후5시(KST)에 포인트 부여


## # 로또 프로세스 및 사용법
> **실행 명령어: /lottery-setting** 
- 라운드 별 로또 게임 세팅

> **실행 명령어: /start-lottery**
- 로또 게임 라운드 오픈 및 티켓 구매

> **실행 명령어: /end-lottery <당첨번호1> <당첨번호2> <당첨번호3> <당첨번호4> <당첨번호5> <당첨번호6>**
- 로또 게임 라운드 종료 및 입력한 당첨번호에 따른 당첨자 확인