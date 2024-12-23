import streamlit as st
import pandas as pd
from io import StringIO

uploaded_file = st.file_uploader("Choose a file")
if uploaded_file is not None:
    # Read the CSV file into a dataframe
    dataframe = pd.read_csv(uploaded_file)
    
    # Display the first 10 rows
    st.write("First 10 rows of the uploaded file:")
    st.write(dataframe.head(10))

    # Initialize session state for 'graph_data'
    if 'graph_data' not in st.session_state:
        st.session_state['graph_data'] = False

    # When the button is clicked, update session state
    if st.button("Graph Data"):
        st.session_state['graph_data'] = True

    # If 'graph_data' is True, display the chart options
    if st.session_state['graph_data']:
        option = st.selectbox(
            "Which type of chart would you like to display?",
            ("Area Chart", "Bar Chart", "Line Chart", "Scatter Chart"),
        )

        st.write("You selected:", option)

        # Get numerical columns only
        numeric_cols = dataframe.select_dtypes(include=['float64', 'int64']).columns

        # Unique key for each multiselect to avoid conflicts
        multiselect_key = f"{option.lower().replace(' ', '_')}_columns"

        selected_columns = st.multiselect(
            "Select columns to plot:",
            options=numeric_cols,
            default=numeric_cols[:3] if len(numeric_cols) > 0 else None,
            key=multiselect_key
        )

        if selected_columns:
            if option == "Area Chart":
                st.area_chart(data=dataframe[selected_columns])
            elif option == "Bar Chart":
                st.bar_chart(data=dataframe[selected_columns])
            elif option == "Line Chart":
                st.line_chart(data=dataframe[selected_columns])
            elif option == "Scatter Chart":
                st.scatter_chart(data=dataframe[selected_columns])
        else:
            st.warning("Please select at least one column to plot")



