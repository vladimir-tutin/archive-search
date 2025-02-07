import streamlit as st
import time
import internetarchive
import io
import requests
from PIL import Image
import base64
import re

def search_archive(search_term, media_type):
    """
    Searches archive.org for audiobooks or ebooks.
    Args:
        search_term (str): The term to search for.
        media_type (str): The media type to search for.
    Returns:
        list: A list of dictionaries, where each dictionary represents a search result.
              Returns an empty list if no results are found or an error occurs.
    """
    try:
        # Create an ArchiveSession object
        ia = internetarchive.ArchiveSession()
        search_results = ia.search_items(
            query=f'({search_term}) AND mediatype:{media_type}',
            fields=['identifier', 'title', 'creator', 'image']  # Specify fields to retrieve, including 'image'
        )
        results = []
        for item in search_results:
            results.append(item)
        # Convert results to a list of dictionaries for easier use
        results_list = []
        for result in results:
            results_list.append(dict(result))  # Convert to dict
        print(f"search_archive returning: {results_list}")
        return results_list
    except Exception as e:
        print(f"Error during search: {e}")
        return []

def get_item_files(identifier):
    """
    Retrieves the files associated with an item on archive.org.
    Args:
        identifier (str): The identifier of the item.
    Returns:
        list: A list of dictionaries, where each dictionary represents a file.
              Returns an empty list if no files are found or an error occurs.
    """
    try:
        item = internetarchive.get_item(identifier)
        files = list(item.files)
        file_list = []
        for file in files:
            file_list.append(dict(file))
        return file_list
    except Exception as e:
        print(f"Error retrieving item files: {e}")
        return []

def filter_results_by_file_types(results, file_types_str):
    """
    Filters search results to only include items that contain files of the specified types.
    Args:
        results (list): A list of dictionaries, where each dictionary represents a search result.
        file_types_str (str): A string containing space-separated file types (e.g., "mp3 flac pdf").
    Returns:
        list: A list of dictionaries, where each dictionary represents a filtered search result.
    """
    if not file_types_str:
        return results  # Return all results if no file types are specified
    file_types = file_types_str.lower().split()
    filtered_results = []
    for result in results:
        identifier = result['identifier']
        files = get_item_files(identifier)
        if files:
            for file in files:
                file_name = file['name'].lower()
                for file_type in file_types:
                    if file_name.endswith(f".{file_type}"):
                        filtered_results.append(result)
                        break  # Only need one matching file to include the result
                else:
                    continue
                break  # Move to the next result if a match was found
    return filtered_results

def download_file(url, filename):
    """Downloads a file from the given URL and returns it as bytes."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
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
    if 'image' in result:
        image_url = result['image']
        st.image(image_url, caption=f"Image for {result['title']}", use_container_width=True)  # Changed here
    else:
        st.write("No image available.")

    # Retrieve files for the selected item
    with st.spinner(f"Retrieving files for '{result['title']}'..."):
        files = get_item_files(result['identifier'])
        if files:
            audio_files = [file for file in files if file['name'].lower().endswith(('.mp3', '.wav', '.flac', '.ogg'))]

            if audio_files:
                st.subheader("Audio Player")
                audio_urls = [f"https://archive.org/download/{result['identifier']}/{file['name']}" for file in audio_files]

                # Create a playlist using the audio URLs
                playlist_html = f"""
                    <audio controls autoplay>
                        {''.join([f'<source src="{url}" type="audio/{url.split(".")[-1]}">' for url in audio_urls])}
                        Your browser does not support the audio element.
                    </audio>
                """
                st.components.v1.html(playlist_html, height=100)  # Adjust height as needed

            st.subheader("Files:")
            file_names = [file['name'] for file in files]
            selected_file = st.selectbox("Select a file to download:", file_names,
                                          key=f"file_select_{result['identifier']}")  # Unique key!
            if selected_file:
                selected_file_data = next((file for file in files if file['name'] == selected_file), None)
                download_url = f"https://archive.org/download/{result['identifier']}/{selected_file_data['name']}"
                # Immediately trigger download
                with st.spinner(f"Downloading '{selected_file}'..."):
                    file_bytes = download_file(download_url, selected_file)
                    if file_bytes:
                        st.download_button(
                            label=f"Download '{selected_file}'",
                            data=file_bytes,
                            file_name=selected_file,
                            mime="application/octet-stream",  # Generic binary file type
                            key=f"download_button_{result['identifier']}_{selected_file}",
                            # Use a unique key
                        )
        else:
            st.warning("No files found for this item.")

def get_thumbnail_url(identifier):
    """
    Retrieves the URL of the thumbnail image for a given item identifier.
    """
    try:
        return f"https://archive.org/services/img/{identifier}"
    except Exception as e:
        print(f"Error getting thumbnail URL: {e}")
        return None

def get_zip_download_url(identifier):
    """
    Constructs the correct zip download URL for an item from archive.org.
    This requires getting the correct server subdomain from the item's metadata.
    """
    try:
        return f"https://archive.org/compress/{identifier}"
    except Exception as e:
        print(f"Error getting ZIP download URL for {identifier}: {e}")
        return None


# Streamlit UI
st.title("Archive.org Search")

# Search Term Input - Trigger search on Enter
search_term = st.text_input("Enter Search Term:", key="search_term_input", on_change=None)  # Removed on_change
if "search_triggered" not in st.session_state:
    st.session_state.search_triggered = False

# Use radio buttons for media type
media_type = st.radio(
    "Select Media Type:",
    ["audio", "texts", "collections", "movies"],
    key="media_type_radio",
    horizontal=True
)

# Map radio button selection to Archive.org media type values
media_type_mapping = {
    "audio": "audio",
    "texts": "texts",
    "collections": "collection",  # Corrected value for collections
    "movies": "movies"  # Corrected value for video
}
selected_media_type = media_type_mapping[media_type]

file_types_filter = st.text_input("Filter by File Types (space-separated, e.g., mp3 flac pdf):",
                                   key="file_types_input")  # Added file types filter

search_button_pressed = st.button("Search", key="search_button")

if search_term or search_button_pressed:
    if not search_term:
        st.warning("Please enter a search term.")
        st.session_state.results = None
    else:
        with st.spinner(f"Searching Archive.org for '{search_term}'..."):
            try:
                results = search_archive(search_term, selected_media_type)
                # Apply file type filtering
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

# Display results in a grid
if st.session_state.results:
    num_columns = 5
    cols = st.columns(num_columns)
    selected_result_identifier = st.session_state.get("selected_result_identifier",
                                                       None)  # Store identifier instead of the whole result.

    # Define a fixed height for the image containers
    image_height = 200  # Adjust this value as needed

    for i, result in enumerate(st.session_state.results):
        with cols[i % num_columns]:
            # Display image if available, otherwise display title
            thumbnail_url = get_thumbnail_url(result['identifier'])
            if thumbnail_url:
                try:
                    response = requests.get(thumbnail_url)
                    response.raise_for_status()
                    image = Image.open(io.BytesIO(response.content))

                    zip_download_url = get_zip_download_url(result['identifier'])
                    # Create a download button URL
                    # Use HTML/CSS for overlapping button
                    if zip_download_url:
                        st.markdown(
                            f"""
                            <div style="position: relative;">
                                <div style="height:{image_height}px; overflow: hidden;">
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
                    st.caption(result['title'])  # Display title below the image
                except:
                    st.write(result['title'])
            else:
                st.write(result['title'])

            # Add a button to trigger the popup panel
            button_key = f"details_{i}"
            if st.button(f"Show Details", key=button_key):
                st.session_state.selected_result_identifier = result['identifier']  # Store the identifier
                st.rerun() # Rerun to show the popup

    # Popup Panel Logic
    if st.session_state.get("selected_result_identifier"):
        selected_result = next((result for result in st.session_state.results if
                                result['identifier'] == st.session_state.selected_result_identifier), None)

        if selected_result:
            # CSS for the overlay and popup
            st.markdown(
                """
                <style>
                .overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0, 0, 0, 0.5); /* Semi-transparent black */
                    z-index: 9998; /* Ensure it's above other content */
                }
                .popup {
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background-color: white;
                    padding: 20px;
                    border-radius: 5px;
                    z-index: 9999; /* Ensure it's above the overlay */
                    width: 80%; /* Adjust as needed */
                    max-height: 80%; /* Adjust as needed */
                    overflow: auto; /* Enable scrolling if content overflows */
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            # Create the overlay
            st.markdown('<div class="overlay"></div>', unsafe_allow_html=True)

            # Create the popup content
            with st.container():  # Use a container to group elements
                st.markdown('<div class="popup">', unsafe_allow_html=True)
                with st.container(): # Container for the details and close button
                    display_result_details(selected_result)  # Display the result details

                    # Close button
                    if st.button("Close", key="close_button"): # Unique key for the close button
                        st.session_state.selected_result_identifier = None  # Clear the selection
                        st.rerun()  # Force a rerun to remove the popup
                st.markdown('</div>', unsafe_allow_html=True) # close the popup div

            # Add JavaScript to close the popup on outside click
            st.components.v1.html(
                """
                <script>
                const overlay = document.querySelector('.overlay');
                if (overlay) {
                    overlay.addEventListener('click', function(event) {
                        if (event.target === overlay) {
                            // Manually trigger a Streamlit update
                            // This might not be the most elegant solution, but it works
                            // by setting the selected_result_identifier to None in JavaScript
                            // and then forcing a re-render
                            Streamlit.setComponentValue(null);
                        }
                    });
                }
                </script>
                """,
                height=0,
            )

            # Handle the JavaScript callback
            component_value = st.session_state.get("component_value", None)
            if component_value is None and st.session_state.selected_result_identifier:
                st.session_state.selected_result_identifier = None
                st.rerun()
        else:
            st.error("Selected result not found.")
            st.session_state.selected_result_identifier = None  # Clear the selection
