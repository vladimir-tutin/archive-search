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
<style>
/* flatpickr.min.css (Inline) */
.flatpickr-calendar {{
    background: #fff;
    border-radius: 5px;
    box-shadow: 0 3px 10px rgba(0,0,0,0.15);
    overflow: hidden;
    opacity: 0;
    position: absolute;
    text-align: center;
    visibility: hidden;
    z-index: 10;
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    -ms-touch-action: manipulation;
    touch-action: manipulation;
    padding: 10px; /* Add padding for better spacing */
}}
.flatpickr-calendar.open,
.flatpickr-calendar.inline {{
    opacity: 1;
    visibility: visible
}}
.flatpickr-calendar.open {{
    display: inline-block;
    z-index: 10
}}
.flatpickr-calendar.animate {{
    opacity: 0;
    -webkit-animation: fpFadeInDown 300ms cubic-bezier(0.23, 1, 0.32, 1);
    animation: fpFadeInDown 300ms cubic-bezier(0.23, 1, 0.32, 1)
}}
.flatpickr-calendar.hasTime .flatpickr-time {{
    border-top: 1px solid rgba(0,0,0,0.05);
    height: 47px
}}
.flatpickr-calendar.noCalendar .flatpickr-time {{
    height: auto
}}
.flatpickr-calendar:before,
.flatpickr-calendar:after {{
    position: absolute;
    display: block;
    pointer-events: none;
    border: solid transparent;
    content: '';
    height: 0;
    width: 0;
    left: 22px
}}
.flatpickr-calendar.rightMost:before,
.flatpickr-calendar.rightMost:after {{
    left: auto;
    right: 22px
}}
.flatpickr-calendar:before {{
    border-width: 5px;
    margin: 0 -5px
}}
.flatpickr-calendar:after {{
    border-width: 4px;
    margin: 0 -4px
}}
.flatpickr-calendar.arrowTop:before {{
    bottom: auto;
    top: 0;
    border-bottom-color: rgba(0,0,0,0.05)
}}
.flatpickr-calendar.arrowTop:after {{
    bottom: auto;
    top: 0;
    border-bottom-color: #fff
}}
.flatpickr-calendar.arrowBottom:before {{
    top: auto;
    bottom: 0;
    border-top-color: rgba(0,0,0,0.05)
}}
.flatpickr-calendar.arrowBottom:after {{
    top: auto;
    bottom: 0;
    border-top-color: #fff
}}
@-webkit-keyframes fpFadeInDown {{
    from {{
        opacity: 0;
        -webkit-transform: translate3d(0, -20px, 0);
        transform: translate3d(0, -20px, 0)
    }}
    to {{
        opacity: 1;
        -webkit-transform: translate3d(0, 0, 0);
        transform: translate3d(0, 0, 0)
    }}
}}
@keyframes fpFadeInDown {{
    from {{
        opacity: 0;
        -webkit-transform: translate3d(0, -20px, 0);
        transform: translate3d(0, -20px, 0)
    }}
    to {{
        opacity: 1;
        -webkit-transform: translate3d(0, 0, 0);
        transform: translate3d(0, 0, 0)
    }}
}}
.flatpickr-innerContainer {{
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    overflow: hidden
}}
.flatpickr-rContainer {{
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -webkit-box-orient: vertical;
    -webkit-box-direction: normal;
    -ms-flex-direction: column;
    flex-direction: column;
    -webkit-box-pack: justify;
    -ms-flex-pack: justify;
    justify-content: space-between;
    padding: 0 10px
}}
.flatpickr-month {{
    border: 1px solid rgba(0,0,0,0.05);
    border-radius: 5px;
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -webkit-box-pack: justify;
    -ms-flex-pack: justify;
    justify-content: space-between;
    margin-bottom: 10px;
    padding: 5px;
    position: relative
}}
.flatpickr-prev-month,
.flatpickr-next-month {{
    text-decoration: none;
    color: #333;
    cursor: pointer;
    display: inline-block;
    padding: 5px;
    position: relative;
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    height: 34px;
    width: 34px;
    border: 1px solid rgba(0,0,0,0.05);
    border-radius: 50%;
    background: transparent;
    -webkit-transition: background 0.1s;
    transition: background 0.1s;
    fill: #333;
    opacity: 0.5
}}
.flatpickr-prev-month:hover,
.flatpickr-next-month:hover {{
    background: rgba(0,0,0,0.05)
}}
.flatpickr-prev-month:hover svg,
.flatpickr-next-month:hover svg {{
    fill: #f64747
}}
.flatpickr-prev-month.flatpickr-disabled,
.flatpickr-next-month.flatpickr-disabled {{
    cursor: default;
    opacity: 0
}}
.flatpickr-prev-month.flatpickr-disabled svg,
.flatpickr-next-month.flatpickr-disabled svg {{
    fill: rgba(0,0,0,0.1)
}}
.flatpickr-prev-month svg,
.flatpickr-next-month svg {{
    position: absolute;
    top: 9px;
    left: 11px;
    width: 14px;
    height: 16px
}}
.flatpickr-current-month {{
    font-size: 135%;
    font-weight: 700;
    color: inherit;
    position: absolute;
    width: 75%;
    left: 12.5%;
    padding: 0
}}
.flatpickr-current-month .flatpickr-numInputWrapper {{
    display: inline-block;
    width: 66px;
    height: 30px
}}
.flatpickr-current-month .flatpickr-monthDropdown-months {{
    appearance: none;
    background: transparent;
    border: none;
    border-radius: 0;
    color: inherit;
    cursor: pointer;
    font-size: inherit;
    font-family: inherit;
    font-weight: 700;
    height: auto;
    line-height: inherit;
    margin: -1px 0 0;
    outline: none;
    padding: 0 0 0 0.5em;
    position: relative;
    vertical-align: initial;
    width: auto
}}
.flatpickr-current-month .flatpickr-monthDropdown-months:focus,
.flatpickr-current-month .flatpickr-monthDropdown-months:active {{
    outline: none
}}
.flatpickr-current-month .flatpickr-monthDropdown-months:hover {{
    color: #f64747
}}
.flatpickr-current-month .numInputCur,
.flatpickr-current-month .numInputMax {{
    display: none
}}
.flatpickr-current-month input.flatpickr-numInput,
.flatpickr-current-month input.flatpickr-numInput:hover {{
    border: none;
    font-size: inherit;
    font-family: inherit;
    font-weight: 700;
    position: relative;
    vertical-align: initial
}}
.flatpickr-current-month input.flatpickr-numInput:focus,
.flatpickr-current-month input.flatpickr-numInput:active {{
    outline: none
}}
.flatpickr-weekdays {{
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -webkit-box-align: center;
    -ms-flex-align: center;
    align-items: center;
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    padding: 0 10px
}}
span.flatpickr-weekday {{
    cursor: default;
    font-size: 90%;
    font-weight: 700;
    line-height: 1;
    margin: 0;
    text-align: center;
    color: rgba(0,0,0,0.5);
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -webkit-box-align: center;
    -ms-flex-align: center;
    align-items: center;
    -webkit-box-pack: center;
    -ms-flex-pack: center;
    justify-content: center;
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    width: 14.2857143%;
    height: 34px
}}
.dayContainer,
.flatpickr-weeks {{
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    padding: 0 10px
}}
.flatpickr-days {{
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -ms-flex-wrap: wrap;
    flex-wrap: wrap;
    width: 308px;
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    padding: 0;
    cursor: pointer;
    border-spacing: 0;
    border-collapse: collapse
}}
.flatpickr-days:focus {{
    outline: none
}}
.flatpickr-day,
.flatpickr-weekday {{
    max-width: 39px;
    text-align: center;
    font-weight: 400;
    position: relative;
    color: inherit;
    border: 1px solid transparent;
    border-radius: 5px;
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -webkit-box-align: center;
    -ms-flex-align: center;
    align-items: center;
    -webkit-box-pack: center;
    -ms-flex-pack: center;
    justify-content: center;
    -webkit-box-sizing: border-box;
    box-sizing: border-box;
    width: 14.2857143%;
    height: 34px;
    -ms-flex-preferred-size: 14.2857143%;
    flex-basis: 14.2857143%;
    padding: 0
}}
.flatpickr-day.inRange,
.flatpickr-day.prevMonthDay.inRange,
.flatpickr-day.nextMonthDay.inRange,
.flatpickr-day.today.inRange,
.flatpickr-day.flatpickr-disabled,
.flatpickr-day.flatpickr-disabled:hover,
.flatpickr-day.prevMonthDay.flatpickr-disabled,
.flatpickr-day.nextMonthDay.flatpickr-disabled,
.flatpickr-day.prevMonthDay.flatpickr-disabled:hover,
.flatpickr-day.nextMonthDay.flatpickr-disabled:hover {{
    cursor: default;
    background: rgba(0,0,0,0.05);
    border-color: transparent;
    color: rgba(0,0,0,0.3)
}}
.flatpickr-day.today:not(.flatpickr-selected),
.flatpickr-day.today:not(.flatpickr-selected):hover {{
    color: #f64747
}}
.flatpickr-day.selected,
.flatpickr-day.startRange,
.flatpickr-day.endRange,
.flatpickr-day.selected.inRange,
.flatpickr-day.startRange.inRange,
.flatpickr-day.endRange.inRange,
.flatpickr-day.selected:focus,
.flatpickr-day.startRange:focus,
.flatpickr-day.endRange:focus,
.flatpickr-day.selected:hover,
.flatpickr-day.startRange:hover,
.flatpickr-day.endRange:hover,
.flatpickr-day.selected.prevMonthDay,
.flatpickr-day.startRange.prevMonthDay,
.flatpickr-day.endRange.prevMonthDay,
.flatpickr-day.selected.nextMonthDay,
.flatpickr-day.startRange.nextMonthDay,
.flatpickr-day.endRange.nextMonthDay {{
    background: #f64747;
    -webkit-box-shadow: none;
    box-shadow: none;
    color: #fff !important; /* Use !important to override Streamlit styles */
    border-color: #f64747
}}
.flatpickr-day.selected.startRange,
.flatpickr-day.startRange.startRange,
.flatpickr-day.endRange.startRange {{
    border-radius: 50px 0 0 50px
}}
.flatpickr-day.selected.endRange,
.flatpickr-day.startRange.endRange,
.flatpickr-day.endRange.endRange {{
    border-radius: 0 50px 50px 0
}}
.flatpickr-day.selected:not(.flatpickr-disabled),
.flatpickr-day.startRange:not(.flatpickr-disabled),
.flatpickr-day.endRange:not(.flatpickr-disabled),
.flatpickr-day.selected:not(.flatpickr-disabled):hover,
.flatpickr-day.startRange:not(.flatpickr-disabled):hover,
.flatpickr-day.endRange:not(.flatpickr-disabled):hover {{
    background: #f64747;
    color: #fff
}}
.flatpickr-day:hover,
.flatpickr-day:focus {{
    background: rgba(0,0,0,0.05);
    border-color: transparent
}}
.flatpickr-day.nextMonthDay,
.flatpickr-day.prevMonthDay {{
    color: rgba(0,0,0,0.3);
    fill: rgba(0,0,0,0.3)
}}
.flatpickr-day.nextMonthDay:hover,
.flatpickr-day.prevMonthDay:hover {{
    background: rgba(0,0,0,0.05)
}}
.flatpickr-day.flatpickr-selected,
.flatpickr-day.flatpickr-selected:hover {{
    background: #f64747;
    color: #fff
}}
.flatpickr-time {{
    text-align: center;
    outline: none;
    display: -webkit-box;
    display: -ms-flexbox;
    display: flex;
    -webkit-box-align: center;
    -ms-flex-align: center;
    align-items: center;
    height: 0
}}
.flatpickr-time:after {{
    display: block;
    position: absolute;
    content: '';
    height: 1px;
    background: rgba(0,0,0,0.05);
    width: 100%;
    left: 0
}}
.flatpickr-time .flatpickr-time-separator,
.flatpickr-time .flatpickr-time-am-pm {{
    height: auto;
    display: inline-block;
    float: none;
    margin: 0;
    position: static;
    width: auto;
    border: 0;
    padding: 0 5px
}}
.flatpickr-time .flatpickr-time-am-pm {{
    outline: none;
    cursor: pointer;
    color: inherit;
    font-weight: 700;
    line-height: 1
}}
.flatpickr-time input.flatpickr-numInput {{
    width: 50px;
    border: none;
    border-radius: 0;
    text-align: center;
    font-weight: 700;
    font-size: inherit;
    color: inherit;
    display: inline-block
}}
.flatpickr-time input.flatpickr-numInput:focus,
.flatpickr-time input.flatpickr-numInput:active {{
    outline: none
}}
.flatpickr-time .flatpickr-time-components {{
    -webkit-box-flex: 1;
    -ms-flex: 1;
    flex: 1;
    border: 0;
    border-radius: 0;
    padding: 0;
    background: transparent !important
}}
.flatpickr-input[readonly] {{
    cursor: pointer
}}
</style>
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
