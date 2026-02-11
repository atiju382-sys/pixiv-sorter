import requests
import argparse
import webbrowser
from pixivpy3 import AppPixivAPI
import time
import sys
import os
import pixiv_auth

def get_unique_download_path(search_term, threshold):
    """
    Creates a folder 'download/<search term> <threshold>'
    If folder exists, adds (1), (2), etc.
    """
    base_dir = "download"
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    # Clean folder name (remove invalid chars)
    safe_term = "".join([c for c in search_term if c.isalnum() or c in (' ', '_', '-')]).strip()
    folder_name = f"{safe_term} {threshold}"
    
    dest_path = os.path.join(base_dir, folder_name)
    
    if os.path.exists(dest_path):
        counter = 1
        while os.path.exists(f"{dest_path} ({counter})"):
            counter += 1
        dest_path = f"{dest_path} ({counter})"
    
    os.makedirs(dest_path)
    return dest_path

def download_image(illust, dest_folder, logger=print):
    """
    Downloads the high-resolution (original) version of an illustration.
    """
    if isinstance(illust, dict):
        # Extract original URL
        meta_single = illust.get('meta_single_page', {})
        url = meta_single.get('original_image_url')
        if not url:
            meta_pages = illust.get('meta_pages', [])
            if meta_pages:
                url = meta_pages[0].get('image_urls', {}).get('original')
        
        # Fallback to large if original not found
        if not url:
            url = illust.get('image_urls', {}).get('large')
            
        illust_id = illust.get('id')
        title = illust.get('title', 'Untitled')
    else:
        # For object-based results (less common with json_result)
        meta_single = getattr(illust, 'meta_single_page', {})
        url = getattr(meta_single, 'original_image_url', None)
        if not url:
            meta_pages = getattr(illust, 'meta_pages', [])
            if meta_pages:
                url = meta_pages[0].get('image_urls', {}).get('original')
        
        if not url:
            image_urls = getattr(illust, 'image_urls', {})
            url = getattr(image_urls, 'large', None)

        illust_id = getattr(illust, 'id', '0')
        title = getattr(illust, 'title', 'Untitled')

    if not url:
        return False

    # Get file extension from URL
    ext = os.path.splitext(url)[1]
    filename = f"{illust_id}{ext}"
    filepath = os.path.join(dest_folder, filename)

    headers = {
        "Referer": "https://www.pixiv.net/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
        else:
            logger(f"  [!] Failed to download {illust_id}: HTTP {response.status_code}")
    except Exception as e:
        logger(f"  [!] Error downloading {illust_id}: {e}")
    
    return False

def generate_html(illustrations, search_term, threshold, filename="output.html"):
    # Create results directory if it doesn't exist
    output_dir = "results"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    filepath = os.path.join(output_dir, filename)

    # Sort by likes descending by default for the initial render
    illustrations.sort(key=lambda x: (x.get('total_bookmarks', 0) if isinstance(x, dict) else getattr(x, 'total_bookmarks', 0)), reverse=True)

    css_filename = "style.css"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pixiv: {search_term}</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="{css_filename}">
    </head>
    <body>
        <header>
            <div class="brand">
                <h1>Pixiv Result: <span>{search_term}</span></h1>
                <div class="subtitle">{len(illustrations)} images found (> {threshold} likes)</div>
            </div>

            <div class="controls">
                <button onclick="downloadAll()" class="download-all-btn">
                    <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                    Download All (Browser)
                </button>
                <div class="sorting">
                    <button onclick="sortGrid('likes')" class="active" id="btn-likes">Original Order (Likes)</button>
                    <button onclick="sortGrid('date')" id="btn-date">Newest First</button>
                </div>
            </div>
        </header>

        <div class="container" id="grid">
    """

    for illust in illustrations:
        # Helper to get attributes safely
        def get_attr(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        # Image URLs
        # Extract Original URL for High-Res downloading/viewing
        orig_url = None
        if isinstance(illust, dict):
            # Try single page original
            orig_url = illust.get('meta_single_page', {}).get('original_image_url')
            if not orig_url:
                # Try multi-page original
                meta_pages = illust.get('meta_pages', [])
                if meta_pages:
                    orig_url = meta_pages[0].get('image_urls', {}).get('original')
            
            if not orig_url:
                orig_url = illust.get('image_urls', {}).get('large')
        
        image_urls = get_attr(illust, 'image_urls')
        if image_urls:
            image_url_medium = get_attr(image_urls, 'square_medium')
            # Use "large" (master) for the preview/lightbox (not the original P0)
            image_url_preview = get_attr(image_urls, 'large') or get_attr(image_urls, 'medium')
            # Use original URL specifically for the download action
            image_url_original = orig_url or image_url_preview
        else:
            image_url_medium = "" 
            image_url_preview = ""
            image_url_original = ""
        
        # Proxy
        def proxy_url(url):
            if url:
                return url.replace("i.pximg.net", "i.pixiv.re")
            return "https://via.placeholder.com/300?text=No+Image"
            
        thumb_src = proxy_url(image_url_medium)
        preview_src = proxy_url(image_url_preview)
        original_src = proxy_url(image_url_original)
        
        illust_id = get_attr(illust, 'id')
        title = get_attr(illust, 'title', 'Untitled')
        user = get_attr(illust, 'user')
        user_name = get_attr(user, 'name', 'Unknown') if user else 'Unknown'
        bookmarks = get_attr(illust, 'total_bookmarks', 0)
        create_date = get_attr(illust, 'create_date', '')

        detail_url = f"https://www.pixiv.net/en/artworks/{illust_id}"
        
        # Card HTML
        # thumb_src for card image
        # preview_src for lightbox (master)
        # original_src for actual download (P0)
        html_content += f"""
            <div class="card" data-likes="{bookmarks}" data-date="{create_date}" data-preview-url="{preview_src}" data-original-url="{original_src}" data-illust-id="{illust_id}">
                <div class="image-wrapper">
                    <img src="{thumb_src}" alt="{title}" loading="lazy">
                    <div class="overlay-actions">
                        <button class="action-btn" onclick="openLightbox('{preview_src}')" title="Preview">
                            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                        </button>
                        <button class="action-btn download-trigger" title="Download High-Res">
                            <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                        </button>
                    </div>
                    <a href="{detail_url}" target="_blank" class="pixiv-link" title="Open on Pixiv"></a>
                </div>
                <div class="info">
                    <div class="title" title="{title}">{title}</div>
                    <div class="author">
                        <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
                        {user_name}
                    </div>
                    <div class="stats">
                        <span class="likes">
                            <svg width="14" height="14" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                            {bookmarks}
                        </span>
                        <span class="date">{create_date[:10]}</span>
                    </div>
                </div>
            </div>
        """

    html_content += """
        </div>

        <div class="lightbox" id="lightbox" onclick="closeLightbox()">
            <div class="close-btn">&times;</div>
            <img id="lightbox-img" src="" alt="Full view" onclick="event.stopPropagation()">
        </div>

        <script>
            function sortGrid(type) {
                const container = document.getElementById('grid');
                const cards = Array.from(container.getElementsByClassName('card'));
                
                cards.sort((a, b) => {
                    if (type === 'likes') {
                        const likesA = parseInt(a.dataset.likes);
                        const likesB = parseInt(b.dataset.likes);
                        return likesB - likesA; // Descending
                    } else if (type === 'date') {
                        const dateA = a.dataset.date;
                        const dateB = b.dataset.date;
                        return dateB.localeCompare(dateA); // Descending (Newest first)
                    }
                });

                cards.forEach(card => container.appendChild(card));
                
                document.querySelectorAll('.sorting button').forEach(btn => btn.classList.remove('active'));
                document.getElementById('btn-' + type).classList.add('active');
            }

            async function downloadImage(url, filename, triggerElement = null) {
                if (triggerElement) {
                    triggerElement.classList.add('loading');
                    triggerElement.disabled = true;
                }
                
                try {
                    // Use images.weserv.nl as a CORS proxy
                    // We also ensure it handles the download by attempting to fetch as blob first
                    const proxyUrl = `https://wsrv.nl/?url=${encodeURIComponent(url)}&default=${encodeURIComponent(url)}`;
                    
                    const response = await fetch(proxyUrl);
                    if (!response.ok) throw new Error('Fetch via proxy failed');
                    
                    const blob = await response.blob();
                    const blobUrl = window.URL.createObjectURL(blob);
                    
                    const link = document.createElement('a');
                    link.href = blobUrl;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    // Cleanup
                    setTimeout(() => window.URL.revokeObjectURL(blobUrl), 100);
                } catch (error) {
                    console.error('Download failed:', error);
                    // Fallback: try download via proxy direct link which uses Content-Disposition
                    const fallbackUrl = `https://wsrv.nl/?url=${encodeURIComponent(url)}&filename=${filename}`;
                    window.open(fallbackUrl, '_blank');
                } finally {
                    if (triggerElement) {
                        triggerElement.classList.remove('loading');
                        triggerElement.disabled = false;
                    }
                }
            }

            async function downloadAll() {
                const cards = Array.from(document.querySelectorAll('.card'));
                if (!confirm(`Are you sure you want to download ${cards.length} high-resolution images?`)) return;

                const btn = document.querySelector('.download-all-btn');
                if (btn) {
                    btn.classList.add('loading');
                    btn.textContent = 'Downloading...';
                }

                for (let i = 0; i < cards.length; i++) {
                    const card = cards[i];
                    const trigger = card.querySelector('.download-trigger');
                    const url = card.dataset.originalUrl;
                    const filename = card.dataset.illustId + ".jpg";
                    
                    await downloadImage(url, filename, trigger);
                    // 300ms delay to prevent browser congesting
                    await new Promise(r => setTimeout(r, 300));
                }

                if (btn) {
                    btn.classList.remove('loading');
                    btn.textContent = 'Download All (Browser)';
                }
            }

            // Handle individual download clicks
            document.addEventListener('click', function(e) {
                const trigger = e.target.closest('.download-trigger');
                if (trigger) {
                    e.preventDefault();
                    const card = trigger.closest('.card');
                    const url = card.dataset.originalUrl;
                    const filename = card.dataset.illustId + ".jpg";
                    downloadImage(url, filename, trigger);
                }
            });

            function openLightbox(src) {
                const lightbox = document.getElementById('lightbox');
                const img = document.getElementById('lightbox-img');
                img.src = src;
                lightbox.classList.add('active');
            }

            function closeLightbox() {
                document.getElementById('lightbox').classList.remove('active');
            }
            
            document.addEventListener('keydown', function(event) {
                if (event.key === "Escape") {
                    closeLightbox();
                }
            });
        </script>
    </body>
    </html>
    """
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return os.path.abspath(filepath)

def run_sorter(search_term, threshold=1000, pages=5, r18=False, delay=2.5, start_page=1, no_limit=False, auto_download=False, logger=print):
    api = AppPixivAPI()
    
    # Try to load token from environment or file
    token_file = "refresh_token.txt"
    refresh_token = os.environ.get("PIXIV_REFRESH_TOKEN")
    if not refresh_token:
        if os.path.exists(token_file):
            with open(token_file, "r") as f:
                refresh_token = f.read().strip()
    
    def perform_login(current_token):
        if current_token:
            logger("Logging in...")
            try:
                api.auth(refresh_token=current_token)
                return True
            except Exception as e:
                logger(f"Login with existing token failed: {e}")
        
        logger("\n[!] Token expired or missing. Starting authentication flow...")
        new_token = pixiv_auth.login()
        if new_token:
            with open(token_file, "w") as f:
                f.write(new_token)
            logger("New token saved. Retrying login...")
            try:
                api.auth(refresh_token=new_token)
                return True
            except Exception as e:
                logger(f"Login with new token failed: {e}")
        return False

    if not perform_login(refresh_token):
        logger("Could not authenticate. Exiting.")
        return

    # Create results directory if it doesn't exist
    output_dir = "results"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Copy style.css to results directory (Ensure consistent styling)
    def get_resource_path(relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    css_filename = "style.css"
    css_src = get_resource_path("style.css")
    css_dst = os.path.join(output_dir, css_filename)
    
    if os.path.exists(css_src):
        import shutil
        shutil.copy2(css_src, css_dst)
    else:
        logger(f"[!] Warning: {css_filename} not found at {css_src}")

    download_folder = None
    if auto_download:
        download_folder = get_unique_download_path(search_term, threshold)
        logger(f"Auto-download enabled. Images will be saved to: {download_folder}")

    logger(f"Searching for '{search_term}' starting at page {start_page} with threshold {threshold}...")
    
    # Calculate offset
    start_offset = (start_page - 1) * 30

    json_result = api.search_illust(
        search_term, 
        search_target="partial_match_for_tags",
        sort="date_desc", 
        filter="for_ios",
        offset=start_offset
    )

    filtered_illusts = []
    pages_processed = 0
    current_page_number = start_page
    seen_urls = set()
    previous_page_ids = set()
    
    while True:
        illusts = json_result.get('illusts', [])
        pages_processed += 1
        
        # If we reached a page with no illustrations, stop immediately
        if not illusts:
            logger(f"No more illustrations found. Stopping at page {current_page_number}.")
            break

        # Check for duplicate results (Pixiv API sometimes returns the last valid page if requested page > limit)
        current_page_ids = {illust.get('id') for illust in illusts}
        if previous_page_ids and current_page_ids == previous_page_ids:
            logger(f"Duplicate page detected at page {current_page_number}. Stopping.")
            break
        previous_page_ids = current_page_ids

        logger(f"Processing page {current_page_number} ({len(illusts)} items)...")

        for illust in illusts:
            x_restrict = illust.get('x_restrict', 0) if isinstance(illust, dict) else getattr(illust, 'x_restrict', 0)
            if x_restrict > 0 and not r18:
                continue
            
            bookmarks = illust.get('total_bookmarks', 0) if isinstance(illust, dict) else getattr(illust, 'total_bookmarks', 0)
            if bookmarks >= threshold:
                filtered_illusts.append(illust)
                if auto_download:
                    download_image(illust, download_folder, logger=logger)

        next_url = json_result.get('next_url')
        
        # Stop if no next_url
        if not next_url:
            logger("End of results (no next page).")
            break
            
        # Stop if we see the same URL again (circular pagination)
        if next_url in seen_urls:
            logger("Circular pagination detected. Stopping.")
            break
        seen_urls.add(next_url)

        # Handle page limit
        if not no_limit and pages_processed >= pages:
            logger(f"Reached page limit ({pages}). Stopping.")
            break
        
        # Safety cap to prevent infinite runs (e.g. 2000 pages)
        if pages_processed >= 2000:
            logger("Reached safety cap of 2000 pages. Stopping.")
            break
            
        next_qs = api.parse_qs(next_url)
        if not next_qs:
            logger("Could not parse next page parameters. Stopping.")
            break
            
        time.sleep(delay)
        try:
            json_result = api.search_illust(**next_qs)
            current_page_number += 1
        except Exception as e:
            logger(f"API Error fetching next page: {e}")
            break

    logger(f"Found {len(filtered_illusts)} images matching the criteria.")
    
    if filtered_illusts:
        output_file = generate_html(filtered_illusts, search_term, threshold)
        logger(f"Results saved to: {output_file}")
        webbrowser.open(f"file://{output_file}")
    else:
        logger("No images found with that threshold.")

def main():
    parser = argparse.ArgumentParser(description="Pixiv Sorter - Find popular images.")
    parser.add_argument("search_term", nargs="?", help="The search term (tag or keyword)")
    parser.add_argument("--threshold", type=int, default=1000, help="Minimum likes threshold (default: 1000)")
    parser.add_argument("--pages", type=int, default=5, help="Number of pages to search (default: 5)")
    parser.add_argument("--r18", action="store_true", help="Include R-18 content")
    parser.add_argument("--delay", type=float, default=2.5, help="Delay between pages in seconds (default: 2.5)")
    parser.add_argument("--start_page", type=int, default=1, help="Start search from this page number (default: 1)")
    parser.add_argument("--no_limit", action="store_true", help="Keep searching until no more results (overrides --pages)")
    
    args = parser.parse_args()

    # If args are missing, ask interactively
    if not args.search_term:
        args.search_term = input("Enter search term: ").strip()
        if not args.search_term:
            print("Search term is required.")
            return

    run_sorter(
        search_term=args.search_term,
        threshold=args.threshold,
        pages=args.pages,
        r18=args.r18,
        delay=args.delay,
        start_page=args.start_page,
        no_limit=args.no_limit
    )

if __name__ == "__main__":
    main()
