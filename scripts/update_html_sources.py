"""docs/index.html의 PMTILES_SOURCES 블록을 자동 갱신.

deploy.sh가 호출. PMTILES_SOURCES_AUTO_BEGIN ~ END 마커 사이를
새 PMTiles 목록으로 교체.

사용:
  python3 scripts/update_html_sources.py docs/index.html 11110 11140 11680 ...
"""

import os
import re
import sys

SGG_NAMES = {
    '11110':'종로구','11140':'중구','11170':'용산구','11200':'성동구','11215':'광진구',
    '11230':'동대문구','11260':'중랑구','11290':'성북구','11305':'강북구','11320':'도봉구',
    '11350':'노원구','11380':'은평구','11410':'서대문구','11440':'마포구','11470':'양천구',
    '11500':'강서구','11530':'구로구','11545':'금천구','11560':'영등포구','11590':'동작구',
    '11620':'관악구','11650':'서초구','11680':'강남구','11710':'송파구','11740':'강동구',
}

MARKER_BEGIN = "// PMTILES_SOURCES_AUTO_BEGIN"
MARKER_END = "// PMTILES_SOURCES_AUTO_END"


def build_block(codes):
    """주어진 시군구 코드 리스트로 PMTILES_SOURCES JS 배열 생성."""
    lines = ["  " + MARKER_BEGIN, "  const PMTILES_SOURCES = ["]
    for code in codes:
        name = SGG_NAMES.get(code, code)
        # id는 시군구 코드, url은 same-origin 상대경로
        lines.append(f'    {{ id: "{code}", url: "./buildable_{code}.pmtiles", name: "{name}" }},')
    lines.append("  ];")
    lines.append("  " + MARKER_END)
    return "\n".join(lines)


def update_html(html_path, codes):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        re.escape(MARKER_BEGIN) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    new_block = build_block(codes).lstrip()  # 들여쓰기는 기존 라인에 맞춤

    if not pattern.search(content):
        raise RuntimeError(f"마커({MARKER_BEGIN} / {MARKER_END})를 찾을 수 없습니다: {html_path}")

    new_content = pattern.sub(new_block, content)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[update_html_sources] {html_path} 갱신 완료 ({len(codes)}개 구)")
    for code in codes:
        print(f"  - {code} ({SGG_NAMES.get(code, '?')})")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    html_path = sys.argv[1]
    codes = sys.argv[2:]
    if not os.path.isfile(html_path):
        print(f"[ERROR] HTML 파일 없음: {html_path}")
        sys.exit(1)
    update_html(html_path, codes)


if __name__ == "__main__":
    main()
