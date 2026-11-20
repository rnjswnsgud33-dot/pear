# Fear Score — 비트코인 시장 공포 대시보드

트레이딩뷰 없이 휴대폰/PC 웹 브라우저에서 보는 복합 시장 공포지수 사이트입니다. **원본 Fundstrat 공식 지표가 아닌 비공식 재구성**입니다.

## 자동 갱신되는 데이터

- **VIX**: Cboe 공식 일별 종가. https://www.cboe.com/tradable_products/vix/vix_historical_data/
- **MOVE**: Yahoo Finance를 통해 조회하는 ICE BofA MOVE 일별 가격(`^MOVE`). https://finance.yahoo.com/quote/%5EMOVE/
- **HY OAS**: FRED `BAMLH0A0HYM2` (ICE BofA US High Yield Index OAS). https://fred.stlouisfed.org/series/BAMLH0A0HYM2
- **BTC**: Yahoo Finance `BTC-USD` 일별 종가. https://finance.yahoo.com/quote/BTC-USD/

공포지수 = 세 지표 각각의 Z점수 평균. 기준 통계는 **2020-01-01~2026-11-30 (실제로 확보된 거래일만)** 자료로 계산하며, 해당 기간이 아직 끝나지 않았으면 수집 가능한 최신 거래일까지의 표본으로 계산합니다. 2026-11-30 이후에는 표준화 기준 기간이 고정됩니다.

### 정확성 주의

- 원본 분석의 비공개 산출 세부사항, 가격 출처·시간대, 누락값 처리 등이 다르면 원본 +0.31, +1.5 돌파일 수와 값이 다를 수 있습니다. 원본의 정확한 복제라고 주장하지 않습니다.
- **진짜 실시간/초 단위 아님:** 원천 지표는 대부분 일별 데이터이며 HY OAS에는 발표 지연이 있을 수 있습니다.
- 해당 일자의 OAS가 없을 때는 최근 7일 이내 값으로 보충, MOVE는 최근 4일 이내, BTC는 최근 3일 이내 값으로 보충합니다. 데이터 부족 시 해당 거래일을 제외합니다.
- ICE MOVE는 라이선스 대상 지표입니다. 공개 서비스/재배포 전에 데이터 이용약관을 확인하세요. 무료 Yahoo 조회는 언제든 제한되거나 막힐 수 있습니다.
- 데이터 수집에 실패하면 갱신 과정이 오류로 종료되며, GitHub Pages에 이전에 배포된 자료가 남습니다. 사이트에서는 마지막 유효 날짜가 7일 이상 지나면 **오래된 데이터 경고**가 표시됩니다.

## 가장 쉬운 배포 방법 — GitHub Pages (무료 공개 저장소)

1. [github.com/new](https://github.com/new)에서 `fear-score` 이름으로 **Public** 저장소를 만듭니다. 다른 이름도 가능.
2. 이 ZIP 압축을 풀고, 그 안의 **파일 및 폴더 전체**를 저장소에 올립니다. **.github** 폴더까지 반드시 업로드해야 합니다. GitHub의 **Add file → Upload files**를 사용하면 됩니다. 기본 브랜치 이름은 **main**으로 둡니다.
3. 저장소 **Settings → Pages → Build and deployment → Source**에서 **GitHub Actions**를 선택합니다.
4. 저장소 **Actions → Refresh Fear Data & Deploy → Run workflow**를 한 번 실행합니다. 첫 업로드 시 자동 실행될 수도 있습니다.
5. Actions가 정상 종료되면 **Settings → Pages**에 사이트 주소가 나타납니다. 대개 `https://<GitHub아이디>.github.io/fear-score/` 형태입니다.
6. 이후 GitHub Actions가 미국 시장 영업일에 맞춰 하루 1~2회 자동으로 데이터를 받아 사이트를 갱신합니다. GitHub 스케줄 실행은 지연되거나 비활성화될 수 있으며, 데이터 제공사의 전송 주기와 다를 수 있습니다.

**주의:** 여기서 바로 공개 사이트 도메인을 만들어 둔 상태는 아닙니다. 사이트 코드와 자동 갱신 시스템을 제공하는 것이고, 위 단계로 사용자 GitHub 계정에 배포해야 공개 주소가 생깁니다.

## 내 PC에서 실행하기 (GitHub 없어도 가능)

Python 3.12+ 설치 후 압축을 푼 폴더에서:

```bash
pip install -r requirements.txt
python scripts/update_data.py
python -m http.server 8000 --directory site
```

웹 브라우저에서 `http://localhost:8000`에 접속합니다. 한 번 생성된 `site/data.js` 파일은 해당 PC에서 오프라인 열람도 가능합니다. 새 데이터를 반영하려면 다시 `python scripts/update_data.py`를 실행합니다. 자동 갱신은 GitHub Actions 배포 시 적용됩니다.

## 구성

```
site/index.html                       사이트 화면 (휴대폰 최적화)
site/data.js                          빌드 시 자동 생성되는 차트 데이터 (초기에는 비어 있음)
site/assets/fundstrat-reference.jpg  사용자가 준 원본 차트 이미지
scripts/update_data.py               VIX·MOVE·HY OAS·BTC 자동 수집/계산
.github/workflows/update-and-deploy.yml  GitHub Pages 자동 배포
requirements.txt                      Python 의존성
```

## 장애 대응

- `^MOVE`/`BTC-USD` Yahoo 제한(429): 잠시 뒤 Actions의 **Run workflow**로 재실행해 보세요. 계속 실패하면 유료/허가된 MOVE 데이터 제공처가 필요할 수 있습니다.
- 403/FRED: 원천 제공사의 일시적 제한 가능성. 공개 사이트 배포가 아니라, PC에서 실행해 보는 것을 시도할 수 있습니다.
- 페이지가 빈 화면: 개발자 콘솔에서 오류를 확인하거나 `data.js`가 유효한지 확인하세요. 수집 미실행이면 원본 차트 이미지를 볼 수 있습니다.

**이 사이트는 투자 조언을 제공하지 않습니다.**
