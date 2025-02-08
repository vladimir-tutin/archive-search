import os
import re
import io
import time
import random
import logging
import requests
import importlib
from datetime import date
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st
import internetarchive
import musicbrainzngs
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

USER_AGENT = "ArchiveOrgSearcher/1.0 (testing@example.com)"
MUSICBRAINZ_LIMIT = None
MAX_RETRIES = 3
PROXY_ADDRESS = "socks5h://customer-irawrz_z9zc0-sessid-0375393949-sesstime-10:Moomoocow11=@pr.oxylabs.io:7777"

AUDIO_EXTENSIONS = ('.mp3', '.wav', '.flac', '.ogg')
TEXT_EXTENSIONS = ('.txt', '.epub', '.html', '.htm', '.md', '.pdf')
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv')
SOFTWARE_EXTENSIONS = ('.exe', '.msi', '.dmg', '.zip', '.tar', '.gz', '.bin', '.rpm', '.deb')

DEFAULT_THUMBNAIL = "placeholder.png"
DEFAULT_SELECT_OPTION = "Select an option"

musicbrainzngs.set_useragent("ArchiveOrgSearch", "1.0", "your_email@example.com")

def handle_request_error(e, message="Request failed"):
    logging.error(f"{message}: {e}")
    st.error(f"{message}: {e}")
    return None

def retry_with_backoff(func, args=(), max_retries=MAX_RETRIES, initial_delay=1):
    retries = 0
    delay = initial_delay
    while retries < max_retries:
        try:
            return func(*args)
        except requests.exceptions.RequestException as e:
            retries += 1
            if retries == max_retries:
                st.error(
                    f"Max retries reached. Failed to execute {func.__name__} after multiple attempts. Last error: {e}"
                )
                return None
            else:
                st.warning(
                    f"Error executing {func.__name__}: {e}. Retrying in {delay} seconds..."
                )
                time.sleep(delay)
                delay *= 2
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return None

@st.cache_data(ttl=3600)
def search_archive(search_term, media_type, start_year=None):
    try:
        ia = internetarchive.ArchiveSession()
        query = f'({search_term}) AND mediatype:{media_type}'
        if start_year:
            query += f' AND date:[{start_year}-01-01 TO {start_year}-12-31]'

        search_results = ia.search_items(query=query, fields=['identifier', 'title', 'creator', 'image', 'mediatype'])
        results_list = [dict(result) for result in search_results]
        return results_list
    except Exception as e:
        st.error(f"Error during search: {e}")
        return []

@st.cache_data(ttl=3600)
def search_archive_with_duckduckgo(search_term, media_type, start_year=None, max_results=60, max_retries=5, use_proxy=False):
    ddg_results_enriched = []
    ddg_query = f"{search_term} site:archive.org"
    ddg_results = []
    retries = 0
    delay = 1

    while retries <= max_retries:
        try:
            ddgs_instance = DDGS(proxy=PROXY_ADDRESS) if use_proxy else DDGS()
            for r in ddgs_instance.text(ddg_query, max_results=max_results):
                ddg_results.append(r)
            break
        except Exception as e:
            if "Ratelimit" in str(e):
                retries += 1
                if retries > max_retries:
                    logging.error("Max retries reached. DuckDuckGo search failed.")
                    break
                sleep_time = delay * (2 ** (retries - 1)) + random.uniform(0, 1)
                logging.warning(f"Rate limit encountered. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                logging.error(f"Unexpected error during DuckDuckGo search: {e}")
                break

    ddg_identifiers = set()
    for result in ddg_results:
        url = result.get('href', '')
        match = re.search(r'archive\.org/(details|download)/([^/]+)', url)
        if match:
            identifier = match.group(2)
            ddg_identifiers.add(identifier)

    def fetch_item(identifier):
        try:
            item = internetarchive.get_item(identifier)
            metadata = item.metadata
            if metadata.get('mediatype', '').lower() == media_type.lower():
                return {
                    'identifier': identifier,
                    'title': metadata.get('title', identifier),
                    'creator': metadata.get('creator', ''),
                    'image': f"https://archive.org/services/img/{identifier}",
                    'mediatype': metadata.get('mediatype', ''),
                    'source': 'duckduckgo'
                }
        except Exception as e:
            logging.error(f"Error fetching item details for {identifier}: {e}")
        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_item, id_): id_ for id_ in ddg_identifiers}
        for future in as_completed(futures):
            item = future.result()
            if item:
                ddg_results_enriched.append(item)

    return ddg_results_enriched

@st.cache_resource
def get_thumbnail_image(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content))
    except Exception as e:
        logging.error(f"Error fetching thumbnail image: {e}")
        return None

@st.cache_data
def get_item_files(identifier):
    try:
        item = internetarchive.get_item(identifier)
        return [dict(file) for file in item.files]
    except Exception as e:
        logging.error(f"Error retrieving item files for {identifier}: {e}")
        return []

def filter_results_by_file_types(results, file_types_str):
    if not file_types_str:
        return results
    file_types = set(ft.lower() for ft in file_types_str.split())

    def check_file_types(identifier):
        try:
            files = get_item_files(identifier)
            return any(file['name'].lower().endswith(tuple(f".{ft}" for ft in file_types)) for file in files)
        except Exception as e:
            logging.error(f"Error checking file types for {identifier}: {e}")
            return False

    filtered = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(check_file_types, res['identifier']): res['identifier'] for res in results}
        for future in as_completed(future_to_id):
            identifier = future_to_id[future]
            if future.result():
                filtered.append(next(res for res in results if res['identifier'] == identifier))
    return filtered

def download_file(url, filename):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        handle_request_error(e, "Error downloading file")
        return None

def display_pdf_preview(identifier, files):
    pdf_files = [file for file in files if file['name'].lower().endswith('.pdf')]
    if pdf_files:
        st.subheader("PDF Preview")
        selected_pdf = st.selectbox(
            "Select PDF File:",
            options=[file['name'] for file in pdf_files],
            key=f"pdf_select_{identifier}",
        )
        if selected_pdf:
            selected_pdf_url = f"https://archive.org/download/{identifier}/{selected_pdf}"
            st.markdown(
                f'<iframe src="{selected_pdf_url}" style="width:100%;height:300px;"></iframe>',
                unsafe_allow_html=True
            )

def display_media_player(media_type, identifier, files):
    if media_type == "audio":
        audio_files = [file for file in files if file['name'].lower().endswith(AUDIO_EXTENSIONS)]
        if audio_files:
            st.subheader("Audio Player")
            selected_audio = st.selectbox(
                "Select Track:",
                options=[file['name'] for file in audio_files],
                key=f"audio_select_{identifier}",
            )
            if selected_audio:
                audio_url = f"https://archive.org/download/{identifier}/{selected_audio}"
                audio_type = selected_audio.split('.')[-1]
                st.audio(audio_url, format=f'audio/{audio_type}')
    elif media_type == "texts":
        display_pdf_preview(identifier, files)
    elif media_type == "movies":
        video_files = [file for file in files if file['name'].lower().endswith(VIDEO_EXTENSIONS)]
        if video_files:
            st.subheader("Video Player")
            selected_video = st.selectbox(
                "Select Video File:",
                options=[file['name'] for file in video_files],
                key=f"video_select_{identifier}",
            )
            if selected_video:
                video_url = f"https://archive.org/download/{identifier}/{selected_video}"
                video_type = selected_video.split('.')[-1]
                st.video(video_url, format=f'video/{video_type}')
    elif media_type == "software":
        software_files = [file for file in files if file['name'].lower().endswith(SOFTWARE_EXTENSIONS)]
        if software_files:
            st.subheader("Software Downloads")
            selected_software = st.selectbox(
                "Select Software File:",
                options=[file['name'] for file in software_files],
                key=f"software_select_{identifier}",
            )
            if selected_software:
                software_url = f"https://archive.org/download/{identifier}/{selected_software}"
                display_download_button(media_type, identifier, selected_software)

def display_download_button(media_type, identifier, file_name):
    download_url = f"https://archive.org/download/{identifier}/{file_name}"
    button_label = f"Download '{file_name}'"
    button_style = (
        "background-color: #4CAF50; color: white; padding: 10px 24px;"
        "border: none; border-radius: 4px; cursor: pointer; margin-top: 10px;"
    )
    st.markdown(
        f"""
        <a href="{download_url}" download="{file_name}">
            <button style="{button_style}">{button_label}</button>
        </a>
        """,
        unsafe_allow_html=True
    )

def display_result_details(result, media_type):
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader(result['title'])
        thumbnail_url = get_thumbnail_url(result['identifier'])
        thumbnail = get_thumbnail_image(thumbnail_url)
        if thumbnail:
            st.image(thumbnail, caption=f"Image for {result['title']}", width=180)
        else:
            st.image(DEFAULT_THUMBNAIL)

        if result.get('creator'):
            st.write(f"**Creator:** {result['creator']}")
        st.write(f"**Identifier:** {result['identifier']}")
        st.markdown(f"[View on Archive.org](https://archive.org/details/{result['identifier']})")

    with col2:
        with st.spinner(f"Retrieving files for '{result['title']}'..."):
            files = get_item_files(result['identifier'])
            if not files:
                st.warning("No files found for this item.")
                return

        display_media_player(media_type, result['identifier'], files)

        st.subheader("Files:")
        selected_file = st.selectbox(
            "Select a file to download:",
            options=[file['name'] for file in files],
            key=f"file_select_{result['identifier']}"
        )
        if selected_file:
            display_download_button(media_type, result['identifier'], selected_file)

def get_thumbnail_url(identifier):
    return f"https://archive.org/services/img/{identifier}"

def load_tools(tools_dir="tools"):
    tool_modules = []
    if os.path.exists(tools_dir) and os.path.isdir(tools_dir):
        tool_files = sorted([f[:-3] for f in os.listdir(tools_dir) if f.endswith(".py")])
        for tool_file in tool_files:
            try:
                module = importlib.import_module(f"{tools_dir}.{tool_file}")
                tool_modules.append(module)
                logging.info(f"Loaded tool module: {tool_file}")
            except Exception as e:
                st.error(f"Error loading tool {tool_file}: {e}")
    return tool_modules

def main():
    st.title("Archive.org Search")

    session_defaults = {
        'musicbrainz_results': [],
        'selected_album': None,
        'use_album_year': False,
        'selected_result_identifier': None,
        'audible_results': [],
        'search_term_input': "",
        'ia_results': [],
        'use_ddg_search': True,
        'results': [],
        'filtered_results': [],
        'selected_media_type': "audio",
        'file_types_filter': ""
    }
    for key, default in session_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    tools_dir = "tools"
    tool_modules = load_tools(tools_dir)

    with st.sidebar:
        st.header("Tools")
        st.checkbox("Enable DuckDuckGo Search", key="use_ddg_search", value=st.session_state.use_ddg_search)
        use_proxy_ddg = st.checkbox("Use Proxy with DuckDuckGo", value=True)

        for module in tool_modules:
            if hasattr(module, 'album_search_tool'):
                module.album_search_tool(retry_with_backoff)
            if hasattr(module, 'audible_search_tool'):
                module.audible_search_tool(retry_with_backoff)

    with st.form("search_form"):
        if st.session_state.get("selected_album"):
            search_term = f"{st.session_state.selected_album['artist']} {st.session_state.selected_album['title']}"
            st.write(f"Searching for: '{search_term}'")
        elif st.session_state.get("selected_book"):
            search_term = f"{st.session_state.selected_book['author']} {st.session_state.selected_book['title']}"
            st.write(f"Searching for: '{search_term}'")
        else:
            search_term = st.text_input("Enter Search Term:", key="search_term_manual_input", value=st.session_state.search_term_input)

        media_type = st.radio(
            "Select Media Type:",
            ["audio", "texts", "collections", "movies", "software"],
            key="media_type_radio",
            horizontal=True
        )
        media_type_mapping = {
            "audio": "audio",
            "texts": "texts",
            "collections": "collection",
            "movies": "movies",
            "software": "software"
        }
        selected_media_type = media_type_mapping[media_type]

        with st.expander("Filter by File Type", expanded=False):
            file_type_options = ["", "mp3", "flac", "pdf", "wav", "ogg", "zip", "exe", "msi", "dmg", "tar", "gz", "bin", "rpm", "deb"]
            file_types_filter = st.selectbox(
                "Select File Type:",
                options=file_type_options,
                key="file_types_select"
            )

        with st.expander("Year Filter", expanded=False):
            start_year_str = st.text_input("Year (Optional):", key="start_year_input", value="")
            if st.session_state.get("selected_album"):
                st.session_state.use_album_year = st.checkbox(
                    "Use Album Release Year",
                    value=st.session_state.use_album_year
                )
                start_year = st.session_state.selected_album.get('year') if st.session_state.use_album_year else None
                if start_year:
                    st.write(f"Using album release year: {start_year}")
            else:
                start_year = None
                if start_year_str:
                    try:
                        start_year = int(start_year_str)
                    except ValueError:
                        st.error("Invalid year format. Please enter a number.")

        col_search, col_clear = st.columns([1, 1])
        with col_search:
            search_trigger = st.form_submit_button("Search")
        with col_clear:
            clear_trigger = st.form_submit_button("Clear Search")

    if st.session_state.selected_result_identifier:
        selected_result = next(
            (res for res in st.session_state.filtered_results if res['identifier'] == st.session_state.selected_result_identifier),
            None
        )
        if selected_result:
            display_result_details(selected_result, st.session_state.selected_media_type)
        else:
            st.error("Selected result not found.")
        st.session_state.selected_result_identifier = None

    if clear_trigger:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_rerun()

    if search_trigger:
        st.session_state.search_term_input = search_term
        st.session_state.selected_media_type = selected_media_type
        st.session_state.file_types_filter = file_types_filter
        st.session_state.start_year = start_year

        with st.spinner(f"Searching Archive.org for '{search_term}'..."):
            ia_results = search_archive(search_term, selected_media_type, start_year=start_year)
            for result in ia_results:
                result['source'] = 'archive_api'
            st.session_state.ia_results = ia_results

        if st.session_state.use_ddg_search:
            with st.spinner(f"Searching DuckDuckGo for '{search_term}'..."):
                ddg_results = search_archive_with_duckduckgo(
                    search_term,
                    selected_media_type,
                    start_year=start_year,
                    use_proxy=use_proxy_ddg
                )
                existing_ids = {item['identifier'] for item in ia_results}
                combined_results = ia_results.copy()
                combined_results.extend([item for item in ddg_results if item['identifier'] not in existing_ids])
                st.session_state.results = combined_results

                if file_types_filter:
                    filtered = filter_results_by_file_types(combined_results, file_types_filter)
                else:
                    filtered = combined_results
                st.session_state.filtered_results = filtered
        else:
            st.info("DuckDuckGo search is disabled via sidebar toggle.")
            st.session_state.results = st.session_state.ia_results
            st.session_state.filtered_results = st.session_state.ia_results

    if st.session_state.filtered_results:
        st.subheader("Search Results")
        num_columns = 5
        cols = st.columns(num_columns)

        thumbnails = {}
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_id = {
                executor.submit(get_thumbnail_image, get_thumbnail_url(res['identifier'])): res['identifier']
                for res in st.session_state.filtered_results
            }
            for future in as_completed(future_to_id):
                identifier = future_to_id[future]
                try:
                    thumbnails[identifier] = future.result()
                except Exception as e:
                    logging.error(f"Error getting thumbnail for {identifier}: {e}")
                    thumbnails[identifier] = None

        for i, result in enumerate(st.session_state.filtered_results):
            identifier = result['identifier']
            with cols[i % num_columns]:
                if thumbnails.get(identifier):
                    st.image(thumbnails[identifier])
                else:
                    st.image(DEFAULT_THUMBNAIL)
                st.caption(f"{result['title']} (Source: {result['source']})")
                if st.button("Details", key=f"details_button_{identifier}"):
                    st.session_state.selected_result_identifier = identifier

    elif not search_trigger and st.session_state.filtered_results:
        with st.spinner("Loading cached results..."):
            st.subheader("Cached Results")
            for result in st.session_state.filtered_results:
                display_result_details(result, st.session_state.selected_media_type)

if __name__ == "__main__":
    main()
