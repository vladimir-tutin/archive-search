import streamlit as st
import streamlit.components.v1 as components
from datetime import date
import time
import internetarchive
import io
import requests
from PIL import Image
import base64
import re

# Define the HTML/JavaScript component for the date range picker
date_range_picker_html = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
<script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
<script>
    function createDateRangePicker(element, startDate, endDate) {
        flatpickr(element, {
            mode: "range",
            dateFormat: "Y-m-d",
            defaultDate: [startDate, endDate],
            onClose: function(selectedDates, dateStr, instance) {
                // Notify Streamlit when the date range changes
                let event = new Event('dateRangeChange');
                event.dateRange = dateStr;
                window.dispatchEvent(event);
            }
        });
    }

    window.addEventListener('load', function() {
        // Initialize the date range picker with default dates
        let startDate = '%s'; // Placeholder for start date
        let endDate = '%s';   // Placeholder for end date
        createDateRangePicker(document.getElementById('dateRangePicker'), startDate, endDate);

        // Listen for changes from Streamlit
        window.addEventListener('streamlit:componentInit', function() {
            createDateRangePicker(document.getElementById('dateRangePicker'), startDate, endDate);
        });
    });
</script>
<div id="dateRangePicker"></div>
"""

def date_range_picker(start_date=None, end_date=None):
    """Embeds a date range picker component into Streamlit."""

    # Format dates as strings for the component
    start_date_str = start_date.strftime("%Y-%m-%d") if start_date else ""
    end_date_str = end_date.strftime("%Y-%m-%d") if end_date else ""

    # Inject the dates into the HTML
    html_code = date_range_picker_html % (start_date_str, end_date_str)

    # Embed the component
    components.html(html_code, height=100)

    # Listen for date range changes from the component
    date_range = st.session_state.get("date_range", None)  # Get the date range from session state
    if date_range:
        try:
            start_str, end_str = date_range.split(" to ")
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
            return start_date, end_date
        except ValueError:
            st.warning("Invalid date range format.")
            return None, None  # Or return the defaults

    return None, None  # Return None if no date range selected

def search_archive(search_term, media_type, start_date=None, end_date=None):
    """
    Searches archive.org for audiobooks or ebooks, with optional date range filtering.
    Args:
        search_term (str): The term to search for.
        media_type (str): The media type to search for.
        start_date (date, optional): The start date for the search. Defaults to None.
        end_date (date, optional): The end date for the search. Defaults to None.
    Returns:
        list: A list of dictionaries, where each dictionary represents a search result.
              Returns an empty list if no results are found or an error occurs.
    """
    try:
        ia = internetarchive.ArchiveSession()
        query = f'({search_term}) AND mediatype:{media_type}'

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
    """Displays the details of a selected result, including an audio player if applicable."""
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
                    playlist_html = f"""
                        <audio controls autoplay>
                            {''.join([f'<source src="{url}" type="audio/{url.split(".")[-1]}">' for url in audio_urls])}
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

# Default Dates
default_start_date = date(1900, 1, 1)  # Wider range
default_end_date = date.today()

# Date Range Picker
with st.expander("Date Range Filter", expanded=False):
    start_date, end_date = date_range_picker(default_start_date, default_end_date)

    # Store the selected date range in session state
    def handle_date_range_change():
        st.session_state["date_range"] = st.session_state.date_range_input  # Store the value from the text input
    st.text_input("Selected Date Range:", key="date_range_input", on_change=handle_date_range_change)

    # Listen for events from the date range picker
    js = f"""
    <script>
    window.addEventListener('dateRangeChange', function(e) {{
        const dateRange = e.dateRange;
        Streamlit.setComponentValue(dateRange); // Send the value to Streamlit
    }});
    </script>
    """
    components.html(js)

# Search Term Input
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

# Search Button
search_button_pressed = st.button("Search", key="search_button")

if search_term or search_button_pressed:
    if not search_term:
        st.warning("Please enter a search term.")
        st.session_state.results = None
    else:
        with st.spinner(f"Searching Archive.org for '{search_term}'..."):
            try:
                results = search_archive(search_term, selected_media_type, start_date, end_date)
                filtered_results = filter_results_by_file_types(results, file_types_filter)
                st.session_state.results = filtered_results

                if filtered_results:
                    st.success(f"Found {len(filtered_results)} results:")
                else:
                    st.warning("No results found matching the specified file types and date range.")
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
