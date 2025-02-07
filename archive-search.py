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

# Add this CSS to your Streamlit app
st.markdown("""
    <style>
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 9999;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .modal-content {
            background: white;
            padding: 2rem;
            border-radius: 10px;
            max-width: 80%;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .modal-close {
            position: absolute;
            top: 10px;
            right: 10px;
            cursor: pointer;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

def get_thumbnail_url(identifier):
    """
    Retrieves the URL of the thumbnail image for a given item identifier.
    """
    try:
        return f"https://archive.org/services/img/{identifier}"
    except Exception as e:
        print(f"Error getting thumbnail URL: {e}")
        return None

# Modify the display_result_details function to return HTML
def get_result_details_html(result):
    """Returns HTML content for the modal"""
    html = f"""
    <div class="modal-content">
        <span class="modal-close" onclick="window.parent.document.querySelector('.modal-overlay').style.display = 'none'">&times;</span>
        <h3>{result['title']}</h3>
    """
    
    if 'creator' in result:
        html += f"<p><strong>Creator:</strong> {result['creator']}</p>"
    
    html += f"<p><strong>Identifier:</strong> {result['identifier']}</p>"
    
    item_url = f"https://archive.org/details/{result['identifier']}"
    html += f'<p><a href="{item_url}" target="_blank">View on Archive.org</a></p>'
    
    if 'image' in result:
        html += f'<img src="{result["image"]}" style="max-width: 100%; height: auto;">'
    
    # Add files and download section
    files = get_item_files(result['identifier'])
    if files:
        # Audio player
        audio_files = [file for file in files if file['name'].lower().endswith(('.mp3', '.wav', '.flac', '.ogg'))]
        if audio_files:
            html += "<h4>Audio Player</h4>"
            html += "<audio controls>"
            for file in audio_files:
                url = f"https://archive.org/download/{result['identifier']}/{file['name']}"
                html += f'<source src="{url}" type="audio/{file["name"].split(".")[-1]}">'
            html += "Your browser does not support the audio element.</audio>"
        
        # File download section
        html += "<h4>Files</h4>"
        html += "<div style='max-height: 200px; overflow-y: auto;'>"
        for file in files:
            url = f"https://archive.org/download/{result['identifier']}/{file['name']}"
            html += f'<p><a href="{url}" download>{file["name"]}</a></p>'
        html += "</div>"
    
    html += "</div>"
    return html

# Modify the results display section
if st.session_state.results:
    num_columns = 5
    cols = st.columns(num_columns)
    
    for i, result in enumerate(st.session_state.results):
        with cols[i % num_columns]:
            thumbnail_url = get_thumbnail_url(result['identifier'])
            if thumbnail_url:
                st.image(thumbnail_url, use_column_width=True)
            st.write(result['title'][:50] + "..." if len(result['title']) > 50 else result['title'])
            
            if st.button("Show Details", key=f"details_{result['identifier']}"):
                st.session_state.selected_result = result
                st.session_state.show_modal = True

# Show modal if triggered
if st.session_state.get('show_modal'):
    result = st.session_state.selected_result
    modal_html = f"""
    <div class="modal-overlay" onclick="event.stopPropagation(); this.style.display = 'none';">
        {get_result_details_html(result)}
    </div>
    <script>
        document.querySelector('.modal-overlay').addEventListener('click', function(e) {{
            if(e.target === this) {{
                this.style.display = 'none';
            }}
        }});
    </script>
    """
    st.components.v1.html(modal_html, height=600)
    
    # Reset modal state after rendering
    st.session_state.show_modal = False

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
                st.session_state.expander_key = f"expander_{result['identifier']}"  # Store expander key

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
            st.session_state.selected_result_identifier = None  # Clear the selection
