import re

def extract_chunks(text, keyword):
    # 조사 제거: '지방법원을' -> '지방법원'
    match = re.search(rf"(\w*{keyword})", text)
    return match.group(1) if match else None

def parse_and_generate_amendments(xml_path, search_word, replace_word):
    # 더미 로직: 실제로는 xml.etree.ElementTree로 파싱해야 함
    dummy_hits = [
        ("제1조제1항", "관할지방법원"),
        ("제3조제2항", "관할지방법원"),
        ("제5조", "관할지방법원"),
        ("제7조제1항", "지방법원판사"),
        ("제10조제1항", "관할지방법원"),
        ("제13조제1항", "지방법원판사"),
        ("제20조제1항", "관할지방법원"),
    ]

    result_lines = ["① OO법 일부를 다음과 같이 개정한다."]
    current_chunk = None
    current_locations = []

    for loc, chunk in dummy_hits:
        if chunk != current_chunk:
            if current_chunk:
                each_or_not = "각각 " if len(current_locations) > 1 else ""
                result_lines.append(
                    f"{', '.join(current_locations)} 중 "{current_chunk}"을 {each_or_not}"{current_chunk.replace(search_word, replace_word)}"으로 한다."
                )
            current_chunk = chunk
            current_locations = [loc]
        else:
            current_locations.append(loc)

    # 마지막 덩어리 처리
    if current_chunk and current_locations:
        each_or_not = "각각 " if len(current_locations) > 1 else ""
        result_lines.append(
            f"{', '.join(current_locations)} 중 "{current_chunk}"을 {each_or_not}"{current_chunk.replace(search_word, replace_word)}"으로 한다."
        )

    return "\n".join(result_lines)
# XML parsing and article extraction logic
