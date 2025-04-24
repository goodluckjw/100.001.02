
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote
import re
import os
from collections import defaultdict

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

def get_josa(word, josa_with_batchim, josa_without_batchim):
    if not word:
        return josa_with_batchim
    last_char = word[-1]
    code = ord(last_char)
    return josa_with_batchim if (code - 44032) % 28 != 0 else josa_without_batchim

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
            locations.append((조번호, None, None, None))
        if keyword_clean in clean(조내용):
            locations.append((조번호, None, None, None))

        for 항 in article.findall("항"):
            항번호 = 항.findtext("항번호", "").strip()
            항내용 = 항.findtext("항내용") or ""
            has_항번호 = 항번호.isdigit()
            if keyword_clean in clean(항내용) and has_항번호:
                locations.append((조번호, 항번호, None, None))

            for 호 in 항.findall("호"):
                raw_호번호 = 호.findtext("호번호", "").strip().replace(".", "")
                호내용 = 호.findtext("호내용", "") or ""
                if keyword_clean in clean(호내용):
                    항출력 = 항번호 if has_항번호 else None
                    locations.append((조번호, 항출력, raw_호번호, None))
                for 목 in 호.findall("목"):
                    for m in 목.findall("목내용"):
                        if m.text and keyword_clean in clean(m.text):
                            raw_목번호 = 목.findtext("목번호", "").strip().replace(".", "")
                            항출력 = 항번호 if has_항번호 else None
                            locations.append((조번호, 항출력, raw_호번호, raw_목번호))
    return list(dict.fromkeys(locations))

def format_location_groups(locations):
    grouped = defaultdict(list)
    for 조, 항, 호, 목 in locations:
        key = f"제{조}조"
        if 목:
            detail = f"제{항}항제{호}호{목}목" if 항 else f"제{호}호{목}목"
        elif 호:
            detail = f"제{항}항제{호}호" if 항 else f"제{호}호"
        elif 항:
            detail = f"제{항}항"
        else:
            detail = ""
        grouped[key].append((항 or "", detail))

    parts = []
    for 조, 항목리스트 in grouped.items():
        항별묶음 = defaultdict(list)
        for 항, 표현 in 항목리스트:
            항별묶음[항].append(표현)

        묶인 = []
        for 항, 표현들 in 항별묶음.items():
            if 표현들 and all("호" in p or "목" in p for p in 표현들):
                묶음 = "ㆍ".join([re.sub(r"제\d+항", "", p) for p in 표현들])
                묶인.append(f"제{항}항{묶음}" if 항 else 묶음)
            else:
                묶인.extend(표현들)

        parts.append(f"{조}" + "ㆍ".join(묶인))
    return ", ".join(parts[:-1]) + " 및 " + parts[-1] if len(parts) > 1 else parts[0]

def unicircle(n):
    return chr(9311 + n) if 1 <= n <= 20 else str(n)

def run_amendment_logic(find_word, replace_word):
    조사 = get_josa(find_word, "을", "를")
    amendment_results = []
    laws = get_law_list_from_api(find_word)
    for idx, law in enumerate(laws):
        law_name = law["법령명"]
        mst = law["MST"]
        xml = get_law_text_by_mst(mst)
        if not xml:
            continue
        raw_locations = extract_locations(xml, find_word)
        if not raw_locations:
            continue
        loc_str = format_location_groups(raw_locations)
        각각 = "각각 " if len(raw_locations) > 1 else ""
        sentence = (
            f"{unicircle(idx+1)} {law_name} 일부를 다음과 같이 개정한다.\n"
            f"{loc_str} 중 “{find_word}”{조사} {각각}“{replace_word}”로 한다."
        )
        amendment_results.append(sentence)
    return amendment_results if amendment_results else ["⚠️ 개정 대상 조문이 없습니다."]

def run_search_logic(query, unit):
    return {"검색결과": [f"제1조 {query}가 포함된 조문입니다."]}

