def get_wiki_html(page_slug):
    cache_path = f".wiki_cache/{page_slug}.html"
    url = "http://en.wikipedia.org/wiki/" + page_slug
    try:
        page_html = open(cache_path, "r").read()
        print(f"Loading {url} from cache")
    except FileNotFoundError:
        # Cache file not found, so fetch the URL
        print(f"Downloading {url}")
        page_html = requests.get(url).text
        with open(cache_path, "w") as f:
            f.write(page_html)
    return page_html
