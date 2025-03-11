import streamlit as st
import os
import logging
from agent import initialize_agent, query_agent
from local_vector_store import create_vector_store, add_documents_to_store, search_documents
from langchain_community.document_loaders import PDFPlumberLoader
import tempfile
from auth import login_page, logout, get_user_info  # Import the login and logout functions
from dynamodb import (
    create_dynamodb_table,
    get_chat_history,
    add_user_message,
    add_ai_message,
    clear_chat_history,
)  # DynamoDB functions
from packs import get_current_packs, query_pinecone_pack  # Import the get_current_packs function
import json
import pandas as pd
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.utilities.tavily_search import TavilySearchAPIWrapper
from PIL import Image
import requests
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === Set AWS Credentials as Environment Variables ===
os.environ["AWS_ACCESS_KEY_ID"] = st.secrets["default"]["ACCESS_KEY"]
os.environ["AWS_SECRET_ACCESS_KEY"] = st.secrets["default"]["SECRET_KEY"]
os.environ["AWS_DEFAULT_REGION"] = st.secrets["default"]["REGION"]

# Initialize session state variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "logout_trigger" not in st.session_state:
    st.session_state.logout_trigger = False

if "show_login_page" not in st.session_state:
    st.session_state.show_login_page = False

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Helper Functions ---
def handle_clear_chat_history():
    """Callback function for the clear chat history button."""
    if st.session_state.logged_in and st.session_state.access_token:
        user_id = str(st.session_state.user_info["id"])  # Get the user ID
        if clear_chat_history(user_id):  # Use the imported clear_chat_history function
            st.session_state.messages = []  # Also clear the session state messages
            st.rerun()  # Refresh the page to show empty chat
        else:
            st.error("Failed to clear chat history")
    else:
        # For non-logged in users, just clear the session state messages
        if "messages" in st.session_state:
            st.session_state.messages = []
        st.rerun()

def toggle_login_page():
    """Toggle the login page display"""
    st.session_state.show_login_page = not st.session_state.show_login_page
    st.rerun()

def load_user_chat_history():
    """Load the user's chat history from DynamoDB into session state"""
    if st.session_state.logged_in and "user_info" in st.session_state:
        user_id = str(st.session_state.user_info["id"])
        chat_history = get_chat_history(user_id)
        logging.info(f"Retrieved chat history for user {user_id}: {len(chat_history)} messages")
        
        # Replace the current session messages with the user's history
        st.session_state.messages = chat_history
        return chat_history
    return []

def custom_logout():
    """Custom logout function that also clears the messages"""
    logging.info("User logged out.")
    st.session_state.logged_in = False
    st.session_state.access_token = None
    st.session_state.messages = []  # Clear the messages when logging out
    if "user_info" in st.session_state:
        del st.session_state.user_info  # Remove user info from session
    st.session_state.logout_trigger = not st.session_state.logout_trigger  # Toggle the trigger
    st.rerun()  # Force a rerun to update the UI

# Function to display the main page
def main_page():
    st.title("DeepQuery")
    st.subheader("Dive Deeper!")

    # Set up the sidebar
    st.sidebar.title("Options")

    # Login/Logout button in sidebar
    if st.session_state.logged_in:
        st.sidebar.write(f"Logged in as: {st.session_state.user_info.get('username', 'User')}")
        st.sidebar.button("Logout", on_click=custom_logout)  # Use custom logout function
    else:
        st.sidebar.button("Login", on_click=toggle_login_page)

    # Create DynamoDB table if user is logged in
    if st.session_state.logged_in:
        create_dynamodb_table()
        
        # We don't need to retrieve chat history here since it's handled by load_user_chat_history
        # which is called when user logs in
    
    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Connected Apps/Services toggle
    on = st.sidebar.toggle("Connected Apps/Services")
    if on:
        st.sidebar.page_link("https://boxflow.streamlit.app", label="Open Prompt Factory")
        st.sidebar.page_link("https://packman.streamlit.app", label="Open Pack Manager")

    # Select box for text gen or sudo search
    media_gen_or_text_gen = st.sidebar.selectbox(
        "Select Query Type", ["Text Gen", "Sudo Search"]
    )
    st.sidebar.write(f"You selected: {media_gen_or_text_gen}")

    # Conditional logic based on the selection
    if media_gen_or_text_gen == "Text Gen":
        # Display options for Text Gen
        model_options = ["Claude", "Cohere"]
        selected_model = st.sidebar.selectbox("Chat Model", model_options)
        st.sidebar.write(f"You selected: {selected_model}")

        # Initialize the vector store
        vector_store = create_vector_store()

        # File upload for context in the sidebar
        uploaded_file = st.sidebar.file_uploader(
            "Upload a file for context",
            type=["txt", "pdf", "docx", "csv", "json", "xlsx"],
        )
        if uploaded_file is not None:
            file_id = uploaded_file.name
            metadata = {"type": uploaded_file.type}

            # Handle different file types
            if uploaded_file.type == "application/pdf":
                # Save the uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(uploaded_file.read())
                    temp_file_path = temp_file.name

                # Use PDFPlumberLoader to extract text from PDF
                loader = PDFPlumberLoader(temp_file_path)
                documents = loader.load()
                file_content = "\n".join(doc.page_content for doc in documents)

                # Clean up the temporary file
                os.remove(temp_file_path)
            elif uploaded_file.type == "text/csv":
                # Read CSV file
                df = pd.read_csv(uploaded_file)
                # Convert first 10 rows to string for display
                preview = df.head(10).to_string()
                file_content = f"CSV Preview (First 10 rows):\n{preview}"

                # Display the preview in the chat
                with st.chat_message("assistant"):
                    st.markdown("I've loaded your CSV file. Here are the first 10 rows:")
                    st.dataframe(df.head(10))

                    # Initialize session state for 'graph_data'
                    if "graph_data" not in st.session_state:
                        st.session_state["graph_data"] = False

                    # When the button is clicked, update session state
                    if st.button("Graph Data"):
                        st.session_state["graph_data"] = True

                    # If 'graph_data' is True, display the chart options
                    if st.session_state["graph_data"]:
                        option = st.selectbox(
                            "Which type of chart would you like to display?",
                            ("Area Chart", "Bar Chart", "Line Chart", "Scatter Chart"),
                        )

                        st.write("You selected:", option)

                        # Get numerical columns only
                        numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns

                        if numeric_cols.empty:
                            st.error("No numerical columns found in the uploaded file.")
                        else:
                            # Unique key for each multiselect to avoid conflicts
                            multiselect_key = f"{option.lower().replace(' ', '_')}_columns"

                            selected_columns = st.multiselect(
                                "Select columns to plot:",
                                options=numeric_cols,
                                default=numeric_cols[:3] if len(numeric_cols) > 0 else None,
                                key=multiselect_key,
                            )

                            if selected_columns:
                                st.subheader(f"{option}")
                                if option == "Area Chart":
                                    st.area_chart(data=df[selected_columns])
                                elif option == "Bar Chart":
                                    st.bar_chart(data=df[selected_columns])
                                elif option == "Line Chart":
                                    st.line_chart(data=df[selected_columns])
                                elif option == "Scatter Chart":
                                    # For scatter chart, we need to select two columns for x and y axes
                                    if len(selected_columns) >= 2:
                                        x_axis = st.selectbox(
                                            "Select X-axis column:", options=selected_columns
                                        )
                                        y_axis = st.selectbox(
                                            "Select Y-axis column:",
                                            options=[col for col in selected_columns if col != x_axis],
                                        )

                                        # Create a scatter plot using Altair
                                        import altair as alt

                                        scatter_chart = alt.Chart(df).mark_circle(size=60).encode(
                                            x=x_axis,
                                            y=y_axis,
                                            tooltip=selected_columns,
                                        ).interactive()

                                        st.altair_chart(scatter_chart, use_container_width=True)
                                    else:
                                        st.warning("Please select at least two columns for scatter plot.")
                            else:
                                st.warning("Please select at least one column to plot.")

                            # Reset button to clear the session state
                            if st.button("Reset"):
                                st.session_state["graph_data"] = False
            else:
                # Decode other text-based files
                file_content = uploaded_file.read().decode("utf-8")

            # Add the uploaded file content to the vector store
            add_documents_to_store(vector_store, [(file_id, file_content, metadata)])
            st.sidebar.success("File uploaded and embedded successfully!")

        # Pack options - only available when logged in
        if st.session_state.logged_in:
            # Select box in the sidebar for packs
            packs = get_current_packs()
            pack_options = ["No Pack"] + [pack["Pack Name"] for pack in packs]
            selected_pack = st.sidebar.selectbox("Connect to a Pack", pack_options)

            # Store the selected pack's ID if a pack is selected
            if selected_pack != "No Pack":
                selected_pack_info = next(
                    pack for pack in packs if pack["Pack Name"] == selected_pack
                )
                st.session_state.selected_pack_id = selected_pack_info["Pack ID"]
            else:
                st.session_state.selected_pack_id = None

            st.sidebar.write(f"You selected: {selected_pack}")
        else:
            # Show message about login required for packs
            st.sidebar.info("Login to access your Packs")
            selected_pack = "No Pack"

    elif media_gen_or_text_gen == "Sudo Search":
        st.sidebar.write("Sudo Search options will be displayed here.")

        logging.info("Initializing Tavily search...")
        tavily_search = TavilySearchAPIWrapper()
        search = TavilySearchResults(api_wrapper=tavily_search)

        if sudo_query := st.chat_input("Enter your sudo search here."):
            logging.info(f"Sudo Search query: {sudo_query}")
            
            # Add to chat history
            st.session_state.messages.append({"role": "user", "content": sudo_query})
            
            # Display the message
            with st.chat_message("user"):
                st.markdown(sudo_query)
                
            # Save to DynamoDB if logged in
            if st.session_state.logged_in:
                user_id = str(st.session_state.user_info["id"])
                add_user_message(user_id, sudo_query)
                
            # Perform search
            with st.chat_message("assistant"):
                with st.spinner("Searching..."):
                    search_results = search.run(sudo_query)
                    st.write(search_results)
                    
                    # Add to chat history
                    st.session_state.messages.append({"role": "assistant", "content": str(search_results)})
                    
                    # Save to DynamoDB if logged in
                    if st.session_state.logged_in:
                        user_id = str(st.session_state.user_info["id"])
                        add_ai_message(user_id, str(search_results))

    # Clear Chat History button - visible to all users
    st.sidebar.button("Clear Chat History", on_click=handle_clear_chat_history)

    # Initialize the agent for Text Gen
    if media_gen_or_text_gen == "Text Gen" and 'selected_model' in locals():
        if selected_model == "Claude":
            model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        else:
            model_id = "cohere.command-r-plus-v1:0"
        agent_executor = initialize_agent(model_id=model_id)
    else:
        agent_executor = None

    # Initialize tool_logs
    tool_logs = []

    # Accept user input for Text Gen mode
    if media_gen_or_text_gen == "Text Gen" and agent_executor and (prompt := st.chat_input("What is up?")):
        logging.info(f"User prompt: {prompt}")

        # Add message to session state
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display the message
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Save to DynamoDB if logged in
        if st.session_state.logged_in:
            user_id = str(st.session_state.user_info["id"])
            add_user_message(user_id, prompt)

        # Query the vector store with the user's prompt
        search_results = search_documents(vector_store, prompt)
        search_results_content = "\n".join([doc.page_content for doc in search_results])

        # Construct the base prompt with local search results
        agent_prompt = f"PROMPT: {prompt}\nLOCAL SEARCH RESULTS: {search_results_content}"

        # Only query Pinecone pack if logged in and a specific pack is selected (not "No Pack")
        if st.session_state.logged_in and selected_pack != "No Pack":
            username = st.session_state.user_info.get("username")
            pinecone_results = query_pinecone_pack(username, selected_pack, prompt)
            if pinecone_results and isinstance(pinecone_results, dict):
                try:
                    # Parse the response body
                    body = json.loads(pinecone_results.get("body", "{}"))
                    matches = body.get("message", {}).get("matches", [])

                    # Extract text from matches
                    pack_texts = []
                    for match in matches:
                        if "metadata" in match and "text" in match["metadata"]:
                            pack_texts.append(match["metadata"]["text"])

                    # Add pack results to prompt if we found any
                    if pack_texts:
                        pack_content = "\n".join(pack_texts)
                        agent_prompt += f"\nPINECONE PACK RESULTS: {pack_content}"
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing Pinecone results: {e}")

        # Get the agent's response and display it dynamically
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            agent_response = ""

            # Pass the full context to the agent while keeping clean chat history
            temp_history = st.session_state.messages.copy()
            # Replace last prompt with full context
            temp_history[-1]["content"] = agent_prompt

            # Stream chunks from the agent
            for chunk in query_agent(agent_executor, temp_history):
                if chunk["type"] == "response":
                    agent_response += chunk["content"]
                    response_placeholder.markdown(agent_response)
                elif chunk["type"] == "tool_log":
                    tool_logs.append(chunk["content"])
                elif chunk["type"] == "error":
                    st.error(chunk["content"])

        # Log the agent's response
        logging.info(f"Agent response: {agent_response}")

        # Add the agent response to session state
        if agent_response:
            st.session_state.messages.append({"role": "assistant", "content": agent_response})
            
            # Save to DynamoDB if logged in
            if st.session_state.logged_in:
                user_id = str(st.session_state.user_info["id"])
                add_ai_message(user_id, agent_response)

    # Check if there are any tool logs to display
    if tool_logs:
        with st.expander("Tool Usage Logs", expanded=False):
            st.write("Here are the details of the tool usage:")
            for log in tool_logs:
                st.text(log)


# Main app flow
if st.session_state.show_login_page and not st.session_state.logged_in:
    # Only show login page if explicitly requested AND user is not logged in
    login_page()
    
    # Add a back button to return to main page
    if st.button("Back to Main Page"):
        st.session_state.show_login_page = False
        st.rerun()
else:
    # Auto-hide the login page if user logged in successfully
    if st.session_state.logged_in and st.session_state.show_login_page:
        st.session_state.show_login_page = False
        st.rerun()
        
    # Show main page by default
    if st.session_state.logged_in:
        # If user logs in, retrieve user info and chat history
        access_token = st.session_state.access_token
        if access_token:
            # Only fetch user info if we don't have it yet
            if "user_info" not in st.session_state:
                user_info = get_user_info(access_token)
                if user_info:
                    st.session_state.user_info = user_info
                    logging.info(f"User Info: {user_info}")
                    # Load chat history after setting user info
                    load_user_chat_history()
                else:
                    logging.warning("Failed to retrieve user info.")
                    st.session_state.logged_in = False
            else:
                # We have user info but make sure chat history is loaded
                if not st.session_state.messages:  # Only reload if messages is empty
                    load_user_chat_history()
    
    # Display main page
    main_page()
