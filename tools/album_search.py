# tools/album_search.py
import streamlit as st
import musicbrainzngs
import logging

logger = logging.getLogger(__name__)

DEFAULT_SELECT_OPTION = "Select an option"
MUSICBRAINZ_LIMIT = 20

def search_musicbrainz_album(album_title=None, artist_name=None, retry_with_backoff=None):
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
                    try:
                        album_results.append({
                            'artist': rg['artist-credit'][0]['artist']['name'],
                            'title': rg['title'],
                            'year': int(rg['first-release-date'][:4]) if 'first-release-date' in rg else None,
                            'musicbrainz_id': rg['id']
                        })
                    except Exception as e:
                        logger.error(f"Error processing MusicBrainz result: {e}")  # Log the error
                return album_results
            else:
                st.warning("No albums found on MusicBrainz.")
                return []
        except musicbrainzngs.NetworkError as e:
            raise e  # Re-raise to be caught by retry_with_backoff
        except Exception as e:
            st.error(f"Error searching MusicBrainz: {e}")
            return []
    return retry_with_backoff(_search, args=()) if retry_with_backoff else _search()  # Use retry_with_backoff

def album_search_tool(retry_with_backoff):
    """Streamlit UI for Album Search (MusicBrainz)."""
    with st.expander("Album Search (MusicBrainz)", expanded=False):
        album_title = st.text_input("Enter Album Title:", key="album_title_input", value="")
        artist_name = st.text_input("Enter Artist Name:", key="artist_name_input", value="")
        if st.button("Search Album (MusicBrainz)", key="album_search_button"):
            with st.spinner(f"Searching MusicBrainz for '{album_title}' by '{artist_name}'..."):
                st.session_state.musicbrainz_results = search_musicbrainz_album(album_title, artist_name, retry_with_backoff)
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