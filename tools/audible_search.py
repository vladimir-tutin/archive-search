import streamlit as st
import requests
from bs4 import BeautifulSoup
import logging
import time

logger = logging.getLogger(__name__)
DEFAULT_SELECT_OPTION = "Select an option"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"


def scrape_audible(book_title=None, author_name=None):
    """Scrapes Audible search results for audiobook information, preventing duplicates."""
    search_url = f"https://www.audible.com/search?keywords={book_title}+{author_name}"
    try:
        response = requests.get(search_url, headers={'User-Agent': USER_AGENT})
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        results = []
        seen_titles = set()  # Keep track of titles we've already seen

        for item in soup.find_all('div', class_='bc-row-responsive'):
            try:
                title_element = item.find('h3', class_='bc-heading').find('a', class_='bc-link')
                title = title_element.text.strip() if title_element else "Title Not Found"

                # Check for duplicates *before* extracting other data
                if title in seen_titles:
                    continue  # Skip this item if the title is already in the set

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
                    'year': release_date
                })
                seen_titles.add(title)  # Add the title to the set of seen titles

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


def audible_search_tool(retry_with_backoff):
    """Streamlit UI for Book Search (Audible)."""
    with st.expander("Book Search (Audible)", expanded=False):
        book_title = st.text_input("Enter Book Title:", key="book_title_input", value="")
        author_name = st.text_input("Enter Author Name:", key="author_name_input", value="")

        if st.button("Search Book (Audible)", key="book_search_button"):
            with st.spinner(f"Searching Audible for '{book_title}' by '{author_name}'..."):
                st.session_state.audible_results = scrape_audible(book_title, author_name)

        # Display Audible Results
        if st.session_state.get("audible_results"):
            st.subheader("Audible Results")
            book_options = [f"{result['author']} - {result['title']} ({result['year']})" for result in
                             st.session_state.audible_results if result['year']]
            book_options = [DEFAULT_SELECT_OPTION] + book_options  # add a blank option to the start

            selected_book_display = st.selectbox("Select a book:", book_options,
                                                   key="audible_book_select")

            if selected_book_display != DEFAULT_SELECT_OPTION:
                st.session_state.selected_book = next(
                    (result for result in st.session_state.audible_results
                     if f"{result['author']} - {result['title']} ({result['year']})" == selected_book_display),
                    None)
                st.session_state.use_book_year = True  # Set use_book_year to True when a book is selected
            else:
                st.session_state.selected_book = None
                st.session_state.use_book_year = False  # Reset if no book is selected

            # Display full details using st.write
            if st.session_state.selected_book:
                st.write("### Selected Book Details")
                st.write(f"**Title:** {st.session_state.selected_book['title']}")
                st.write(f"**Author:** {st.session_state.selected_book['author']}")
                st.write(f"**Year:** {st.session_state.selected_book['year']}")
                st.write(f"**Narrators:** {', '.join(st.session_state.selected_book['narrators'])}")

def handle_request_error(e, message):
    """Handles request exceptions and logs the error."""
    logger.error(f"{message}: {e}")
    st.error(f"An error occurred: {message}. Please check the logs for details.")