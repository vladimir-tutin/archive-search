def display_result_details(result):
    """Displays the details of a selected result, including an audio player if applicable."""
    st.subheader(result['title'])
    if 'creator' in result:
        st.write(f"**Creator:** {result['creator']}")
    st.write(f"**Identifier:** {result['identifier']}")
    item_url = f"https://archive.org/details/{result['identifier']}"
    st.markdown(f"[View on Archive.org]({item_url})")

    # Display the thumbnail in the details section
    thumbnail_url = get_thumbnail_url(result['identifier'])
    if thumbnail_url:
        try:
            st.image(thumbnail_url, caption=f"Image for {result['title']}", use_column_width=True)
        except Exception as e:
            st.write(f"Error displaying image: {e}")
            st.write("No image available.")
    else:
        st.write("No image available.")

    # The rest of the function remains the same
