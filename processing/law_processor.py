import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import re
import os
from collections import defaultdict
import unicodedata

OC = os.getenv("OC", "chetera")
BASE = "http://www.law.go.kr"

def get_law_list_from_api(query):
    exact_query = f'"{query}"'
    encoded_query = quote(exact_query)
    page = 1
    laws = []
    while True:
        url = f"{BASE}/DRF/lawSearch.do?OC={OC}&target=law&type=XML&display=100&page={page}&search=2&knd=A0002&query={encoded_query}"
        res = requests.get(url, timeout=10)
        res.encoding = 'utf-8'
        if res.status_code != 200:
            break
        root = ET.fromstring(res.content)
        for law in root.findall("law"):
            laws.append({
                "법령명": law.findtext("법령명한글", "").strip(),
                "MST": law.findtext("법령일련번호", "")
            })
        total_count = int(root.findtext("totalCnt", "0"))
        if len(laws) >= total_count:
            break
        page += 1
    return laws

def get_law_text_by_mst(mst):
    url = f"{BASE}/DRF/lawService.do?OC={OC}&target=law&MST={mst}&type=XML"
    try:
        res = requests.get(url, timeout=10)
        res.encoding = 'utf-8'
        return res.content if res.status_code == 200 else None
    except:
        return None

def clean(text):
    return re.sub(r"\s+", "", text or "")

def 조사_을를(word):
    if not word:
        return "을"
    code = ord(word[-1]) - 0xAC00
    jong = code % 28
    return "를" if jong == 0 else "을"

def 조사_으로로(word):
    if not word:
        return "으로"
    code = ord(word[-1]) - 0xAC00
    jong = code % 28
    return "로" if jong == 0 or jong == 8 else "으로"

def normalize_number(text):
    try:
        return str(int(unicodedata.numeric(text)))
    except:
        return text

def extract_locations(xml_data, keyword):
    tree = ET.fromstring(xml_data)
    articles = tree.findall(".//조문단위")
    keyword_clean = clean(keyword)
    locations = []

    for article in articles:
        조번호 = article.findtext("조문번호", "").strip()
        조제목 = article.findtext("조문제목", "") or ""
        조내용 = article.findtext("조문내용", "") or ""

        if keyword_clean in clean(조제목):
            locations.append((조번호, None, None, None, 조제목.strip()))
        if keyword_clean in clean(조내용):
            locations.append((조번호, None, None, None, 조내용.strip()))

        for 항 in article.findall("항"):
            항번호 = normalize_number(항.findtext("항번호", "").strip())
            항내용 = 항.findtext("항내용") or ""
            has_항번호 = 항번호.isdigit()
            if keyword_clean in clean(항내용) and has_항번호:
                locations.append((조번호, 항번호, None, None, 항내용.strip()))

            for 호 in 항.findall("호"):
                raw_호번호 = 호.findtext("호번호", "").strip().replace(".", "")
                호내용 = 호.findtext("호내용", "") or ""
                if keyword_clean in clean(호내용):
                    항출력 = 항번호 if has_항번호 else None
                    항출력 = 항번호 if has_항번호 else None  # ✅ 이 줄이 중요
                    locations.append((조번호, 항출력, raw_호번호, None, 호내용.strip()))
                     
                for 목 in 호.findall("목"):
                    for m in 목.findall("목내용"):
                        if m.text and keyword_clean in clean(m.text):
                            raw_목번호 = 목.findtext("목번호", "").strip().replace(".", "")
                            항출력 = 항번호 if has_항번호 else None
                            locations.append((조번호, 항출력, raw_호번호, raw_목번호, m.text.strip()))
    return locations

def format_location_groups(locations):
    grouped = defaultdict(list)
    조문제목s = defaultdict(lambda: None)
    for 조, 항, 호, 목, 텍스트 in locations:
        if 항 is None and 호 is None and 목 is None:
            조문제목s[조] = "제목"
    for 조, 항, 호, 목, 텍스트 in locations:
        key = f"제{조}조"
        항목표현 = ""
        if 목:
            항목표현 = f"제{항}항제{호}호{목}목" if 항 else f"제{호}호{목}목"
        elif 호:
            항목표현 = f"제{항}항제{호}호" if 항 else f"제{호}호"
        elif 항:
            항목표현 = f"제{항}항"
        grouped[key].append((조문제목s[조], 항목표현))

    parts = []
    for 조key, 항목들 in grouped.items():
        제목있음 = any(x[0] == "제목" for x in 항목들)
        항모음 = [x[1] for x in 항목들 if x[1]]
        if 제목있음 and 항모음:
            all_parts = ["제목"] + 항모음
            parts.append(f"{조key} " + "ㆍ".join(all_parts))
        elif 제목있음:
            parts.append(f"{조key} 제목")
        elif 항모음:
            parts.append(f"{조key}" + "ㆍ".join(항모음))
        else:
            parts.append(f"{조key}")
    return ", ".join(parts[:-1]) + " 및 " + parts[-1] if len(parts) > 1 else parts[0]

def unicircle(n):
    if 1 <= n <= 20:
        return chr(9311 + n)
    return f"<span class='circle-number'>{n}</span>"

def run_amendment_logic(find_word, replace_word):
    을를 = 조사_을를(find_word)
    으로로 = 조사_으로로(replace_word)
    amendment_results = []
    laws = get_law_list_from_api(find_word)
    for idx, law in enumerate(laws):
        law_name = law["법령명"]
        mst = law["MST"]
        xml = get_law_text_by_mst(mst)
        if not xml:
            continue
        all_locations = extract_locations(xml, find_word)
        if not all_locations:
            continue

        chunk_groups = defaultdict(list)
        for loc in all_locations:
            조, 항, 호, 목, 텍스트 = loc
            m = re.search(r"([\w가-힣]*%s)" % re.escape(find_word), 텍스트)
            chunk = m.group(1) if m else find_word
            chunk_groups[chunk].append((조, 항, 호, 목, 텍스트))

        for chunk, locs in chunk_groups.items():
            각각 = "각각 " if len(locs) > 1 else ""
            loc_str = format_location_groups(locs)
            new_chunk = chunk.replace(find_word, replace_word)
            sentence = (
                f"{unicircle(len(amendment_results)+1)} {law_name} 일부를 다음과 같이 개정한다.<br>"
                f"{loc_str} 중 “{chunk}”{을를} {각각}“{new_chunk}”{으로로} 한다."
            )
            amendment_results.append(sentence)
    return amendment_results if amendment_results else ["⚠️ 개정 대상 조문이 없습니다."]

# 파일 맨 마지막에 추가
def run_search_logic(query, unit):
    return {"검색결과": [f"제1조 {query}가 포함된 조문입니다."]}

