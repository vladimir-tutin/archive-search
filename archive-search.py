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
import logging  # Import the logging module
import os
import importlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
USER_AGENT = "ArchiveOrgSearch/1.0 (your_email@example.com)"  # Replace with your email
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
    st.error(f"{message}: {e}")

def retry_with_backoff(func, args=(), max_retries=3, initial_delay=1):
    """Retries a function with exponential backoff."""
    retries = 0
    delay = initial_delay
    while retries < max_retries:
        try:
            return func(*args)
        except requests.exceptions.RequestException as e:  #Catch specific exception
            retries += 1
            if retries == max_retries:
                st.error(f"Max retries reached.  Failed to execute {func.__name__} after multiple attempts. Last error: {e}")
                return None # or raise the exception if appropriate
            else:
                st.warning(f"Error executing {func.__name__}: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            return None #Or raise the exception

def search_archive(search_term, media_type, start_year=None):
    """Searches archive.org with optional year filtering."""
    try:
        ia = internetarchive.ArchiveSession()
        query = f'({search_term}) AND mediatype:{media_type}'
        date_range = None
        if start_year:
            try:
                start_date = date(start_year, 1, 1)
                end_date = date(start_year, 12, 31)
                date_range = f'[{start_date.strftime("%Y-%m-%d")} TO {end_date.strftime("%Y-%m-%d")}]'
            except ValueError:
                st.error("Invalid year.")
                return []
        if date_range:
            query += f' AND date:{date_range}'
        search_results = ia.search_items(query=query, fields=['identifier', 'title', 'creator', 'image'])
        results_list = [dict(result) for result in search_results]
        return results_list
    except Exception as e:
        st.error(f"Error during search: {e}")
        return []

def get_item_files(identifier):
    """Retrieves files associated with an item on archive.org."""
    try:
        item = internetarchive.get_item(identifier)
        files = [dict(file) for file in item.files]
        return files
    except Exception as e:
        st.error(f"Error retrieving item files: {e}")
        return []

def filter_results_by_file_types(results, file_types_str):
    """Filters search results based on specified file types."""
    if not file_types_str:
        return results
    file_types = set(file_types_str.lower().split())
    filtered_results = []
    for result in results:
        identifier = result['identifier']
        files = get_item_files(identifier)
        if files and any(file['name'].lower().endswith(tuple(f".{ft}" for ft in file_types)) for file in files):
            filtered_results.append(result)
    return filtered_results

def download_file(url, filename):
    """Downloads a file from the given URL."""
    try:
        response = requests.get(url, stream=True)  # Use stream for larger files
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
                    f'<iframe src="{selected_pdf_url}" style="width:100%;height:300px;"></iframe>',  # Reduced height to 300px
                    unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error displaying PDF: {e}")

def display_result_details(result, media_type):
    """Displays details of a selected result, including audio player and file selection."""
    #st.subheader(result['title']) #move
    col1, col2 = st.columns([1, 3]) #Change the second column size
    with col1:
        st.subheader(result['title']) #Moved here
        thumbnail_url = get_thumbnail_url(result['identifier'])
        if thumbnail_url:
            st.image(thumbnail_url, caption=f"Image for {result['title']}", width=220)
        else:
            st.write("No image available.")
        # Display creator, identifier, and link _below_ the thumbnail
        if 'creator' in result:
            st.write(f"**Creator:** {result['creator']}")
        st.write(f"**Identifier:** {result['identifier']}")
        item_url = f"https://archive.org/details/{result['identifier']}"
        st.markdown(f"[View on Archive.org]({item_url})")
    with col2:
        with st.spinner(f"Retrieving files for '{result['title']}'..."):
            files = get_item_files(result['identifier'])
            if not files:
                return
            if media_type == "audio":
                audio_files = [file for file in files if
                               file['name'].lower().endswith(tuple(AUDIO_EXTENSIONS))]
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
                            playlist_html = f"""
                                <div style="background-color: transparent; width: 75%;">
                                    <audio controls autoplay style="width: 100%;">
                                        <source src="{selected_audio_url}" type="audio/{selected_audio_url.split(".")[-1]}">
                                        Your browser does not support the audio element.
                                    </audio>
                                </div>
                            """
                            st.components.v1.html(playlist_html, height=50)
                        except requests.exceptions.RequestException as e:
                            handle_request_error(e, "Error loading audio")
            elif media_type == "texts":
                display_pdf_preview(result, files)
                # display_text_preview(result, files)  # removed
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
                        st.warning("No files found for this item.")

def get_thumbnail_url(identifier):
    """Retrieves the URL of the thumbnail image."""
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

# Dynamically load tools from the 'tools' directory ONCE
tools_dir = "tools"
tool_modules = []
if os.path.exists(tools_dir) and os.path.isdir(tools_dir):
    tool_files = sorted([f[:-3] for f in os.listdir(tools_dir) if f.endswith(".py")])  # Sort files alphabetically
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
    # Load tools dynamically
    for module in tool_modules:
        if hasattr(module, 'album_search_tool'):
            module.album_search_tool(retry_with_backoff)
        if hasattr(module, 'audible_search_tool'):
            module.audible_search_tool(retry_with_backoff)

# Main Search Section
if st.session_state.get("selected_album"):
    search_term = f"{st.session_state.selected_album['artist']} {st.session_state.selected_album['title']}"
    st.write(f"Searching for: '{search_term}'")  # Display search term
elif st.session_state.get("selected_book"):
    search_term = f"{st.session_state.selected_book['author']} {st.session_state.selected_book['title']}"
    st.write(f"Searching for: '{search_term}'")  # Display search term
else:
    search_term = st.text_input("Enter Search Term:", key="search_term_input", value=st.session_state.get("search_term_input", ""))

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
    file_type_options = ["", "mp3", "flac", "pdf", "wav", "ogg", "zip"]  # Add more options as needed
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

# Clear Search Button
if st.button("Clear Search", key="clear_search_button"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

# Trigger Search Logic (Simplified)
perform_search = False
if st.session_state.get("selected_album") or search_term:
    perform_search = True

if perform_search:
    if st.session_state.get("selected_album"):
        search_term_to_use = f"{st.session_state.selected_album['artist']} {st.session_state.selected_album['title']}"
    else:
        search_term_to_use = search_term

    with st.spinner(f"Searching Archive.org for '{search_term_to_use}'..."):
        start_year_to_use = None
        if st.session_state.use_album_year and st.session_state.get("selected_album"):
            start_year_to_use = st.session_state.selected_album['year']

        results = search_archive(search_term_to_use, selected_media_type, start_year=start_year_to_use)
        filtered_results = filter_results_by_file_types(results,
                                                          file_types_filter) if file_types_filter else results
        st.session_state.results = results
        st.session_state.filtered_results = filtered_results
else:
    if 'results' not in st.session_state:
        st.session_state.results = None

# Display the details panel _above_ the search results
if st.session_state.selected_result_identifier:
    selected_result = next((result for result in st.session_state.get("filtered_results", []) + st.session_state.get("musicbrainz_results", [])
                            if result['identifier'] == st.session_state.selected_result_identifier), None)
    if selected_result:
        display_result_details(selected_result, selected_media_type)
    else:
        st.error("Selected result not found.")
        st.session_state.selected_result_identifier = None

# Display results in a grid
if st.session_state.results:
    num_columns = 5
    cols = st.columns(num_columns)
    for i, result in enumerate(st.session_state.results):
        with cols[i % num_columns]:
            thumbnail_url = get_thumbnail_url(result['identifier'])
            zip_download_url = get_zip_download_url(result['identifier'])
            if thumbnail_url:
                try:
                    response = requests.get(thumbnail_url)
                    response.raise_for_status()
                    image = Image.open(io.BytesIO(response.content))
                    if zip_download_url:
                        st.markdown(
                            f"""
                            <div style="position: relative;">
                                <div style="height:200px; overflow: hidden;">
                                    <img src="{thumbnail_url}" style="width: 100%; object-fit: contain;">
                                </div>
                                <div style="position: absolute; bottom: 5px; right: 5px;">
                                    <a href="{zip_download_url}" download="{result['identifier']}.zip" style="background-color: #4CAF50; border: none; color: white; padding: 5px 10px; text-align: center; text-decoration: none; display: inline-block; font-size: 10px; cursor: pointer; border-radius: 5px;">Download Zip</a>
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        st.write("Download not available.")
                    st.caption(result['title'])
                except:
                    st.write(result['title'])
            else:
                st.write(result['title'])
            # Add a Streamlit button with a unique key
            if st.button("Details", key=f"details_button_{result['identifier']}"):
                st.session_state.selected_result_identifier = result['identifier']
