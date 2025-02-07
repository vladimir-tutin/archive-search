import streamlit as st
import time
import internetarchive
import io
import requests
from PIL import Image
import webbrowser
from bs4 import BeautifulSoup
import musicbrainzngs
from datetime import date
import random

# Constants
USER_AGENT = "ArchiveOrgSearch/1.0 (your_email@example.com)"  # Replace with your email
MUSICBRAINZ_LIMIT = 20
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


def retry_with_backoff(func, *args, retry_count=0, max_retries=MAX_RETRIES, **kwargs):
    """Retries a function with exponential backoff."""
    try:
        return func(*args, **kwargs)
    except Exception as e:  # Catch a broader exception for retry logic
        if retry_count < max_retries:
            wait_time = (2 ** retry_count) + random.random()
            st.warning(
                f"Error: {e}. Retrying in {wait_time:.2f} seconds (attempt {retry_count + 1}/{max_retries}).")
            time.sleep(wait_time)
            return retry_with_backoff(func, *args, retry_count=retry_count + 1, max_retries=max_retries,
                                      **kwargs)
        else:
            st.error(f"Failed after multiple retries: {e}")
            return None  # Or raise the exception, depending on your needs


def search_musicbrainz_album(album_title=None, artist_name=None):
    """Searches MusicBrainz for albums (release groups) with retry logic."""
    if not album_title and not artist_name:
        st.warning("Please enter either an album title or artist name to search MusicBrainz.")
        return []

    query = f'artist:"{artist_name}" AND release:"{album_title}"' if artist_name and album_title else \
        f'artist:"{artist_name}"' if artist_name else f'release:"{album_title}"'

    def _search():
        try:
            results = musicbrainzngs.search_release_groups(query=query, limit=MUSICBRAINZ_LIMIT)
            if 'release-group-list' in results:
                album_results = []
                for rg in results['release-group-list']:
                    if rg.get('primary-type') == 'Album':
                        try:
                            album_results.append({
                                'artist': rg['artist-credit'][0]['artist']['name'],
                                'title': rg['title'],
                                'year': int(rg['first-release-date'][:4]) if 'first-release-date' in rg else None,
                                'musicbrainz_id': rg['id']
                            })
                        except Exception as e:
                            print(f"Error processing MusicBrainz result: {e}")  # Log the error
                return album_results
            else:
                st.warning("No albums found on MusicBrainz.")
                return []
        except musicbrainzngs.NetworkError as e:
            raise e  # Re-raise to be caught by retry_with_backoff
        except Exception as e:
            st.error(f"Error searching MusicBrainz: {e}")
            return []

    return retry_with_backoff(_search) or []  # Use retry_with_backoff


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


def display_text_preview(result, files):
    """Displays a text preview section with a dropdown to select text-based files."""
    text_files = [file for file in files if file['name'].lower().endswith(tuple(TEXT_EXTENSIONS))]
    if text_files:
        st.subheader("Text Preview")
        selected_text_name = st.selectbox(
            "Select Text File:",
            options=[file['name'] for file in text_files],
            key=f"text_select_{result['identifier']}",
        )
        if selected_text_name:
            selected_text_url = f"https://archive.org/download/{result['identifier']}/{selected_text_name}"
            try:
                response = requests.get(selected_text_url)
                response.raise_for_status()
                text_content = response.text
                st.markdown(
                    f"<div style='height:400px; overflow-y:scroll; border: 1px solid #ccc; padding: 10px;'>{text_content}</div>",
                    unsafe_allow_html=True)
            except requests.exceptions.RequestException as e:
                handle_request_error(e, "Error loading text file")
            except Exception as e:
                st.error(f"Error processing text file: {e}")


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
                    f'<iframe src="{selected_pdf_url}" style="width:100%;height:500px;"></iframe>',
                    unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Error displaying PDF: {e}")


def display_result_details(result, media_type):
    """Displays details of a selected result, including audio player and file selection."""
    st.subheader(result['title'])
    if 'creator' in result:
        st.write(f"**Creator:** {result['creator']}")
    st.write(f"**Identifier:** {result['identifier']}")
    item_url = f"https://archive.org/details/{result['identifier']}"
    st.markdown(f"[View on Archive.org]({item_url})")

    thumbnail_url = get_thumbnail_url(result['identifier'])

    col1, col2 = st.columns([1, 2])
    with col1:
        if thumbnail_url:
            st.image(thumbnail_url, caption=f"Image for {result['title']}", width=220)
        else:
            st.write("No image available.")

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
                display_text_preview(result, files)

    # File section below the image and audio
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


def scrape_audible(audiobook_title):
    """Scrapes Audible search results for audiobook information."""
    search_url = f"https://www.audible.com/search?keywords={audiobook_title}"
    try:
        response = requests.get(search_url, headers={'User-Agent': USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        results = []
        for item in soup.find_all('div', class_='bc-row-responsive'):
            try:
                title_element = item.find('h3', class_='bc-heading').find('a', class_='bc-link')
                title = title_element.text.strip() if title_element else "Title Not Found"
                author_element = item.find('li', class_='authorLabel').find('a', class_='bc-link')
                author = author_element.text.strip() if author_element else "Author Not Found"
                narrators = [narrator_element.text.strip() for narrator_element in
                             item.find('li', class_='narratorLabel').find_all('a', class_='bc-link')]
                narrators = narrators if narrators else ["Narrator Not Found"]
                release_date_element = item.find('li', class_='releaseDateLabel').find('span', class_='bc-text')
                release_date = release_date_element.text.replace("Release date:", "").strip() if release_date_element else "Release Date Not Found"
                results.append({
                    'title': title,
                    'author': author,
                    'narrators': narrators,
                    'release_date': release_date
                })
            except Exception as e:
                print(f"Error extracting information from result item: {e}")
                continue

        time.sleep(1)  # Add a 1-second delay between requests
        return results
    except requests.exceptions.RequestException as e:
        handle_request_error(e, "Request error during Audible scraping")
        return []
    except Exception as e:
        st.error(f"Error during scraping: {e}")
        return []


# --- Streamlit UI ---
st.title("Archive.org Search")

# Initialize session state
if 'musicbrainz_results' not in st.session_state:
    st.session_state.musicbrainz_results = []
if 'selected_album' not in st.session_state:
    st.session_state.selected_album = None
if 'use_album_year' not in st.session_state:
    st.session_state.use_album_year = False
if 'selected_title_formatted' not in st.session_state:
    st.session_state.selected_title_formatted = DEFAULT_SELECT_OPTION
# Add scraped media type to session state
if 'scraped_media_type' not in st.session_state:
    st.session_state.scraped_media_type = "audio"

# Sidebar for Tools
with st.sidebar:
    st.header("Tools")

    with st.expander("Album Search (MusicBrainz)", expanded=False):
        album_title = st.text_input("Enter Album Title:", key="album_title_input", value="")
        artist_name = st.text_input("Enter Artist Name:", key="artist_name_input", value="")

        if st.button("Search Album (MusicBrainz)", key="album_search_button"):
            with st.spinner(f"Searching MusicBrainz for '{album_title}' by '{artist_name}'..."):
                st.session_state.musicbrainz_results = search_musicbrainz_album(album_title, artist_name)

        # Display MusicBrainz Results
        if st.session_state.musicbrainz_results:
            st.subheader("MusicBrainz Results")
            album_options = [f"{result['artist']} - {result['title']} ({result['year']})" for result in
                             st.session_state.musicbrainz_results if result['year']]
            album_options = [DEFAULT_SELECT_OPTION] + album_options  # add a blank option to the start
            selected_album_display = st.selectbox("Select an album:", album_options,
                                                   key="musicbrainz_album_select")

            if selected_album_display != DEFAULT_SELECT_OPTION:
                st.session_state.selected_album = next(
                    (result for result in st.session_state.musicbrainz_results
                     if f"{result['artist']} - {result['title']} ({result['year']})" == selected_album_display),
                    None)
                st.session_state.use_album_year = True  # Set use_album_year to True when an album is selected
            else:
                st.session_state.selected_album = None
                st.session_state.use_album_year = False  # Reset if no album is selected

    with st.expander("Audiobook Search (Web & Audible)", expanded=False):
        audiobook_title = st.text_input("Enter Audiobook Title:", key="audiobook_title_input", value="")

        if st.button("Search Audible", key="audiobook_audible_search_button"):
            with st.spinner(f"Scraping Audible for '{audiobook_title}'..."):
                audible_results = scrape_audible(audiobook_title)

                if audible_results:
                    st.subheader("Audible Results (Scraped):")
                    title_options = [
                        f"{result['title']} - {result['author']} - Narrated by: {', '.join(result['narrators'])} ({result['release_date']})"
                        for result in audible_results
                    ]
                    title_options = [DEFAULT_SELECT_OPTION] + title_options
                    selected_title_formatted = st.selectbox("Select an audiobook:", title_options,
                                                            key="audible_select")

                    if selected_title_formatted != DEFAULT_SELECT_OPTION:
                        st.session_state.selected_title_formatted = selected_title_formatted
                        selected_title = selected_title_formatted.split(" - ")[0]
                        selected_result = next(
                            (result for result in audible_results if result['title'] == selected_title), None)

                        if selected_result:
                            st.session_state.scraped_title = selected_result['title']
                            st.session_state.scraped_year = selected_result['release_date'].split('-')[-1]
                            st.session_state.scraped_media_type = "audio"
                            st.info(
                                f"Selected: '{selected_result['title']} - {selected_result['author']} - Narrated by: {', '.join(selected_result['narrators'])} ({st.session_state.scraped_year})'")
                    else:
                        st.session_state.scraped_title = None
                        st.session_state.scraped_year = None
                        st.session_state.scraped_media_type = "audio"
                        st.session_state.selected_title_formatted = DEFAULT_SELECT_OPTION

                else:
                    st.warning("No results found (or scraping failed).")

# Main Search Section
if st.session_state.get("selected_album"):
    search_term = f"{st.session_state.selected_album['artist']} {st.session_state.selected_album['title']}"
    st.write(f"Searching for: '{search_term}'")  # Display search term
elif 'scraped_title' in st.session_state and st.session_state.scraped_title is not None:
    search_term = st.session_state.scraped_title
    st.write(f"Searching for: '{search_term}'")
else:
    search_term = st.text_input("Enter Search Term:", key="search_term_input", value="")

# Media Type Selection
# Use the media type from session state if a scraped title is present, otherwise use the radio button
if 'scraped_title' in st.session_state and st.session_state.scraped_title is not None:
    selected_media_type = st.session_state.scraped_media_type
    st.write(f"Searching as media type: {selected_media_type}")  # Display the selected media type
else:
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
    elif 'scraped_year' in st.session_state and st.session_state.scraped_year is not None:
        start_year_str = st.session_state.scraped_year
        st.write(f"Using release year: {start_year_str}")

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

if st.session_state.get("selected_album") or (
        'scraped_title' in st.session_state and st.session_state.scraped_title is not None) or search_term:
    perform_search = True

if perform_search:
    if st.session_state.get("selected_album"):
        search_term_to_use = f"{st.session_state.selected_album['artist']} {st.session_state.selected_album['title']}"
    elif 'scraped_title' in st.session_state and st.session_state.scraped_title is not None:
        search_term_to_use = st.session_state.scraped_title
    else:
        search_term_to_use = search_term

    with st.spinner(f"Searching Archive.org for '{search_term_to_use}'..."):
        start_year_to_use = None

        if st.session_state.use_album_year and st.session_state.get("selected_album"):
            start_year_to_use = st.session_state.selected_album['year']
        elif 'scraped_year' in st.session_state and st.session_state.scraped_year is not None:
            try:
                start_year_to_use = int(st.session_state.scraped_year)
            except ValueError:
                st.error("Invalid year format. Please enter a number.")

        results = search_archive(search_term_to_use, selected_media_type, start_year=start_year_to_use)
        filtered_results = filter_results_by_file_types(results,
                                                          file_types_filter) if file_types_filter else results

        st.session_state.results = results
        st.session_state.filtered_results = filtered_results
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

