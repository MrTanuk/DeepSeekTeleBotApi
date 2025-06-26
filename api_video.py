import os
import re
import logging
import tempfile
from yt_dlp import YoutubeDL, DownloadError
# Import the configured supabase client from the config module
import config

logger = logging.getLogger(__name__)

def get_cookies_from_supabase():
    """Fetches cookie data from the Supabase database."""
    if not config.supabase:
        logger.warning("Supabase is not configured. Cannot fetch cookies.", exc_info=True)
        return None
    try:
        response = config.supabase.table("cookies").select("cookies_data").eq("name_media", "Youtube/Instagram").single().execute()
        if response.data and "cookies_data" in response.data:
            logger.info("Cookies loaded successfully from Supabase.")
            return response.data["cookies_data"]
        logger.warning("No cookies found for 'Youtube/Instagram' in Supabase.", exc_info=True)
        return None
    except Exception as e:
        logger.error("Error fetching cookies from Supabase: %s", e, exc_info=True)
        return None

def download_video(url):
    """Downloads a video from a given URL, using cookies for YouTube/Instagram if available."""
    url_pattern = re.compile(
        r'^(https?://)?(?:www\.)?'
        r'(?:'
        r'(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)[\w\-]+|'
        r'facebook\.com|fb\.watch|instagram\.com|instagr\.am|tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com'
        r')', re.IGNORECASE
    )
    if not url_pattern.match(url):
        raise ValueError("❌ Invalid URL. Supported sites: YouTube, Facebook, Instagram, TikTok.")

    is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
    is_instagram = "instagram.com" in url.lower() or "instagr.am" in url.lower()

    if is_youtube:
        format_spec = 'bestvideo[ext=mp4][vcodec^=avc1][height<=480]+bestaudio/best'  # YouTube optimized
    elif is_instagram:
        format_spec = 'best[ext=mp4]/bestvideo+bestaudio'
    elif "tiktok.com" in url.lower() or "vm.tiktok.com" in url.lower():
        format_spec = 'bestvideo[ext=mp4][vcodec^=avc1][height<=720]+bestaudio/best'  # TikTok
    else:  
        format_spec = '(bestvideo[vcodec^=avc1][height<=720]+bestaudio)/best' # Facebook

    MAX_SIZE_MB = 49.5
    MAX_SIZE_BYTES = MAX_SIZE_MB * 1_000_000

    cookie_file_path = None
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'outtmpl': f'{tmpdir}/%(id)s.%(ext)s',  # Temporary output template
                'format': format_spec,
                'quiet': True,  # Disable debug output
                'no_warnings': True,
                'cookiefile': None,
                'noplaylist': True,
                'max_filesize': MAX_SIZE_BYTES,
                'merge_output_format': 'mp4',  # Force MP4 container
                'socket_timeout': 30,
                'retries': 5,
                'fragment_retries': 5,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',  # Ensure MP4 output
                    'when': 'post_process'
                }],
                'extractor_args': {
                    'instagram': {
                        'format_sort': ['quality']},
                    'facebook': {
                        'video_formats': 'sd'}
                },
            }
        
            if is_youtube or is_instagram:
                cookie_data = get_cookies_from_supabase()
                if cookie_data:
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_cookie_file:
                        tmp_cookie_file.write(cookie_data)
                        cookie_file_path = tmp_cookie_file.name
                    ydl_opts['cookiefile'] = cookie_file_path
                    logger.info(f"Using temporary cookie file: {cookie_file_path}", exc_info=True)

            with YoutubeDL(ydl_opts) as ydl:
                # This call downloads the file and populates 'info' with the results.
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)

                if not filename or not os.path.exists(filename):
                    estimated_size = info.get('filesize') or info.get('filesize_approx')
                    if estimated_size and estimated_size > MAX_SIZE_BYTES:
                        raise ValueError(
                            f"❌ Video too large to download.\n"
                            f"Estimated size: {estimated_size / 1_000_000:.1f}MB (Limit: {MAX_SIZE_MB}MB)"
                        )
                    logger.error(f"yt-dlp finished, but the final file was not found. Info dict: {info}", exc_info=True)
                    raise RuntimeError("Download process completed, but the final video file is missing.")

                # Perform size validation on the final file
                file_size = os.path.getsize(filename)
                if file_size > MAX_SIZE_BYTES:
                    raise ValueError(
                        f"❌ Video too large ({file_size/1_000_000:.1f}MB > "
                        f"{MAX_SIZE_MB}MB limit)"
                    )

                # Read the file's bytes and return them
                with open(filename, 'rb') as f:
                    return f.read()

    except DownloadError as e:
        error_msg = str(e).lower()
        if "login" in error_msg or "age-restricted" in error_msg or "private" in error_msg:
             raise ValueError("🔒 This video is private or age-restricted. Updated cookies may be required.")
        raise ValueError(f"❌ Download failed: {str(e).split(':')[-1].strip()}")
    except Exception as e:
        logger.error("Unexpected error in video API: %s", str(e), exc_info=True)
        # Re-raise with a user-friendly message, but keep the original exception for logs
        raise RuntimeError(f"🚨 Unexpected error: {str(e)}") from e
    finally:
        # Crucial cleanup: remove the temporary cookie file if it was created
        if cookie_file_path and os.path.exists(cookie_file_path):
            os.remove(cookie_file_path)
            logger.info(f"Temporary cookie file deleted: {cookie_file_path}", exc_info=True)

