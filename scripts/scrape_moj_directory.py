import urllib.request
import json
from html.parser import HTMLParser

class MOJParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.data = None

    def handle_starttag(self, tag, attrs):
        if tag == "div":
            for attr, value in attrs:
                if attr == "data-organisation-data":
                    self.data = value

def fetch_moj():
    url = "https://www.justice.govt.nz/about/directory-of-official-information/directory-of-official-information-search-tool/"
    print(f"Fetching {url}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return
    
    parser = MOJParser()
    parser.feed(html)
    if not parser.data:
        print("No data found on page.")
        return
        
    page_data = json.loads(parser.data)
    if not page_data:
        print("Empty JSON array on page.")
        return
        
    print(f"Successfully extracted {len(page_data)} items from the embedded data attribute.")
    
    with open("moj_authorities.json", "w") as f:
        json.dump(page_data, f, indent=2)
    print("Saved to moj_authorities.json")

if __name__ == "__main__":
    fetch_moj()
