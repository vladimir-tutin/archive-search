import streamlit as st
import time
import internetarchive
import io
import requests
from PIL import Image
import base64
import re

def search_archive(search_term, media_type):
    """Searches archive.org for audiobooks or ebooks."""
    try:
        ia = internetarchive.ArchiveSession()
        search_results = ia.search_items(
            query=f'({search_term}) AND mediatype:{media_type}',
            fields=['identifier', 'title', 'creator', 'image']
        )
        results = [dict(item) for item in search_results]
        return results
    except Exception as e:
        st.error(f"Error during search: {e}")
        return []

def get_item_files(identifier):
    """Retrieves the files associated with an item on archive.org."""
    try:
        item = internetarchive.get_item(identifier)
        return [dict(file) for file in item.files]
    except Exception as e:
        st.error(f"Error retrieving item files: {e}")
        return []

def filter_results_by_file_types(results, file_types_str):
    """Filters search results to only include items with specified file types."""
    if not file_types_str:
        return results
    file_types = file_types_str.lower().split()
    filtered_results = []
    for result in results:
        files = get_item_files(result['identifier'])
        if any(file['name'].lower().endswith(tuple(file_types)) for file in files):
            filtered_results.append(result)
    return filtered_results

def download_file(url, filename):
    """Downloads a file from the given URL and returns it as bytes."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading file: {e}")
        return None

def display_result_details(result):
    """Displays the details of a selected result."""
    st.subheader(result['title'])
    if 'creator' in result:
        st.write(f"**Creator:** {result['creator']}")
    st.write(f"**Identifier:** {result['identifier']}")
    item_url = f"https://archive.org/details/{result['identifier']}"
    st.markdown(f"[View on Archive.org]({item_url})")
    if 'image' in result:
        st.image(result['image'], caption=f"Image for {result['title']}", use_container_width=True)
    else:
        st.write("No image available.")

    files = get_item_files(result['identifier'])
    if files:
        audio_files = [file for file in files if file['name'].lower().endswith(('.mp3', '.wav', '.flac', '.ogg'))]
        if audio_files:
            st.subheader("Audio Player")
            audio_urls = [f"https://archive.org/download/{result['identifier']}/{file['name']}" for file in audio_files]
            playlist_html = f"""
                <audio controls autoplay>
                    {''.join([f'<source src="{url}" type="audio/{url.split(".")[-1]}">' for url in audio_urls])}
                    Your browser does not support the audio element.
                </audio>
            """
            st.components.v1.html(playlist_html, height=100)

        st.subheader("Files:")
        file_names = [file['name'] for file in files]
        selected_file = st.selectbox("Select a file to download:", file_names, key=f"file_select_{result['identifier']}")
        if selected_file:
            selected_file_data = next((file for file in files if file['name'] == selected_file), None)
            download_url = f"https://archive.org/download/{result['identifier']}/{selected_file_data['name']}"
            file_bytes = download_file(download_url, selected_file)
            if file_bytes:
                st.download_button(
                    label=f"Download '{selected_file}'",
                    data=file_bytes,
                    file_name=selected_file,
                    mime="application/octet-stream",
                    key=f"download_button_{result['identifier']}_{selected_file}",
                )
    else:
        st.warning("No files found for this item.")

def get_thumbnail_url(identifier):
    """Retrieves the URL of the thumbnail image for a given item identifier."""
    return f"https://archive.org/services/img/{identifier}"

def get_zip_download_url(identifier):
    """Constructs the correct zip download URL for an item from archive.org."""
    return f"https://archive.org/compress/{identifier}"

# Streamlit UI
st.title("Archive.org Search")

# Search Term Input
search_term = st.text_input("Enter Search Term:", key="search_term_input")

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

# File Types Filter
file_types_filter = st.text_input("Filter by File Types (space-separated, e.g., mp3 flac pdf):", key="file_types_input")

# Search Button
if st.button("Search", key="search_button"):
    if not search_term:
        st.warning("Please enter a search term.")
    else:
        with st.spinner(f"Searching Archive.org for '{search_term}'..."):
            results = search_archive(search_term, selected_media_type)
            filtered_results = filter_results_by_file_types(results, file_types_filter)
            st.session_state.results = filtered_results
            if filtered_results:
                st.success(f"Found {len(filtered_results)} results:")
            else:
                st.warning("No results found matching the specified file types.")

# Display Results
if 'results' in st.session_state and st.session_state.results:
    num_columns = 5
    cols = st.columns(num_columns)
    for i, result in enumerate(st.session_state.results):
        with cols[i % num_columns]:
            thumbnail_url = get_thumbnail_url(result['identifier'])
            if thumbnail_url:
                try:
                    response = requests.get(thumbnail_url)
                    response.raise_for_status()
                    image = Image.open(io.BytesIO(response.content))
                    zip_download_url = get_zip_download_url(result['identifier'])
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
                    st.caption(result['title'])
                except:
                    st.write(result['title'])
            else:
                st.write(result['title'])

            if st.button(f"Show Details", key=f"details_{i}"):
                st.session_state.selected_result = result
                st.rerun()

# Popup Panel Logic
if 'selected_result' in st.session_state and st.session_state.selected_result:
    st.markdown(
        """
        <style>
        .overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 9998;
        }
        .popup {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            z-index: 9999;
            width: 80%;
            max-height: 80%;
            overflow: auto;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="overlay"></div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="popup">', unsafe_allow_html=True)
        display_result_details(st.session_state.selected_result)
        if st.button("Close", key="close_button"):
            del st.session_state.selected_result
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
