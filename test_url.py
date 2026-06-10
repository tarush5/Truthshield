import sys
import traceback
import requests
from bs4 import BeautifulSoup
import re

def test():
    url = 'https://www.hindustantimes.com/'
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    soup = BeautifulSoup(response.text, 'html.parser')

    title = ""
    if soup.title:
        title = soup.title.string or ""
    og_title = soup.find("meta", property="og:title")
    if og_title:
        title = og_title.get("content", title)

    og_image = None
    og_img_tag = soup.find("meta", property="og:image")
    if og_img_tag:
        og_image = og_img_tag.get("content")

    meta_desc = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag:
        meta_desc = desc_tag.get("content", "")

    junk_tags = ["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "svg", "form", "button"]
    for tag in soup.find_all(junk_tags):
        tag.decompose()

    junk_patterns = re.compile(
        r"(nav|menu|sidebar|footer|header|banner|advert|cookie|consent|"
        r"social|share|comment|related|recommend|popup|modal|overlay|"
        r"breadcrumb|widget|signup|subscribe|newsletter|promo|"
        r"partner.?site|site.?map|disclaimer|copyright)",
        re.IGNORECASE,
    )
    for el in soup.find_all(attrs={"class": True}):
        if el.attrs is None:
            continue
        classes = el.get("class", [])
        if isinstance(classes, list):
            classes = " ".join(classes)
        if junk_patterns.search(classes):
            el.decompose()

    for el in soup.find_all(attrs={"id": True}):
        if el.attrs is None:
            continue
        ident = el.get("id", "")
        if junk_patterns.search(ident):
            el.decompose()

    print("Success")

try:
    test()
except Exception as e:
    traceback.print_exc()
