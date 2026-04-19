import asyncio
import os
import sys

# Add project root to sys path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.preprocessor.url_scraper import URLScraper

def main():
    scraper = URLScraper()
    url = "https://www.bbc.com/news/articles/cwylwrzxl8xo" # random URL to test
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    print(f"Scraping: {url}")
    result = scraper.process(url)
    
    text = result.text or ""
    print(f"Extraction successful: {len(text)} characters")
    print(f"Title: {result.metadata.get('title')}")
    if len(text) > 0:
        print(f"Preview: {text[:200]}...")
    else:
        print(f"FAILED TO EXTRACT TEXT: Metadata={result.metadata}")
        
    print(f"Has Error: {result.metadata.get('has_error')}")

if __name__ == "__main__":
    main()
