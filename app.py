import streamlit as st
import os
import logging
from agent import initialize_agent, query_agent
from local_vector_store import create_vector_store, add_documents_to_store, search_documents
from langchain_community.document_loaders import PDFPlumberLoader
import tempfile
from auth import login_page, logout, get_user_info  # Import the login and logout functions
from dynamodb import create_dynamodb_table, get_chat_history, add_user_message, add_ai_message, clear_chat_history  # DynamoDB functions
from packs import get_current_packs, query_pinecone_pack  # Import the get_current_packs function
import json
import pandas as pd
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities.tavily_search import TavilySearchAPIWrapper
from test import call_sana, initialize_replicate_client
from PIL import Image
import requests
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Set AWS Credentials as Environment Variables ===
os.environ["AWS_ACCESS_KEY_ID"] = st.secrets["default"]["ACCESS_KEY"]
os.environ["AWS_SECRET_ACCESS_KEY"] = st.secrets["default"]["SECRET_KEY"]
os.environ["AWS_DEFAULT_REGION"] = st.secrets["default"]["REGION"]

# Initialize session state for login
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'access_token' not in st.session_state:
    st.session_state.access_token = None

if 'logout_trigger' not in st.session_state:
    st.session_state.logout_trigger = False

# Ensure user info is retrieved only when logged in
if st.session_state.logged_in and 'user_info' not in st.session_state:
    access_token = st.session_state.access_token
    if access_token:
        user_info = get_user_info(access_token)
        if user_info:
            st.session_state.user_info = user_info
            logging.info(f"User Info: {user_info}")
        else:
            logging.warning("Failed to retrieve user info.")
            # Force the user to re-login
            st.session_state.logged_in = False
    else:
        logging.warning("Access token is not available to retrieve user info.")
        # Force the user to re-login
        st.session_state.logged_in = False

# Function to display the main page
def main_page():
    logging.info(f"Access Token: {st.session_state.access_token}")
    st.sidebar.title("Options")

    # Ensure DynamoDB table exists
    create_dynamodb_table()

    # Use the access token as session ID for chat history
    session_id = st.session_state.access_token
    if not session_id:
        st.error("Session ID not found. Please log in.")
        return

    # Retrieve user ID from user info
    user_id = str(st.session_state.user_info["id"])

    # Retrieve chat history from DynamoDB
    chat_history = get_chat_history(user_id)
    logging.info(f"Retrieved chat history: {chat_history}")

    st.title("DeepQuery")
    st.subheader("Dive Deeper!")

    # Display chat messages from history on app rerun
    for message in chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    on = st.sidebar.toggle("Connected Apps/Services")
    if on:
        st.sidebar.page_link("https://boxflow.streamlit.app", label="Open Prompt Factory")
        st.sidebar.page_link("https://packman.streamlit.app", label="Open Pack Manager")

    
    # Select box for image gen or text gen
    media_gen_or_text_gen = st.sidebar.selectbox("Media Gen or Text Gen", ["Text Gen", "Media Gen", "Sudo Search"])
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
            type=["txt", "pdf", "docx", "csv", "json", "xlsx"]
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
            else:
                # Handle other file types (e.g., txt, csv, etc.)
                if uploaded_file.type == "text/csv":
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
                            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns

                            if numeric_cols.empty:
                                st.error("No numerical columns found in the uploaded file.")
                            else:
                                # Unique key for each multiselect to avoid conflicts
                                multiselect_key = f"{option.lower().replace(' ', '_')}_columns"

                                selected_columns = st.multiselect(
                                    "Select columns to plot:",
                                    options=numeric_cols,
                                    default=numeric_cols[:3] if len(numeric_cols) > 0 else None,
                                    key=multiselect_key
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
                                            x_axis = st.selectbox("Select X-axis column:", options=selected_columns)
                                            y_axis = st.selectbox(
                                                "Select Y-axis column:",
                                                options=[col for col in selected_columns if col != x_axis]
                                            )

                                            # Create a scatter plot using Altair
                                            import altair as alt
                                            scatter_chart = alt.Chart(df).mark_circle(size=60).encode(
                                                x=x_axis,
                                                y=y_axis,
                                                tooltip=selected_columns
                                            ).interactive()

                                            st.altair_chart(scatter_chart, use_container_width=True)
                                        else:
                                            st.warning("Please select at least two columns for scatter plot.")
                                else:
                                      st.warning("Please select at least one column to plot.")

                                # Reset button to clear the session state
                                if st.button("Reset"):
                                    st.session_state['graph_data'] = False
                else:
                    # Decode other text-based files
                    file_content = uploaded_file.read().decode('utf-8')

            # Add the uploaded file content to the vector store
            add_documents_to_store(vector_store, [(file_id, file_content, metadata)])
            st.sidebar.success("File uploaded and embedded successfully!")

        # Select box in the sidebar for packs
        packs = get_current_packs()
        pack_options = ["No Pack"] + [pack["Pack Name"] for pack in packs]
        selected_pack = st.sidebar.selectbox("Connect to a Pack", pack_options)
        
        # Store the selected pack's ID if a pack is selected
        if selected_pack != "No Pack":
            selected_pack_info = next(pack for pack in packs if pack["Pack Name"] == selected_pack)
            st.session_state.selected_pack_id = selected_pack_info["Pack ID"]
        else:
            st.session_state.selected_pack_id = None
        
        st.sidebar.write(f"You selected: {selected_pack}")

    elif media_gen_or_text_gen == "Media Gen":
        # Display options for Media Gen
        st.sidebar.write("Media Gen options will be displayed here.")
        # Example: Add a different set of models or tools
        media_model_options = ["Nvidia/Sana"]
        selected_media_model = st.sidebar.selectbox("Media Model", media_model_options)
        st.sidebar.write(f"You selected: {selected_media_model}")

        if selected_media_model == "Nvidia/Sana":
            # Model variant selection (if applicable)
            # If model variants are needed, add another selectbox here
            # For now, we'll keep it static as per your requirement

            # Width and Height selection
            width_height = st.sidebar.selectbox("Width/Height", ["1024/1024"])
            guidance_scale = st.sidebar.slider("Guidance Scale", 1, 10, 5)
            num_inference_steps = st.sidebar.slider("Number of Inference Steps", 1, 100, 18)
            
            # Define a mapping from width_height to width and height
            variant_mapping = {
                "1024/1024": (1024, 1024),
                "1600M-1024px": (1600, 1024),
                "1600M-512px": (1600, 512)
            }

            # Get width and height based on the selected width_height
            width, height = variant_mapping.get(width_height, (1024, 1024))  # Defaults to (1024, 1024) if variant not found

            if prompt := st.chat_input("Enter your prompt here."):
                logging.info(f"User prompt: {prompt}")
                
                # Initialize the Replicate client
                replicate_client = initialize_replicate_client()
                
                # Call the function with all required arguments
                output = call_sana(
                    prompt=prompt,
                    replicate_client=replicate_client,
                    width=width,
                    height=height,
                    model_variant=selected_media_model,  # Use the selected model variant
                    guidance_scale=guidance_scale,
                    num_inference_steps=num_inference_steps
                )
                
                # Verify the output type
                if isinstance(output, str):
                    st.image(output, caption="Generated Image")
                else:
                    logging.error(f"Unexpected output type: {type(output)}")
                    st.error("Failed to generate image due to unexpected output type.")

    elif media_gen_or_text_gen == "Sudo Search":

        st.sidebar.write("Sudo Search options will be displayed here.")

        logging.info("Initializing Tavily search...")
        tavily_search = TavilySearchAPIWrapper()
        search = TavilySearchResults(api_wrapper=tavily_search)
        
        if sudo_query := st.chat_input("Enter your sudo search here."):
            logging.info(f"Sudo Search query: {sudo_query}")
            search_results = search.run(sudo_query)
            st.write(search_results)

    # Common options for both Text Gen, Media Gen, and Sudo Search
    st.sidebar.button("Clear Chat History", on_click=clear_chat_history)
    st.sidebar.button("Logout", on_click=logout)

    # Initialize the agent
    if media_gen_or_text_gen == "Text Gen" and selected_model in model_options:
        if selected_model == "Claude":
            model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        else:
            model_id = "cohere.command-r-plus-v1:0"
        agent_executor = initialize_agent(model_id=model_id)
    elif media_gen_or_text_gen == "Media Gen" and selected_media_model in media_model_options:
        # Initialize media generation agent or tools
        pass
    else:
        st.error("Selected model is not supported.")
        return

    # -------------------------------------------------
    # Ensure tool_logs is defined in this scope
    tool_logs = []
    # -------------------------------------------------

    # Accept user input
    if prompt := st.chat_input("What is up?"):
        logging.info(f"User prompt: {prompt}")

        # Add just the prompt to chat history display
        chat_history.append({"role": "human", "content": prompt})

        # Query the vector store with the user's prompt
        search_results = search_documents(vector_store, prompt)
        search_results_content = "\n".join([doc.page_content for doc in search_results])
        
        # Construct the base prompt with local search results
        agent_prompt = f"PROMPT: {prompt}\nLOCAL SEARCH RESULTS: {search_results_content}"
        
        # Only query Pinecone pack if a specific pack is selected (not "No Pack")
        if selected_pack != "No Pack":
            username = st.session_state.user_info.get("username")
            pinecone_results = query_pinecone_pack(username, selected_pack, prompt)
            if pinecone_results and isinstance(pinecone_results, dict):
                try:
                    # Parse the response body
                    body = json.loads(pinecone_results.get('body', '{}'))
                    matches = body.get('message', {}).get('matches', [])
                    
                    # Extract text from matches
                    pack_texts = []
                    for match in matches:
                        if 'metadata' in match and 'text' in match['metadata']:
                            pack_texts.append(match['metadata']['text'])
                    
                    # Add pack results to prompt if we found any
                    if pack_texts:
                        pack_content = "\n".join(pack_texts)
                        agent_prompt += f"\nPINECONE PACK RESULTS: {pack_content}"
                        
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing Pinecone results: {e}")

        # Add just the user prompt to DynamoDB chat history
        add_user_message(user_id, prompt)
        
        # Display just the prompt in the chat
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get the agent's response and display it dynamically
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            agent_response = ""

            # Pass the full context to the agent while keeping clean chat history
            temp_history = chat_history.copy()
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

        # Add the agent response to DynamoDB chat history
        if agent_response:
            add_ai_message(user_id, agent_response)

    # Check if there are any tool logs to display
    if tool_logs:
        with st.expander("Tool Usage Logs", expanded=False):
            st.write("Here are the details of the tool usage:")
            for log in tool_logs:
                st.text(log)

# Display the appropriate page based on login state
if st.session_state.logged_in:
    main_page()
else:
    login_page()
