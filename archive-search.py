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
musicbrainzngs.set_useragent("ArchiveOrgSearch", "1.0", "your_email@example.com")  # Replace with your email

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
                    #Check if it is an album
                    if rg.get('primary-type') == 'Album':
                        album_results.append({
                            'artist': rg['artist-credit'][0]['artist']['name'],
                            'title': rg['title'],
                            'year': int(rg['first-release-date'][:4]) if 'first-release-date' in rg and rg['first-release-date'] else None,  # Extract year
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
            st.warning(f"Network error from MusicBrainz. Retrying in {wait_time:.2f} seconds (attempt {retry_count + 1}/{max_retries}).")
            time.sleep(wait_time)
            return search_musicbrainz_album(album_title, artist_name, retry_count + 1, max_retries)
        else:
            return [], "MusicBrainz network error after multiple retries."
    except Exception as e:
        return [], f"Error searching MusicBrainz: {e}"


def search_archive(search_term, media_type, start_year=None, start_month=None, start_day=None, end_year=None, end_month=None, end_day=None):
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


def display_result_details(result):
    """Displays the details of a selected result, including an audio player with queue and file selection."""
    st.subheader(result['title'])
    if 'creator' in result:
        st.write(f"**Creator:** {result['creator']}")
    st.write(f"**Identifier:** {result['identifier']}")
    item_url = f"https://archive.org/details/{result['identifier']}"
    st.markdown(f"[View on Archive.org]({item_url})")
    thumbnail_url = get_thumbnail_url(result['identifier'])
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(
            f"""
            <div style="padding-right: 15px;">
            """,
            unsafe_allow_html=True
        )
        if thumbnail_url:
            st.image(thumbnail_url, caption=f"Image for {result['title']}", width=300)
        else:
            st.write("No image available.")
    with col2:
        with st.spinner(f"Retrieving files for '{result['title']}'..."):
            files = get_item_files(result['identifier'])
            if files:
                audio_files = [file for file in files if file['name'].lower().endswith(('.mp3', '.wav', '.flac', '.ogg'))]
                if audio_files:
                    st.subheader("Audio Player")
                    audio_urls = [f"https://archive.org/download/{result['identifier']}/{file['name']}" for file in audio_files]
                    audio_names = [file['name'] for file in audio_files]

                    # Create a playlist using session state to manage selected track
                    if 'selected_track_index' not in st.session_state:
                        st.session_state.selected_track_index = 0

                    def play_track(index):
                        st.session_state.selected_track_index = index
                        st.rerun()  # Force a rerun to update the player

                    # Display track list with buttons to play each track
                    for i, name in enumerate(audio_names):
                        if st.button(f"Play: {name}", key=f"play_button_{result['identifier']}_{i}"):
                            play_track(i)

                    # Generate the audio player HTML with the selected track
                    selected_track_index = st.session_state.selected_track_index
                    selected_audio_url = audio_urls[selected_track_index]
                    playlist_html = f"""
                        <audio controls autoplay>
                            <source src="{selected_audio_url}" type="audio/{selected_audio_url.split(".")[-1]}">
                            Your browser does not support the audio element.
                        </audio>
                    """
                    st.components.v1.html(playlist_html, height=100)

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


# Streamlit UI
st.title("Archive.org Search")

# Album Search Section
st.subheader("Album Search")
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
    album_options = [f"{result['artist']} - {result['title']} ({result['year']})" for result in st.session_state.musicbrainz_results if result['year']]
    default_index = 0 if album_options else None  # Select first if available, else None
    selected_album_display = st.selectbox("Select an album:", album_options, key="musicbrainz_album_select", index=default_index, on_change=None)


    # Find the selected album
    if selected_album_display: #Only update if a selection is made
        selected_album = next((result for result in st.session_state.musicbrainz_results
                               if f"{result['artist']} - {result['title']} ({result['year']})" == selected_album_display), None)
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
    search_term = st.text_input("Enter Search Term:", key="search_term_input", on_change=None)

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

# File Type Filter
file_types_filter = st.text_input("Filter by File Types (space-separated, e.g., mp3 flac pdf):",
                                   key="file_types_input")

# Date Range Filter (Simplified)
with st.expander("Date Range Filter", expanded=False):
    use_album_year = False
    start_year = None  # Initialize start_year

    if st.session_state.get("selected_album"):
        use_album_year = st.checkbox("Use Album Release Year", value=True)  # Checked by default

    if use_album_year and st.session_state.get("selected_album"):
        start_year = st.session_state.selected_album['year']
        st.write(f"Using album release year: {start_year}")
    else:
        current_year = date.today().year
        year_options = list(range(1900, current_year + 1))
        start_year = st.selectbox("Year", year_options, index=len(year_options) - 1, key="start_year")

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
                results = search_archive(search_term, selected_media_type, start_year=start_year, start_month=start_month, start_day=start_day, end_year=end_year, end_month=end_month, end_day=end_day)
                filtered_results = filter_results_by_file_types(results, file_types_filter)
                st.session_state.results = filtered_results

                if filtered_results:
                    st.success(f"Found {len(filtered_results)} results:")
                else:
                    st.warning("No results found matching the specified file types.")
                    st.session_state.results = None
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.session_state.results = None
else:
    if 'results' not in st.session_state:
        st.session_state.results = None

# Display the popup panel if a result is selected
if st.session_state.get("selected_result_identifier"):
    selected_result = next((result for result in st.session_state.results if
                            result['identifier'] == st.session_state.selected_result_identifier), None)
    if selected_result:
        expander_key = st.session_state.get("expander_key", "default_expander")
        with st.expander("Result Details", expanded=True):
            display_result_details(selected_result)
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
                st.session_state.expander_key = f"expander_{result['identifier']}"
