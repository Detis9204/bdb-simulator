# 빌디바이드 브라이트 카드 대전 연습 시뮬레이터

친구들과 대회 연습용으로만 쓰는 개인 프로젝트예요. 카드 이미지와 텍스트의 저작권은 각 권리자에게 있으므로 **이 저장소는 비공개로 유지**합니다.

- 규칙: 빌디바이드 총합 규칙 Ver.6.10.0 (빌디바이드/브라이트 공통) 중 브라이트 카드 기준
- 게시된 페이지(온라인 대전 가능): GitHub Pages 또는 claude.ai 아티팩트

## GitHub Pages로 게시하기

`main`에 올리면 `.github/workflows/pages.yml`이 카드 이미지 묶음을 만들고 `simulator/`와 함께 Pages에 게시해요.

1. 저장소 **Settings → Pages → Build and deployment → Source**를 **GitHub Actions**로 바꿔요 (처음 한 번).
2. **Actions** 탭에서 `Pages` 작업이 끝나면 `https://bdb-simulator.github.io/`에서 열려요.
3. 비공개 저장소의 Pages는 GitHub Pro 이상 요금제에서만 켤 수 있어요.

claude.ai 밖에서는 온라인 대전이 PeerJS(브라우저끼리 직접 연결)로 동작해요. 로그인이나 초대 없이 같은 주소를 열고 방 코드만 알려 주면 돼요. 연결 중개는 PeerJS 공개 서버가 하고, 게임 데이터는 두 브라우저가 직접 주고받아요. 회사망처럼 방화벽이 엄격한 곳에서는 연결이 안 될 수 있어요.

## 폴더

| 폴더 | 내용 |
|---|---|
| `simulator/` | 시뮬레이터 (HTML 한 파일: 규칙 엔진 + 화면 + 온라인 동기화) |
| `collector/` | 공식 사이트 카드 수집 스크립트 |
| `data/` | 수집한 카드 데이터 (카드 상세 원문, 필터별 태그, 이미지 주소, PhotoCraft 명령 목록) |
| `db/` | 카드 효과 번역 DB (일본어·한국어) |
| `images/` | 크기를 줄인 카드 이미지 (2단계에서 추가) |
| `tests/` | 자동 검증 (무작위 대전, 재현성, 온라인 2기기 동기화(claude.ai·PeerJS), 화면 클릭) |

## 카드 수집 (PC에서)

```powershell
python collector/bdb_collect.py
git add data
git commit -m "카드 데이터 수집"
git push
```

- 처음 한 번은 수십 분 걸릴 수 있어요. 끊겨도 다시 실행하면 이어서 받아요.
- 이미지 원본은 `images_raw/`에 저장되고 git에는 올라가지 않아요.

## 카드 정리 (수집 후)

```powershell
python collector/bdb_parse.py     # data/cards/*.json → data/cards.json (시뮬레이터가 쓰는 정리본)
```

## 카드 이미지 (PC에서, PhotoCraft 사용)

```powershell
python collector/bdb_images.py
git add images data
git commit -m "카드 이미지"
git push
```

- 공식 썸네일과 테리토리 뒷면을 받고, PhotoCraft(`image.imageSize`)로 가로 240px WebP로 줄여 `images/`에 저장해요.
- 매개변수는 PhotoCraft에서 직접 조회하고, 한 장으로 결과 크기를 확인한 뒤에만 전체에 적용해요.

## 테스트 (Node.js, jsdom 필요)

```powershell
cd tests
npm install jsdom@24
node sim.js        # 무작위 자동 대전 1,200판
node det.js        # 같은 시드 + 같은 행동 → 같은 게임 (온라인 동기화 전제)
node net.js 0.25   # 두 기기 온라인 대전, 메시지 25% 유실에서도 상태 일치
```
