import unicodedata
import requests
from bs4 import BeautifulSoup
import pandas as pd
from openpyxl import load_workbook
import re
import os


def process_program(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    Title = soup.select_one("h1").text
    Learningoutcomes = soup.select_one("div.program_description").text.replace("Degree Map", "").replace("Student Outcomes", "").strip()

    Credits = re.findall(r'\(\s*\d+(?:-\d+)?\s+credits\s*\)', Learningoutcomes)
    if Credits:
        Total_Credits = Credits[0]
    else:
        Total_Credits = 'NA'
    content_div_all = soup.find_all("div", class_="acalog-core")

    structured_data = []
    current_section = "Program Overview"
    current_main_section = "Main"

    for content_div in content_div_all:
        for tag in content_div.find_all(["h2", "h3", "p", "ul"], recursive=True):
            if tag.name == "h2":
                current_main_section = tag.get_text(strip=True)
                structured_data.append({"Main": current_main_section.replace(":", '')})
            if tag.name == "h3":
                current_section = tag.get_text(strip=True)
                if not content_div.find_all(["p", "ul"], recursive=True):
                    structured_data.append(
                        {"Main": current_main_section.replace(":", ''), "Section": current_section.replace(":", ''),
                         "Content": content_div.text})
            elif tag.name == "p":
                text = tag.get_text(strip=True)
                if text and text != "or":
                    structured_data.append(
                        {"Main": current_main_section.replace(":", ''), "Section": current_section.replace(":", ''),
                         "Content": text})
            elif tag.name == "ul":
                for li in tag.find_all("li"):
                    text = li.get_text(strip=True)
                    text = unicodedata.normalize("NFKD", text)
                    dict_ = {"course_code": '', "course_name": '', "credits": ''}
                    creditspattern = re.compile(r"(?P<credits>\d{1,2}(?:-\d{1,2})?\s*Credits)")
                    credits = ''
                    match = creditspattern.search(text)
                    if match and match.group("credits"):
                        credits = match.group("credits").strip()
                        dict_['credits'] = credits
                    cleaned = text.replace("course -->", "").strip()
                    if " - " in cleaned:
                        parts = cleaned.split(" - ", 1)
                        dict_['course_code'] = parts[0].strip()
                        dict_['course_name'] = parts[1].replace(dict_['credits'], '').strip()
                    if " | " in cleaned:
                        parts = cleaned.split(" | ")
                        dict_['course_name'] = " ".join(parts[:-1])
                    if dict_['course_name']:
                        Content = ""
                    else:
                        Content = text
                    structured_data.append({
                        "Main": current_main_section.replace(":", ''),
                        "Section": current_section.replace(":", ''),
                        "Content": Content,
                        "course_code": dict_['course_code'],
                        "course_name": dict_['course_name'],
                        "credits": dict_['credits']
                    })

    formatted_data = []
    for d in structured_data:
        if 'Section' not in d or d['Section'] == '':
            continue
        # if 'Content' in d and d['Content'] == '':
        #     d['Section'] = ''
        if d not in formatted_data:
            if d['Section'] == "Program Overview":
                d['Section'] = "Program Overview " + d['Main']
            formatted_data.append(d)

    # Create folders if they don't exist
    os.makedirs("data", exist_ok=True)
    os.makedirs("short_data", exist_ok=True)

    # Save full structured data
    df1 = pd.DataFrame(formatted_data)
    df1.to_excel(f"data/{Title}.xlsx", index=False)

    # Save summary data
    df2 = pd.DataFrame([{
        "Program": Title.strip(),
        "Learningoutcomes": Learningoutcomes.strip(),
        "Total_Credits": Total_Credits
    }])
    df2.to_excel(f"short_data/{Title}1.xlsx", index=False)


if __name__ == "__main__":
    df = pd.read_csv("scrapped_urls.csv", encoding="cp1252")  # <-- fixed encoding here
    for _, row in df.iterrows():
        try:
            print(f"Processing: {row['Name']}")
            process_program(row['Link'])
        except Exception as e:
            print(f"Failed to process {row['Name']}: {e}")




