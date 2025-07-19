import sys, json
from lxml import etree

def clean(text):
    return " ".join(text.split()) if text else ""

def parse_articles(xml_path, law_code):
    root = etree.parse(xml_path).getroot()
    effective_date = root.attrib.get("inwerkingtreding", "")
    articles = []
    for artikel in root.findall(".//artikel"):
        nr = clean(artikel.findtext("kop/nr"))
        identifier = f"{law_code}:{nr}" if nr else None
        paragraphs = []
        for lid in artikel.findall("lid"):
            lidnr = clean(lid.findtext("lidnr"))
            text = clean(" ".join(lid.itertext()))
            paragraphs.append({"lidnr": lidnr, "text": text, "subparagraphs": None})
        articles.append({
            "article_number": nr,
            "identifier": identifier,
            "effective_date": effective_date,
            "full_text_json": paragraphs
        })
    return articles

if __name__ == "__main__":
    xml_path, law_code = sys.argv[1], sys.argv[2]
    articles = parse_articles(xml_path, law_code)
    json.dump(articles, open("parsed_articles.json", "w"), ensure_ascii=False, indent=2) 