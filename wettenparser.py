import json
import unicodedata
import sys
import os
import glob
from lxml import etree
from typing import Optional

DEFAULT_OUTPUT_FILE = "parsed_articles.json"

def select_xml_file():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path) and file_path.endswith('.xml'):
            return file_path
        else:
            print(f"❌ Error: '{file_path}' is not a valid XML file or doesn't exist.")
            sys.exit(1)
    print("📁 XML File Selection")
    print("=" * 40)
    xml_files = glob.glob("*.xml")
    if xml_files:
        print("Found XML files in current directory:")
        for i, file in enumerate(xml_files, 1):
            print(f"  {i}. {file}")
        print(f"  {len(xml_files) + 1}. Enter custom path")
        while True:
            try:
                choice = input(f"\nSelect a file (1-{len(xml_files) + 1}): ").strip()
                if choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(xml_files):
                        return xml_files[choice_num - 1]
                    elif choice_num == len(xml_files) + 1:
                        break
                print("❌ Invalid choice. Please try again.")
            except (ValueError, KeyboardInterrupt):
                print("\n❌ Invalid input. Please try again.")
    while True:
        file_path = input("\nEnter the path to your XML file: ").strip()
        if not file_path:
            print("❌ Please enter a file path.")
            continue
        if not file_path.endswith('.xml'):
            print("❌ Please select an XML file (.xml extension).")
            continue
        if not os.path.exists(file_path):
            print(f"❌ File '{file_path}' does not exist.")
            continue
        return file_path

def get_output_filename():
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
        return output_file
    default_name = DEFAULT_OUTPUT_FILE
    custom_name = input(f"\nOutput filename (default: {default_name}): ").strip()
    final_name = custom_name if custom_name else default_name
    return final_name

def clean_text(text):
    if not text:
        return ""
    text = text.replace("\xa0", " ")
    text = unicodedata.normalize("NFKC", text)
    text = " ".join(text.split())
    return text.strip()

def extract_full_text(element):
    parts = []
    for node in element.iter():
        if node.tag == "a":
            label = node.text or ""
            parts.append(label)
        elif node.text and node.tag != "a":
            parts.append(node.text)
        if node.tail:
            parts.append(node.tail)
    return "".join(parts)

def extract_subparagraphs(lid_element):
    subparagraphs = []
    for lijst in lid_element.findall("lijst"):
        for li in lijst.findall("li"):
            li_nr_el = li.find("li.nr")
            li_al_el = li.find("al")
            li_nr = clean_text(li_nr_el.text) if li_nr_el is not None else None
            li_text = clean_text(extract_full_text(li_al_el)) if li_al_el is not None else None
            if li_nr or li_text:
                subparagraphs.append({
                    "nr": li_nr,
                    "text": li_text
                })
    return subparagraphs if subparagraphs else None

def parse_xml_file(file_path: str, law_code: str):
    try:
        with open(file_path, 'rb') as f:
            xml_content = f.read()
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)
    try:
        root = etree.fromstring(xml_content)
    except Exception as e:
        print(f"❌ Error parsing XML: {e}")
        sys.exit(1)
    effective_date = root.attrib.get("inwerkingtreding", "")
    articles_data = []
    def get_kop_title(element):
        kop = element.find("kop")
        if kop is None:
            return None
        parts = []
        for tag in ["label", "nr", "titel"]:
            el = kop.find(tag)
            if el is not None and el.text:
                parts.append(el.text.strip())
        return " ".join(parts)
    def extract_articles_with_context(element, context: Optional[dict[str, str | None]] = None):
        if context is None:
            context = {"title_heading": None}
        tag = etree.QName(element).localname
        if tag == "titeldeel":
            context["title_heading"] = get_kop_title(element)
        elif tag == "artikel":
            kop = element.find("kop")
            nr_el = kop.find("nr") if kop is not None else None
            nr = clean_text(nr_el.text) if nr_el is not None else None
            article_number = nr
            identifier = f"{law_code}:{article_number}" if article_number else None
            full_text_parts = []
            paragraphs = []
            lids = element.findall("lid")
            if lids:
                for lid in lids:
                    lidnr_el = lid.find("lidnr")
                    lidnr = clean_text(lidnr_el.text) if lidnr_el is not None else None
                    lid_text_parts = []
                    for child in lid:
                        if child.tag == "al":
                            lid_text_parts.append(clean_text(extract_full_text(child)))
                    lid_text = " ".join(lid_text_parts).strip()
                    if lidnr and lid_text.startswith(lidnr):
                        lid_text = lid_text[len(lidnr):].lstrip(". ").lstrip()
                    subparagraphs = extract_subparagraphs(lid)
                    paragraphs.append({
                        "lidnr": lidnr,
                        "text": lid_text,
                        "subparagraphs": subparagraphs
                    })
                    full_text_parts.append(lid_text)
            else:
                for al in element.findall("al"):
                    al_text_raw = extract_full_text(al)
                    al_text = clean_text(al_text_raw)
                    if al_text:
                        full_text_parts.append(al_text)
                        paragraphs.append({
                            "lidnr": None,
                            "text": al_text,
                            "subparagraphs": None
                        })
            if not full_text_parts:
                return
            article = {
                "article_number": article_number,
                "identifier": identifier,
                "effective_date": effective_date,
                "full_text_json": paragraphs
            }
            articles_data.append(article)
        for child in element:
            extract_articles_with_context(child, context.copy())
    extract_articles_with_context(root)
    with open(get_output_filename(), "w", encoding="utf-8") as f:
        json.dump(articles_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Parsed {len(articles_data)} articles for law {law_code}.")

if __name__ == "__main__":
    file_path = select_xml_file()
    law_code = input("Enter law code (e.g. BW1): ").strip()
    if not law_code:
        print("❌ Law code is required.")
        sys.exit(1)
    parse_xml_file(file_path, law_code)