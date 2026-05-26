#!/usr/bin/env bash
# 자동 배포 파이프라인
#
# 동작:
#   1. data/_seoul_apt/result_geom/ 에서 .done 마커로 완료된 구 식별
#   2. 각 구별로 SHP -> GeoJSONL -> MVT -> PMTiles 생성
#   3. docs/buildable_{시군구코드}.pmtiles로 복사
#   4. docs/index.html의 PMTILES_SOURCES 블록 자동 갱신
#   5. git: 브랜치 생성, commit, push, PR 생성, 머지
#   6. GitHub Pages 빌드 완료 대기
#
# 사용:
#   ./scripts/deploy.sh                # 25개 모두 완료된 후
#   ./scripts/deploy.sh --partial      # 일부만 완료돼도 진행 (테스트용)
#   ./scripts/deploy.sh --skip-git     # PMTiles만 만들고 git 작업 안 함
#   ./scripts/deploy.sh --dry-run      # 실행 안 하고 계획만 출력

set -euo pipefail

# === 설정 ===
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULT_DIR="$REPO_ROOT/data/_seoul_apt/result_geom"
DOCS_DIR="$REPO_ROOT/docs"
HTML_PATH="$DOCS_DIR/index.html"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXPECTED_DISTRICTS=25
GITHUB_OWNER="969flash"
GITHUB_REPO="BuildableRegionGenrator"

ALLOW_PARTIAL=0
SKIP_GIT=0
DRY_RUN=0

# 인자 파싱
while [[ $# -gt 0 ]]; do
    case $1 in
        --partial) ALLOW_PARTIAL=1; shift ;;
        --skip-git) SKIP_GIT=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help)
            head -25 "$0" | tail -22 | sed 's/^# //; s/^#//'
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

cd "$REPO_ROOT"

# === 색상 출력 ===
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $*"; }
warn()  { echo -e "${YELLOW}[$(date +%H:%M:%S)] WARN:${NC} $*" >&2; }
fail()  { echo -e "${RED}[$(date +%H:%M:%S)] FAIL:${NC} $*" >&2; exit 1; }

# === 의존성 체크 ===
for cmd in tippecanoe pmtiles gh python3 git; do
    command -v "$cmd" >/dev/null || fail "필수 명령어 없음: $cmd"
done

# === 1. .done 마커로 완료 구 식별 ===
info "=== [1/6] 완료된 구 식별 ==="

if [ ! -d "$RESULT_DIR" ]; then
    fail "result 디렉토리 없음: $RESULT_DIR"
fi

shopt -s nullglob
DONE_FILES=("$RESULT_DIR"/*.done)
shopt -u nullglob
DONE_COUNT=${#DONE_FILES[@]}

if [ "$DONE_COUNT" -eq 0 ]; then
    fail "완료된 구 없음 (.done 마커 0개). GH 시뮬레이션 먼저 끝내세요."
fi

info "완료: $DONE_COUNT / $EXPECTED_DISTRICTS"
if [ "$DONE_COUNT" -lt "$EXPECTED_DISTRICTS" ] && [ "$ALLOW_PARTIAL" -eq 0 ]; then
    fail "25개 미만 완료. --partial 옵션으로 강제 진행 가능."
fi

# 시군구 코드 추출 (정렬)
CODES=()
for done_file in "${DONE_FILES[@]}"; do
    stem=$(basename "$done_file" .done)
    code=$(echo "$stem" | grep -oE 'D194_[0-9]+' | sed 's/D194_//')
    [ -n "$code" ] && CODES+=("$code")
done
# sort + uniq
IFS=$'\n' SORTED_CODES=($(printf "%s\n" "${CODES[@]}" | sort -u))
unset IFS

info "처리 대상: ${SORTED_CODES[*]}"

if [ "$DRY_RUN" -eq 1 ]; then
    info "[DRY RUN] 여기서 종료. 실제 빌드 안 함."
    exit 0
fi

# === 2. 각 구별 PMTiles 생성 ===
info "=== [2/6] PMTiles 생성 (${#SORTED_CODES[@]}개 구) ==="

TEMP_DIR=$(mktemp -d -t deploy_pmtiles_XXX)
trap "rm -rf $TEMP_DIR" EXIT

SUCCESS_CODES=()
FAIL_CODES=()

for code in "${SORTED_CODES[@]}"; do
    info "  >> $code 시작"

    # 단일 구 GeoJSONL
    GEOJSONL="$TEMP_DIR/${code}.geojsonl"
    if ! python3 scripts/shp_to_geojsonl.py "$RESULT_DIR" \
            --district "$code" --output "$GEOJSONL" 2>&1 | tail -5; then
        warn "  $code GeoJSONL 실패, 건너뜀"
        FAIL_CODES+=("$code")
        continue
    fi
    if [ ! -s "$GEOJSONL" ]; then
        warn "  $code GeoJSONL 비어있음, 건너뜀"
        FAIL_CODES+=("$code")
        continue
    fi

    # Tippecanoe -> mbtiles
    MBTILES="$TEMP_DIR/${code}.mbtiles"
    if ! tippecanoe -o "$MBTILES" \
            --layer=buildable \
            --minimum-zoom=10 --maximum-zoom=16 \
            --drop-densest-as-needed --extend-zooms-if-still-dropping \
            --force \
            --quiet \
            "$GEOJSONL" 2>&1 | tail -3; then
        warn "  $code tippecanoe 실패, 건너뜀"
        FAIL_CODES+=("$code")
        continue
    fi

    # PMTiles
    OUT_PMTILES="$DOCS_DIR/buildable_${code}.pmtiles"
    if ! pmtiles convert "$MBTILES" "$OUT_PMTILES" 2>&1 | tail -2; then
        warn "  $code pmtiles convert 실패, 건너뜀"
        FAIL_CODES+=("$code")
        continue
    fi

    SIZE_MB=$(du -m "$OUT_PMTILES" | cut -f1)
    if [ "$SIZE_MB" -gt 95 ]; then
        warn "  $code PMTiles ${SIZE_MB}MB - GitHub 100MB 한계 근접!"
    fi
    info "  $code 완료 (${SIZE_MB} MB)"
    SUCCESS_CODES+=("$code")
done

info "PMTiles 생성: 성공 ${#SUCCESS_CODES[@]}개, 실패 ${#FAIL_CODES[@]}개"
[ ${#FAIL_CODES[@]} -gt 0 ] && warn "실패: ${FAIL_CODES[*]}"

if [ ${#SUCCESS_CODES[@]} -eq 0 ]; then
    fail "성공한 PMTiles가 없습니다."
fi

# === 3. 옛 단일 PMTiles 정리 ===
info "=== [3/6] 옛 buildable_gangnam.pmtiles 정리 ==="
# 새 11680 (강남구)가 생성됐으면 옛 이름 제거
if [ -f "$DOCS_DIR/buildable_gangnam.pmtiles" ] && [[ " ${SUCCESS_CODES[*]} " == *" 11680 "* ]]; then
    rm "$DOCS_DIR/buildable_gangnam.pmtiles"
    info "  buildable_gangnam.pmtiles 제거 (이제 buildable_11680.pmtiles)"
else
    info "  유지 또는 미생성 (skip)"
fi

# === 4. HTML 갱신 ===
info "=== [4/6] index.html 갱신 ==="
python3 scripts/update_html_sources.py "$HTML_PATH" "${SUCCESS_CODES[@]}"

# === 5. Git 작업 ===
if [ "$SKIP_GIT" -eq 1 ]; then
    info "=== [5/6] git 건너뜀 (--skip-git) ==="
    info "로컬 확인: open $HTML_PATH"
    exit 0
fi

info "=== [5/6] Git: branch + commit + push + PR + merge ==="

BRANCH="release/seoul-${TIMESTAMP}"
git checkout main >/dev/null
git pull >/dev/null
git checkout -b "$BRANCH" >/dev/null
info "  브랜치: $BRANCH"

git add docs/

if git diff --cached --quiet; then
    warn "  변경사항 없음. main으로 복귀."
    git checkout main >/dev/null
    git branch -D "$BRANCH" >/dev/null
    exit 0
fi

COMMIT_MSG="자동 배포: 서울 ${#SUCCESS_CODES[@]}구 PMTiles (${TIMESTAMP})

처리 구: ${SUCCESS_CODES[*]}
실패: ${FAIL_CODES[*]:-없음}

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"

git commit -m "$COMMIT_MSG" >/dev/null
git push -u origin "$BRANCH" >/dev/null
info "  push 완료"

PR_URL=$(gh pr create \
    --title "자동 배포: 서울 ${#SUCCESS_CODES[@]}구 (${TIMESTAMP})" \
    --body "scripts/deploy.sh 자동 생성 PR." \
    | tail -1)
info "  PR: $PR_URL"

gh pr merge --squash --delete-branch >/dev/null
info "  머지 완료"

git checkout main >/dev/null
git pull >/dev/null

# === 6. GitHub Pages 빌드 대기 ===
info "=== [6/6] Pages 빌드 대기 ==="
PAGES_URL="https://${GITHUB_OWNER}.github.io/${GITHUB_REPO}/"

for i in $(seq 1 24); do  # 최대 6분
    STATUS=$(gh api "repos/${GITHUB_OWNER}/${GITHUB_REPO}/pages/builds/latest" --jq '.status' 2>&1 || echo "unknown")
    info "  [${i}] $STATUS"
    if [ "$STATUS" = "built" ]; then
        break
    fi
    sleep 15
done

# HTTP 200 확인
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$PAGES_URL" || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    info "=== ✅ 배포 완료 ==="
    info "🌐 $PAGES_URL"
    info "처리: ${#SUCCESS_CODES[@]}개 구, 실패: ${#FAIL_CODES[@]}개"
else
    warn "HTTP $HTTP_CODE -- 빌드는 됐지만 응답 이상. 잠시 후 확인 필요."
fi
