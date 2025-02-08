import streamlit as st
import time
import internetarchive
import io
import requests
from PIL import Image
import webbrowser
import musicbrainzngs
from datetime import date
import random
import logging
import os
import re
import importlib
from duckduckgo_search import DDGS
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import proxies

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Constants
USER_AGENT = "ArchiveOrgSearcher/1.0 (testing@example.com)"  # Replace with your email
MUSICBRAINZ_LIMIT = None  # 20 # Removed limit
MAX_RETRIES = 3
AUDIO_EXTENSIONS = ('.mp3', '.wav', '.flac', '.ogg')
TEXT_EXTENSIONS = ('.txt', '.epub', '.html', '.htm', '.md')
PDF_EXTENSION = '.pdf'
DEFAULT_THUMBNAIL = "placeholder.png"  # Optional placeholder image
DEFAULT_SELECT_OPTION = "Select an option"
# MusicBrainz Configuration
musicbrainzngs.set_useragent("ArchiveOrgSearch", "1.0", "your_email@example.com")
# --- Helper Functions ---
def handle_request_error(e, message="Request failed"):
    logging.error(f"{message}: {e}")
    return None
def retry_with_backoff(func, args=(), max_retries=1, initial_delay=1):
    """Retries a function with exponential backoff."""
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
                st.warning(f"Error executing {func.__name__}: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return None
@st.cache_data(ttl=3600)
def search_archive(search_term, media_type, start_year=None):
    """Searches archive.org with optional year filtering and fetches all necessary metadata."""
    try:
        ia = internetarchive.ArchiveSession()
        query = f'({search_term}) AND mediatype:{media_type}'
        if start_year:
            query += f' AND date:[{start_year}-01-01 TO {start_year}-12-31]'
        # Include 'mediatype' in the fields to avoid fetching it later
        search_results = ia.search_items(query=query, fields=['identifier', 'title', 'creator', 'image', 'mediatype'])
        results_list = [dict(result) for result in search_results]
        return results_list
    except Exception as e:
        st.error(f"Error during search: {e}")
        return []
# Proxy functions (moved to top for clarity)
@st.cache_data(ttl=3600)
def search_archive_with_duckduckgo(search_term, media_type, start_year=None, max_results=60, max_retries=5, use_proxy=False):
    """Searches archive.org using DuckDuckGo and fetches all necessary metadata."""
    ddg_results_enriched = []
    ddg_query = f"{search_term} site:archive.org"
    ddg_results = []
    retries = 0
    delay = 1
    proxy_address = "socks5h://customer-irawrz_z9zc0-sessid-0375393949-sesstime-10:Moomoocow11=@pr.oxylabs.io:7777"
    print(proxy_address)
    while retries <= max_retries:
        try:
            ddgs_instance = DDGS(proxy=proxy_address)  # Pass proxy to DDGS
            with ddgs_instance as ddgs:
                for r in ddgs.text(ddg_query, max_results=max_results):
                    ddg_results.append(r)
            break
        except Exception as e:
            if "Ratelimit" in str(e):
                retries += 1
                if retries > max_retries:
                    print("Max retries reached. DuckDuckGo search failed.")
                    break
                else:
                    sleep_time = delay * (2 * (retries - 1)) + random.uniform(0, 1)
                    print(f"Rate limit encountered. Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                    delay = 1  # Reset delay after exception
            else:
                print(f"An unexpected error occurred during DuckDuckGo search: {e}")
                break
    # Extract Archive.org identifiers from DuckDuckGo results
    ddg_identifiers = set()
    for result in ddg_results:
        url = result.get('href', '')
        if "archive.org/details/" in url:
            parts = url.split("details/")
            if len(parts) > 1:
                identifier = parts[1].split("/")[0]
                ddg_identifiers.add(identifier)
        elif "archive.org/download/" in url:
            parts = url.split("download/")
            if len(parts) > 1:
                identifier = parts[1].split("/")[0]
                ddg_identifiers.add(identifier)
    # Fetch item details concurrently
    def fetch_item(identifier):
        try:
            item = internetarchive.get_item(identifier)
            item_metadata = item.metadata
            item_mediatype = item_metadata.get('mediatype', '').lower()
            if item_mediatype == media_type.lower():
                return {
                    'identifier': identifier,
                    'title': item_metadata.get('title', identifier),
                    'creator': item_metadata.get('creator', ''),
                    'image': f"https://archive.org/services/img/{identifier}",
                    'mediatype': item_mediatype,
                    'source': 'duckduckgo'
                }
        except Exception as e:
            print(f"Error fetching item details for {identifier}: {e}")
        return None
    with ThreadPoolExecutor(max_workers=50) as executor:
        future_to_id = {executor.submit(fetch_item, id_): id_ for id_ in ddg_identifiers}
        for future in as_completed(future_to_id):
            item = future.result()
            if item:
                ddg_results_enriched.append(item)
    return ddg_results_enriched
@st.cache_resource
def get_thumbnail_image(url):
    """Fetches and caches the thumbnail image."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        return image
    except:
        return None
@st.cache_data
def get_item_files(identifier):
    """Retrieves and caches files associated with an item on archive.org."""
    try:
        item = internetarchive.get_item(identifier)
        files = [dict(file) for file in item.files]
        return files
    except Exception as e:
        logging.error(f"Error retrieving item files: {e}")
        return []
def filter_results_by_file_types(results, file_types_str):
    """Filters search results based on specified file types."""
    if not file_types_str:
        return results
    file_types = set([ft.lower() for ft in file_types_str.split()])
    def check_file_types(identifier, file_types):
        try:
            files = get_item_files(identifier)
            return any(file['name'].lower().endswith(tuple(f".{ft}" for ft in file_types)) for file in files)
        except Exception as e:
            logging.error(f"Error checking file types for {identifier}: {e}")  # Log the error
            return False  # Assume no match if there's an error
    with ThreadPoolExecutor(max_workers=50) as executor:
        # Pass file_types to the check_file_types function
        future_to_id = {executor.submit(check_file_types, result['identifier'], file_types): result['identifier'] for result in results}
        filtered_results = []
        for future in as_completed(future_to_id):
            identifier = future_to_id[future]
            try:
                if future.result():
                    filtered_results.append(next(result for result in results if result['identifier'] == identifier))
            except Exception as e:
                logging.error(f"Error processing result for {identifier}: {e}")
    return filtered_results
def download_file(url, filename):
    """Downloads a file from the given URL."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        handle_request_error(e, "Error downloading file")
        return None
def display_pdf_preview(result, files):
    """Displays a PDF preview section with a dropdown to select PDF files."""
    pdf_files = [file for file in files if file['name'].lower().endswith(PDF_EXTENSION)]
    if pdf_files:
        st.subheader("PDF Preview")
        selected_pdf_name = st.selectbox(
            "Select PDF File:",
            options=[file['name'] for file in pdf_files],
            key=f"pdf_select_{result['identifier']}",
        )
        if selected_pdf_name:
            selected_pdf_url = f"https://archive.org/download/{result['identifier']}/{selected_pdf_name}"
            try:
                st.markdown(
                    f'<iframe src="{selected_pdf_url}" style="width:100%;height:300px;"></iframe>',
                    unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error displaying PDF: {e}")
def display_result_details(result, media_type):
    """Displays details of a selected result, including audio player and file selection."""
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader(result['title'])
        thumbnail_url = get_thumbnail_url(result['identifier'])
        if thumbnail_url:
            image = get_thumbnail_image(thumbnail_url)
            if image:
                st.image(image, caption=f"Image for {result['title']}", width=180)
            else:
                st.write("No image available.")
        else:
            st.write("No image available.")
        if 'creator' in result and result['creator']:
            st.write(f"**Creator:** {result['creator']}")
        st.write(f"**Identifier:** {result['identifier']}")
        item_url = f"https://archive.org/details/{result['identifier']}"
        st.markdown(f"[View on Archive.org]({item_url})")
    with col2:
        with st.spinner(f"Retrieving files for '{result['title']}'..."):
            files = get_item_files(result['identifier'])
            if not files:
                st.warning("No files found for this item.")
                return
            if media_type == "audio":
                audio_files = [file for file in files if file['name'].lower().endswith(AUDIO_EXTENSIONS)]
                if audio_files:
                    st.subheader("Audio Player")
                    selected_track_name = st.selectbox(
                        "Select Track:",
                        options=[file['name'] for file in audio_files],
                        key=f"track_select_{result['identifier']}",
                    )
                    if selected_track_name:
                        selected_audio_url = f"https://archive.org/download/{result['identifier']}/{selected_track_name}"
                        try:
                            response = requests.head(selected_audio_url, allow_redirects=True)
                            response.raise_for_status()
                            audio_html = f"""
                                <audio controls autoplay style="width: 100%;">
                                    <source src="{selected_audio_url}" type="audio/{selected_audio_url.split('.')[-1]}">
                                    Your browser does not support the audio element.
                                </audio>
                            """
                            st.markdown(audio_html, unsafe_allow_html=True)
                        except requests.exceptions.RequestException as e:
                            logging.error(f"Error loading audio: {e}")
                            st.error("Error loading audio.  Check the console for details.")
            elif media_type == "texts":
                display_pdf_preview(result, files)
            # File selection is always shown, regardless of media type
            st.subheader("Files:")
            selected_file = st.selectbox("Select a file to download:", [file['name'] for file in files],
                                          key=f"file_select_{result['identifier']}")
            if selected_file:
                selected_file_data = next((file for file in files if file['name'] == selected_file), None)
                download_url = f"https://archive.org/download/{result['identifier']}/{selected_file_data['name']}"
                with st.spinner(f"Downloading '{selected_file}'..."):
                    file_bytes = download_file(download_url, selected_file)
                    if file_bytes:
                        st.download_button(
                            label=f"Download '{selected_file}'",
                            data=file_bytes,
                            file_name=selected_file,
                            mime="application/octet-stream",
                            key=f"download_button_{result['identifier']}_{selected_file}"
                        )
                    else:
                        st.warning(f"Download of '{selected_file}' failed.")
def get_thumbnail_url(identifier):
    """Constructs the thumbnail URL."""
    return f"https://archive.org/services/img/{identifier}"
def get_zip_download_url(identifier):
    """Constructs the zip download URL."""
    return f"https://archive.org/compress/{identifier}"
# --- Streamlit UI ---
st.title("Archive.org Search")
# Initialize session state
if 'musicbrainz_results' not in st.session_state:
    st.session_state.musicbrainz_results = []
if 'selected_album' not in st.session_state:
    st.session_state.selected_album = None
if 'use_album_year' not in st.session_state:
    st.session_state.use_album_year = False
if 'selected_result_identifier' not in st.session_state:
    st.session_state.selected_result_identifier = None
if 'audible_results' not in st.session_state:
    st.session_state.audible_results = []
if 'search_term_input' not in st.session_state:
    st.session_state.search_term_input = ""
if 'ia_results' not in st.session_state:
    st.session_state.ia_results = []
if 'use_ddg_search' not in st.session_state:
    st.session_state.use_ddg_search = True
if 'results' not in st.session_state:
    st.session_state.results = []
if 'filtered_results' not in st.session_state:
    st.session_state.filtered_results = []
if 'selected_media_type' not in st.session_state:
    st.session_state.selected_media_type = "audio"
if 'file_types_filter' not in st.session_state:
    st.session_state.file_types_filter = ""
# Dynamically load tools from the 'tools' directory ONCE
tools_dir = "tools"
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
# Sidebar for Tools
with st.sidebar:
    st.header("Tools")
    st.checkbox("Enable DuckDuckGo Search", key="use_ddg_search", value=st.session_state.use_ddg_search)
    use_proxy_ddg = st.checkbox("Use Proxy with DuckDuckGo", value=False)  # New checkbox for proxy
    # Load tools dynamically
    for module in tool_modules:
        if hasattr(module, 'album_search_tool'):
            module.album_search_tool(retry_with_backoff)
        if hasattr(module, 'audible_search_tool'):
            module.audible_search_tool(retry_with_backoff)
# Function to display results
def display_results(results, media_type):
    if not results:
        st.info("No results found.")
        return
    num_columns = 5
    cols = st.columns(num_columns)
    # Fetch all thumbnails concurrently to speed up loading
    def fetch_image(url):
        try:
            return get_thumbnail_image(url)
        except Exception as e:
            logging.error(f"Error fetching image from {url}: {e}")
            return None
    thumbnails = {}
    with ThreadPoolExecutor(max_workers=50) as executor:
        future_to_id = {executor.submit(fetch_image, get_thumbnail_url(result['identifier'])): result['identifier'] for result in results}
        for future in as_completed(future_to_id):
            identifier = future_to_id[future]
            try:
                thumbnails[identifier] = future.result()
            except Exception as e:
                logging.error(f"Error getting thumbnail for {identifier}: {e}")
                thumbnails[identifier] = None # set thumbnail to None in case of error
    for i, result in enumerate(results):
        identifier = result['identifier']
        with cols[i % num_columns]:
            if thumbnails.get(identifier):
                st.image(thumbnails[identifier], use_container_width=True)
            else:
                st.image(DEFAULT_THUMBNAIL, use_container_width=True)
            st.caption(f"{result['title']} (Source: {result['source']})")
            if st.button("Details", key=f"details_button_{identifier}"):
                set_selected_result(identifier)
# Function to set the selected result
def set_selected_result(identifier):
    st.session_state.selected_result_identifier = identifier
# Main Search Section
with st.form("search_form"):
    if st.session_state.get("selected_album"):
        search_term = f"{st.session_state.selected_album['artist']} {st.session_state.selected_album['title']}"
        st.write(f"Searching for: '{search_term}'")
    elif st.session_state.get("selected_book"):
        search_term = f"{st.session_state.selected_book['author']} {st.session_state.selected_book['title']}"
        st.write(f"Searching for: '{search_term}'")
    else:
        search_term = st.text_input("Enter Search Term:", key="search_term_manual_input",
                                     value=st.session_state.get("search_term_input", ""))
    # Media Type Selection
    media_type = st.radio(
        "Select Media Type:",
        ["audio", "texts", "collections", "movies"],
        key="media_type_radio",
        horizontal=True
    )
    media_type_mapping = {
        "audio": "audio",
        "texts": "texts",
        "collections": "collection",
        "movies": "movies"
    }
    selected_media_type = media_type_mapping[media_type]
    # File Type Filter (Dropdown)
    with st.expander("Filter by File Type", expanded=False):
        file_type_options = ["", "mp3", "flac", "pdf", "wav", "ogg", "zip"]
        file_types_filter = st.selectbox(
            "Select File Type:",
            options=file_type_options,
            key="file_types_select"
        )
    # Year Filter (Simplified)
    with st.expander("Year Filter", expanded=False):
        start_year_str = st.text_input("Year (Optional):", key="start_year_input", value="")
        if st.session_state.get("selected_album"):
            st.session_state.use_album_year = st.checkbox("Use Album Release Year",
                                                           value=st.session_state.use_album_year)
        start_year = None
        if st.session_state.use_album_year and st.session_state.get("selected_album"):
            start_year = st.session_state.selected_album['year']
            st.write(f"Using album release year: {start_year}")
        else:
            if start_year_str:
                try:
                    start_year = int(start_year_str)
                except ValueError:
                    st.error("Invalid year format. Please enter a number.")
    # Search and Clear Buttons
    col_search, col_clear = st.columns([1, 1])
    with col_search:
        search_trigger = st.form_submit_button("Search")
    with col_clear:
        clear_trigger = st.form_submit_button("Clear Search")
# Display the details panel above the search results
if st.session_state.selected_result_identifier:
    selected_result = next(
        (
            result for result in st.session_state.filtered_results
            if result['identifier'] == st.session_state.selected_result_identifier
        ),
        None
    )
    if selected_result:
        display_result_details(selected_result, st.session_state.selected_media_type)
    else:
        st.error("Selected result not found.")
        st.session_state.selected_result_identifier = None
# Clear Search Logic
if clear_trigger:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
# Trigger Search Logic
if search_trigger:
    # Update stored search parameters
    st.session_state.search_term_input = search_term
    st.session_state.selected_media_type = selected_media_type
    st.session_state.file_types_filter = file_types_filter
    st.session_state.start_year = start_year
    # Perform the search
    with st.spinner(f"Searching Archive.org for '{search_term}'..."):
        ia_results = search_archive(search_term, selected_media_type, start_year=start_year)
        for result in ia_results:
            result['source'] = 'archive_api'
        st.session_state.ia_results = ia_results
    # Then, search DuckDuckGo (if there are IA results and DDG Search is enabled)
    if st.session_state.use_ddg_search:
        with st.spinner(f"Searching DuckDuckGo for '{search_term}'..."):
            ddg_results = search_archive_with_duckduckgo(search_term, selected_media_type, start_year=start_year, use_proxy=use_proxy_ddg)  # Pass use_proxy flag
            # Combine IA results and DDG results
            combined_results = ia_results.copy()
            existing_identifiers = {item['identifier'] for item in ia_results}
            combined_results.extend([item for item in ddg_results if item['identifier'] not in existing_identifiers])
            st.session_state.results = combined_results
            # Apply file type filtering
            filtered_results = filter_results_by_file_types(combined_results, file_types_filter) if file_types_filter else combined_results
            st.session_state.filtered_results = filtered_results
    else:
        if not st.session_state.use_ddg_search:
            st.info("DuckDuckGo search is disabled via sidebar toggle.")
        elif not ia_results:
            st.info("No results from Archive.org, skipping DuckDuckGo search.")
        st.session_state.results = ia_results
        st.session_state.filtered_results = ia_results
    # Display the combined and filtered results
    display_results(st.session_state.filtered_results, st.session_state.selected_media_type)
# Display cached results if available and not currently performing a search
if not search_trigger and st.session_state.filtered_results:
    with st.spinner("Loading cached results..."):
        display_results(st.session_state.filtered_results, st.session_state.selected_media_type)