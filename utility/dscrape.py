import requests
import io
from PIL import Image
from bs4 import BeautifulSoup

page_urls = []

def download_image_to_ram(image_url: str):
    """Downloads the image from the given URL and returns it as an Image object"""
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))
    except requests.RequestException as e:
        print(f"EXCEPTION: dscrape.download_image_to_ram(), Failed to download {image_url}")
        raise e
        
def get_search_page_links(url: str):
    print(f"INFO: dscrape.get_search_page_links(), Getting post links from {url}")
    try:
      response = requests.get(url, timeout=10)
      response.raise_for_status()
    except requests.RequestException as e:
      print("EXCEPTION: dscrape.get_search_page_links(), Failed to get search page links from front page")
      raise e
       
    soup = BeautifulSoup(response.text, "html.parser")

    anchor_tags = soup.find_all('a', class_="post-preview-link")
    page_urls = []

    for link in anchor_tags:
        href = link.get('href')
        if href and href.startswith('/posts/'):
            page_url = "https://danbooru.donmai.us" + href
            page_urls.append(page_url)

    print(f"INFO: dscrape.get_search_page_links(), Got {len(page_urls)} links")
    return page_urls

def remove_seen_links(page_links: list):
    # check if we've already checked this link
    seen_links = open("global_seen_links.txt").read()

    # Use list comprehension to filter out seen links
    page_links = [link for link in page_links if str(link) not in seen_links]

    print(f"INFO: Found {len(page_links)} unseen links")
    return page_links

def get_new_links_from_front_page():
    # Get the links from the front page
    page_links = get_search_page_links("https://danbooru.donmai.us/posts?page=1&tags=maid+rating%3Ageneral")
    # Filter out the links we've already seen
    page_links = remove_seen_links(page_links)

    return page_links

def get_image_from_page_link(url: str):
    """Fetches the main image from the webpage at the given URL"""
    try:
        print(f"INFO: dscrape.get_image_from_page_link(), Downloading image from {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        image_url = soup.find('img', id="image").get('src')
        if not image_url:
          raise ValueError(f"Failed to find image on {url}")
        img = download_image_to_ram(image_url)
        print(f"INFO: dscrape.get_image_from_page_link(), successfully downloaded image from URL\n")
        return img
    except Exception as e:
        print(e)
        return None
