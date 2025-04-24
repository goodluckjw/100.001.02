
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
            locations.append((조번호, None, None, None, 조제목.strip(), "제목"))
        if keyword_clean in clean(조내용):
            locations.append((조번호, None, None, None, 조내용.strip(), "조문"))

        for 항 in article.findall("항"):
            항번호 = normalize_number(항.findtext("항번호", "").strip())
            항내용 = 항.findtext("항내용") or ""
            has_항번호 = 항번호.isdigit()
            if keyword_clean in clean(항내용) and has_항번호:
                locations.append((조번호, 항번호, None, None, 항내용.strip(), "항"))

            for 호 in 항.findall("호"):
                raw_호번호 = 호.find력, raw_호번호, raw_목번호, m.text.strip(), "목"))
    return locations

def format_location_groups(locations):
    grouped = defaultdict(list)
    for 조, 항, 호, 목, _, 타입 in locations:
        key = f"제{조}조"
        if 타입 == "제목":
            grouped[key].append(("제목", f"{key} 제목"))
        else:
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
        제목들 = [p for 항, p in 항목리스트 if 항 == "제목"]
        비제목들 = [p for 항, p in 항목리스트 if 항 != "제목"]

        조부 = ""
        if 제목들 and 비제목들:
            조부 = f"{제목들[0]}ㆍ" + "ㆍ".join(비제목들)
        elif 제목들:
            조부 = 제목들[0]
        else:
            조부 = "ㆍ".join(비제목들)

        parts.append(조부)

    return ", ".join(parts[:-1]) + " 및 " + parts[-1] if len(parts) > 1 else parts[0]
