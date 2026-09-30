# 무료 클라우드 재입고 감시

GitHub Actions가 5분 간격으로 네이버 상품 페이지를 Chromium으로 확인하고, 품절에서 구매 가능으로 바뀌면 ntfy Android 앱으로 푸시 알림을 보냅니다. 감시가 설정된 뒤에는 PC를 켜둘 필요가 없습니다.

## 휴대폰만으로 설정하기

1. Android에 ntfy 앱을 설치합니다: https://play.google.com/store/apps/details?id=io.heckel.ntfy
2. 휴대폰의 비밀번호 관리자나 오프라인 난수 생성기로 영문·숫자 조합의 예측하기 어려운 32자 주제명을 만듭니다. 이 주제명은 알림을 받을 수 있는 비밀 주소이므로 채팅이나 공개 저장소에 올리지 않습니다.
3. ntfy 앱에서 새 구독을 만들고 주제명을 등록합니다.
4. 휴대폰 브라우저에서 GitHub에 로그인하고 새 공개 저장소를 만듭니다.
5. 이 ZIP을 휴대폰 파일 앱에서 압축 해제합니다. 저장소에 README.md, monitor.py, monitor_state.json, requirements.txt를 올립니다.
6. 워크플로 파일은 GitHub에서 Add file → Create new file을 선택하고 파일 이름에 아래 경로를 입력합니다. 압축 해제한 .github/workflows/check-restock.yml 파일의 내용을 복사해 붙여넣습니다.

       .github/workflows/check-restock.yml

   모바일 화면에서 경로 입력이나 편집이 불편하면 브라우저 메뉴에서 데스크톱 사이트 보기를 켭니다.
7. GitHub 저장소의 Settings → Secrets and variables → Actions → New repository secret에서 이름을 NTFY_TOPIC으로 하고 2단계 주제명을 값으로 저장합니다.
8. Actions 탭에서 SmartStore restock check를 열어 Run workflow를 한 번 실행합니다. 연결 확인 알림이 휴대폰에 오면 설정이 된 것입니다.

## 무료 사용 조건과 공개 범위

표준 GitHub-hosted runner 사용은 공개 저장소에서 무료입니다. 그래서 저장소를 공개로 만들어야 무료로 계속 실행할 수 있습니다. 저장소 안의 코드, 상품 URL, 감시 상태 파일은 공개됩니다. 알림 주제명은 코드에 넣지 않고 GitHub Actions Secret에만 저장합니다.

예약 실행의 최단 간격은 5분입니다. GitHub 사용량이 몰리면 실행이 늦어지거나 누락될 수 있어 정확히 5분 간격을 보장하지는 않습니다.

## 동작과 제한

- 기본 감시 대상은 Panasonic Korea 스마트스토어 상품입니다.
- 구매 버튼이나 품절 문구를 읽지 못하면 오탐을 피하기 위해 재입고 알림을 보내지 않습니다. 실행 결과는 Actions 탭의 해당 실행 로그에서 확인합니다.
- 첫 실행에서 페이지가 상품이 없다고 표시하거나 네이버가 접근을 거부하면 GitHub runner에서도 재고를 읽지 못할 수 있습니다.
- 색상·사이즈 등 옵션이 있는 상품은 특정 옵션을 자동으로 선택하지 않습니다.
- 상품 URL과 알림 문구는 ntfy.sh로 전송됩니다.
- 감시기는 재고만 확인하고 자동 구매는 하지 않습니다.
