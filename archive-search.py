import streamlit as st
import time
import internetarchive
import io
import requests
from PIL import Image
import base64
import re
from datetime import date
import musicbrainzngs
import random
# Configure MusicBrainz
musicbrainzngs.set_useragent("ArchiveOrgSearch", "1.0", "your_email@example.com") # Replace with your email
def search_musicbrainz_album(album_title=None, artist_name=None, retry_count=0, max_retries=3):
    """Searches MusicBrainz for albums (release groups) with retry logic, handling missing artist/album."""
    try:
        query = ""
        if artist_name:
            query += f'artist:"{artist_name}"'
        if album_title:
            if query:
                query += " AND "
            query += f'release:"{album_title}"'
        if not query:
            st.warning("Please enter either an album title or artist name to search MusicBrainz.")
            return [], None
        results = musicbrainzngs.search_release_groups(
            query=query,
            limit=20  # Limit the number of results
        )
        if 'release-group-list' in results:
            album_results = []
            for rg in results['release-group-list']:
                try:
                    # Check if it is an album
                    if rg.get('primary-type') == 'Album':
                        album_results.append({
                            'artist': rg['artist-credit'][0]['artist']['name'],
                            'title': rg['title'],
                            'year': int(rg['first-release-date'][:4]) if 'first-release-date' in rg and rg[
                                'first-release-date'] else None,  # Extract year
                            'musicbrainz_id': rg['id']
                        })
                except Exception as e:
                    print(f"Error processing a MusicBrainz result: {e}")
                    continue
            return album_results, None
        else:
            return [], "No album found on MusicBrainz."
    except musicbrainzngs.NetworkError as e:
        if retry_count < max_retries:
            wait_time = (2 ** retry_count) + random.random()
            st.warning(
                f"Network error from MusicBrainz. Retrying in {wait_time:.2f} seconds (attempt {retry_count + 1}/{max_retries}).")
            time.sleep(wait_time)
            return search_musicbrainz_album(album_title, artist_name, retry_count + 1, max_retries)
        else:
            return [], "MusicBrainz network error after multiple retries."
    except Exception as e:
        return [], f"Error searching MusicBrainz: {e}"
def search_archive(search_term, media_type, start_year=None, start_month=None, start_day=None, end_year=None,
                   end_month=None, end_day=None):
    """
    Searches archive.org for audiobooks or ebooks, with optional date range filtering using year/month/day.
    Args:
        search_term (str): The term to search for.
        media_type (str): The media type for the search.
        start_year (int, optional): The start year for the search. Defaults to None.
        start_month (int, optional): The start month for the search. Defaults to None.
        start_day (int, optional): The start day for the search. Defaults to None.
        end_year (int, optional): The end year for the search. Defaults to None.
        end_month (int, optional): The end month for the search. Defaults to None.
        end_day (int, optional): The end day for the search. Defaults to None.
    Returns:
        list: A list of dictionaries, where each dictionary represents a search result.
              Returns an empty list if no results are found or an error occurs.
    """
    try:
        ia = internetarchive.ArchiveSession()
        query = f'({search_term}) AND mediatype:{media_type}'
        start_date = None
        end_date = None
        # Set the date range to the entire year if only the year is provided
        if start_year:
            try:
                start_date = date(start_year, 1, 1)
                end_date = date(start_year, 12, 31)
            except ValueError:
                st.error("Invalid year.")
                return []
        # Add date range filter if start and end dates are provided
        if start_date and end_date:
            query += f' AND date:[{start_date.strftime("%Y-%m-%d")} TO {end_date.strftime("%Y-%m-%d")}]'
        elif start_date:
            query += f' AND date>={start_date.strftime("%Y-%m-%d")}'
        elif end_date:
            query += f' AND date<={end_date.strftime("%Y-%m-%d")}'
        search_results = ia.search_items(
            query=query,
            fields=['identifier', 'title', 'creator', 'image']
        )
        results = []
        for item in search_results:
            results.append(item)
        results_list = [dict(result) for result in results]
        print(f"search_archive returning: {results_list}")
        return results_list
    except Exception as e:
        print(f"Error during search: {e}")
        return []
def get_item_files(identifier):
    """Retrieves the files associated with an item on archive.org."""
    try:
        item = internetarchive.get_item(identifier)
        files = list(item.files)
        file_list = [dict(file) for file in files]
        return file_list
    except Exception as e:
        print(f"Error retrieving item files: {e}")
        return []
def filter_results_by_file_types(results, file_types_str):
    """Filters search results to only include items that contain files of the specified types."""
    if not file_types_str:
        return results
    file_types = file_types_str.lower().split()
    filtered_results = []
    for result in results:
        identifier = result['identifier']
        files = get_item_files(identifier)
        if files:
            if any(file['name'].lower().endswith(f".{file_type}") for file in files for file_type in file_types):
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
def display_text_preview(result, files):
    """Displays a text preview section with a dropdown to select text-based files."""
    text_extensions = ['.txt', '.epub', '.html', '.htm', '.md']  # Add more as needed
    text_files = [file for file in files if any(file['name'].lower().endswith(ext) for ext in text_extensions)]
    if text_files:
        st.subheader("Text Preview")
        text_names = [file['name'] for file in text_files]
        # Session state key for the selected text file
        selected_text_key = f"selected_text_{result['identifier']}"
        # Initialize selected text file in session state if it doesn't exist
        if selected_text_key not in st.session_state:
            st.session_state[selected_text_key] = text_names[0] if text_names else None  # Select the first by default
        # Dropdown to select the text file
        selected_text_name = st.selectbox(
            "Select Text File:",
            options=text_names,
            key=f"text_select_{result['identifier']}",
            index=text_names.index(st.session_state[selected_text_key]) if st.session_state[
                                                                              selected_text_key] in text_names else 0,
            # Set index to currently selected text file
        )
        st.session_state[selected_text_key] = selected_text_name
        # Get the selected text file URL
        selected_text_url = f"https://archive.org/download/{result['identifier']}/{selected_text_name}" if selected_text_name else None
        if selected_text_url:
            try:
                response = requests.get(selected_text_url)
                response.raise_for_status()  # Raise HTTPError for bad responses
                text_content = response.text
                # Basic text display (you might want to add formatting for HTML/EPUB)
                st.markdown(f"<div style='height:400px; overflow-y:scroll; border: 1px solid #ccc; padding: 10px;'>{text_content}</div>", unsafe_allow_html=True)
            except requests.exceptions.RequestException as e:
                st.error(f"Error loading text file: {e}")
            except Exception as e:
                st.error(f"Error processing text file: {e}")
def display_pdf_preview(result, files):
    """Displays a PDF preview section with a dropdown to select PDF files."""
    pdf_files = [file for file in files if file['name'].lower().endswith('.pdf')]
    if pdf_files:
        st.subheader("PDF Preview")
        pdf_names = [file['name'] for file in pdf_files]
        # Session state key for the selected PDF
        selected_pdf_key = f"selected_pdf_{result['identifier']}"
        # Initialize selected PDF in session state if it doesn't exist
        if selected_pdf_key not in st.session_state:
            st.session_state[selected_pdf_key] = pdf_names[0] if pdf_names else None  # Select the first PDF by default
        # Dropdown to select the PDF
        selected_pdf_name = st.selectbox(
            "Select PDF File:",
            options=pdf_names,
            key=f"pdf_select_{result['identifier']}",
            index=pdf_names.index(st.session_state[selected_pdf_key]) if st.session_state[
                                                                              selected_pdf_key] in pdf_names else 0,
            # Set index to currently selected PDF
        )
        st.session_state[selected_pdf_key] = selected_pdf_name
        # Get the selected PDF URL
        selected_pdf_url = f"https://archive.org/download/{result['identifier']}/{selected_pdf_name}" if selected_pdf_name else None
        if selected_pdf_url:
            try:
                # Use an iframe to display the PDF
                st.markdown(
                    f'<iframe src="{selected_pdf_url}" style="width:100%;height:500px;"></iframe>',
                    unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error displaying PDF: {e}")
def display_result_details(result, media_type):
    """Displays the details of a selected result, including an audio player with queue and file selection."""
    st.subheader(result['title'])
    if 'creator' in result:
        st.write(f"**Creator:** {result['creator']}")
    st.write(f"**Identifier:** {result['identifier']}")
    item_url = f"https://archive.org/details/{result['identifier']}"
    st.markdown(f"[View on Archive.org]({item_url})")
    thumbnail_url = get_thumbnail_url(result['identifier'])
    # Use columns for the image and content section
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(
            f"""
            <div style="padding-right: 15px;">
            """,
            unsafe_allow_html=True
        )
        if thumbnail_url:
            st.image(thumbnail_url, caption=f"Image for {result['title']}", width=220)
        else:
            st.write("No image available.")
    with col2:
        with st.spinner(f"Retrieving files for '{result['title']}'..."):
            files = get_item_files(result['identifier'])
            if files:
                if media_type == "audio":
                    audio_files = [file for file in files if
                                   file['name'].lower().endswith(('.mp3', '.wav', '.flac', '.ogg'))]
                    if audio_files:
                        st.subheader("Audio Player")
                        audio_urls = [f"https://archive.org/download/{result['identifier']}/{file['name']}" for file
                                      in audio_files]
                        audio_names = [file['name'] for file in audio_files]
                        # Create a dictionary mapping track names to URLs
                        track_options = {name: url for name, url in zip(audio_names, audio_urls)}
                        # Session state key for the selected track
                        selected_track_key = f"selected_track_{result['identifier']}"
                        # Initialize selected track in session state if it doesn't exist
                        if selected_track_key not in st.session_state:
                            st.session_state[selected_track_key] = next(
                                iter(track_options)) if track_options else None  # Select the first track by default
                        # Dropdown to select the track
                        selected_track_name = st.selectbox(
                            "Select Track:",
                            options=list(track_options.keys()),
                            key=f"track_select_{result['identifier']}",
                            index=list(track_options.keys()).index(
                                st.session_state[selected_track_key]) if st.session_state[
                                                                             selected_track_key] in track_options else 0,
                            # on_change=lambda: st.session_state.update({selected_track_key: st.session_state[f"track_select_{result['identifier']}"]})
                        )
                        st.session_state[selected_track_key] = selected_track_name
                        # Get the selected audio URL
                        selected_audio_url = track_options[selected_track_name] if selected_track_name else None
                        if selected_audio_url:
                            try:
                                response = requests.head(selected_audio_url, allow_redirects=True)
                                response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
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
                                st.error(f"Error loading audio: {e}")
                elif media_type == "texts":
                    display_pdf_preview(result, files)
                    display_text_preview(result, files)
    # File section below the image and audio
    st.subheader("Files:")
    file_names = [file['name'] for file in files]
    selected_file = st.selectbox("Select a file to download:", file_names,
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
    """Retrieves the URL of the thumbnail image for a given item identifier."""
    try:
        return f"https://archive.org/services/img/{identifier}"
    except Exception as e:
        print(f"Error getting thumbnail URL: {e}")
        return None
def get_zip_download_url(identifier):
    """Constructs the zip download URL for an item from archive.org."""
    try:
        return f"https://archive.org/compress/{identifier}"
    except Exception as e:
        print(f"Error getting ZIP download URL for {identifier}: {e}")
        return None
def has_restricted_download(identifier):
    """
    Checks if an item has a restricted download by attempting to access the zip download URL.
    Returns True if the download is restricted (status code 403), False otherwise.
    """
    zip_url = get_zip_download_url(identifier)
    if zip_url:
        try:
            response = requests.head(zip_url, allow_redirects=True)
            response.raise_for_status()  # Raise HTTPError for bad responses
            if response.status_code == 403:  # Forbidden status code indicates restricted download
                return True
            else:
                return False
        except requests.exceptions.RequestException as e:
            print(f"Error checking download restriction for {identifier}: {e}")
            return True  # Assume restricted if there's an error during the check
    else:
        return True  # Assume restricted if zip URL cannot be constructed
# Streamlit UI
st.title("Archive.org Search")
# Album Search Section in an expander
with st.expander("Album Search", expanded=False):
    album_title = st.text_input("Enter Album Title:", key="album_title_input", value="")  # Initialize with empty string
    artist_name = st.text_input("Enter Artist Name:", key="artist_name_input", value="")  # Initialize with empty string
    album_search_button = st.button("Search Album (MusicBrainz)", key="album_search_button")
    # Initialize session state for musicbrainz_results and selected_album
    if 'musicbrainz_results' not in st.session_state:
        st.session_state.musicbrainz_results = []
    if 'selected_album' not in st.session_state:
        st.session_state.selected_album = None
    musicbrainz_results = []
    if album_search_button:
        with st.spinner(f"Searching MusicBrainz for '{album_title}' by '{artist_name}'..."):
            musicbrainz_results, musicbrainz_error = search_musicbrainz_album(album_title, artist_name)
            if musicbrainz_error:
                st.error(musicbrainz_error)
            st.session_state.musicbrainz_results = musicbrainz_results  # Store results in session state
    # Display MusicBrainz Results
    if st.session_state.get("musicbrainz_results"):
        st.subheader("MusicBrainz Results")
        album_options = [f"{result['artist']} - {result['title']} ({result['year']})" for result in
                         st.session_state.musicbrainz_results if result['year']]
        default_index = 0 if album_options else None  # Select first if available, else None
        selected_album_display = st.selectbox("Select an album:", album_options, key="musicbrainz_album_select",
                                               index=default_index, on_change=None)
        # Find the selected album
        if selected_album_display:  # Only update if a selection is made
            selected_album = next((result for result in st.session_state.musicbrainz_results
                                   if f"{result['artist']} - {result['title']} ({result['year']})" == selected_album_display),
                                  None)
            st.session_state.selected_album = selected_album  # Store selected album in session state
        else:
            st.session_state.selected_album = None
# Main Search Section
st.subheader("Archive.org Search")
# Search Term Input (Prefilled)
if st.session_state.get("selected_album"):
    search_term = f"{st.session_state.selected_album['artist']} {st.session_state.selected_album['title']}"
    st.write(f"Searching Archive.org for: '{search_term}'")  # Display search term
else:
    search_term = st.text_input("Enter Search Term:", key="search_term_input", value="")
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
# Date Range Filter (Simplified)
with st.expander("Date Range Filter", expanded=False):
    use_album_year = False
    start_year_str = st.text_input("Year (Optional):", key="start_year_input", value="")  # Text input for year
    if st.session_state.get("selected_album"):
        use_album_year = st.checkbox("Use Album Release Year", value=False)  # Unchecked by default
    if use_album_year and st.session_state.get("selected_album"):
        start_year = st.session_state.selected_album['year']
        st.write(f"Using album release year: {start_year}")
    else:
        start_year = None
        if start_year_str:
            try:
                start_year = int(start_year_str)
            except ValueError:
                st.error("Invalid year format. Please enter a number.")
                start_year = None
    # Disable month and day selection when using album release year
    start_month = None
    start_day = None
    end_year = None
    end_month = None
    end_day = None
# Search Button
search_button_pressed = st.button("Search Archive.org", key="search_button")
if search_term or search_button_pressed:
    if not search_term:
        st.warning("Please enter a search term.")
        st.session_state.results = None
    else:
        with st.spinner(f"Searching Archive.org for '{search_term}'..."):
            try:
                # Pass the start_year to search_archive
                results = search_archive(search_term, selected_media_type, start_year=start_year,
                                         start_month=start_month, start_day=start_day, end_year=end_year,
                                         end_month=end_month, end_day=end_day)
                # Filter out results with restricted downloads
                filtered_results = [result for result in results if not has_restricted_download(result['identifier'])]
                st.session_state.results = filtered_results
                # Handle single file type filtering
                if file_types_filter:
                    filtered_results = filter_results_by_file_types(filtered_results, file_types_filter)
                st.session_state.filtered_results = filtered_results
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.session_state.results = None
else:
    if 'results' not in st.session_state:
        st.session_state.results = None
# Display the popup panel if a result is selected
if st.session_state.get("selected_result_identifier"):
    selected_result = next((result for result in st.session_state.get("filtered_results", [])
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
    results_to_display = st.session_state.get("filtered_results", st.session_state.results)
    for i, result in enumerate(results_to_display):
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
                    else:
                        st.write("Download not available.")
                    st.caption(result['title'])
                except:
                    st.write(result['title'])
            else:
                st.write(result['title'])
            button_key = f"details_{i}"
            if st.button(f"Show Details", key=button_key):
                st.session_state.selected_result_identifier = result['identifier']
                st.rerun()  # Force a rerun here