def html_path(source_id: int, crawl_id: int) -> str:
    return f"sources/{source_id}/crawls/{crawl_id}/raw.html"


def extracted_json_path(source_id: int, crawl_id: int) -> str:
    return f"sources/{source_id}/crawls/{crawl_id}/extracted.json"
