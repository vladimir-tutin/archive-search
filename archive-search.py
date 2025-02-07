    # Display the thumbnail in the details section, limiting the width
    thumbnail_url = get_thumbnail_url(result['identifier'])
    if thumbnail_url:
        try:
            # Use HTML and CSS to limit the image width
            st.markdown(
                f"""
                <div style="max-width: 300px;">
                    <img src="{thumbnail_url}" style="width: 100%; object-fit: contain;">
                    <p style="text-align: center; font-size: smaller;">Image for {result['title']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
        except Exception as e:
            st.write(f"Error displaying image: {e}")
            st.write("No image available.")
    else:
        st.write("No image available.")
