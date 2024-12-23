import streamlit as st
import os
import logging
from dotenv import load_dotenv
from agent import initialize_agent, query_agent
from local_vector_store import create_vector_store, add_documents_to_store, search_documents
from langchain_community.document_loaders import PDFPlumberLoader
import tempfile
from auth import login_page, logout, get_user_info  # Import the login and logout functions
from dynamodb import create_dynamodb_table, get_chat_history, add_user_message, add_ai_message, clear_chat_history  # DynamoDB functions
from packs import get_current_packs, query_pinecone_pack  # Import the get_current_packs function
import json
import pandas as pd

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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
    else:
        logging.warning("Access token is not available to retrieve user info.")


# --- Helper Functions ---
def handle_clear_chat_history():
    """Callback function for the clear chat history button."""
    if st.session_state.access_token:
        user_id = str(st.session_state.user_info["id"])  # Get the user ID
        if clear_chat_history(user_id):  # Use the imported clear_chat_history function
            st.rerun()  # Refresh the page to show empty chat
        else:
            st.error("Failed to clear chat history")

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

    # Select box for chatbot model
    model_options = ["Claude", "Cohere"]
    selected_model = st.sidebar.selectbox("Chat Model", model_options)
    st.sidebar.write(f"You selected: {selected_model}")

    # Initialize the vector store
    vector_store = create_vector_store()

    # File upload for context in the sidebar
    uploaded_file = st.sidebar.file_uploader("Upload a file for context", type=["txt", "pdf", "docx", "csv", "json", "xlsx"])
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
                st.button("Graph Data")
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

    # Activate voice toggle
    voice_toggle = st.sidebar.toggle("Activate Voice", value=False)
    if voice_toggle:
        audio_input = st.sidebar.audio_input("Record a voice message")
        if audio_input:
            st.sidebar.audio(audio_input)
    
    st.sidebar.button("Clear Chat History", on_click=handle_clear_chat_history)

    # Logout button in the sidebar
    st.sidebar.button("Logout", on_click=logout)

    # Initialize the agent
    if selected_model in model_options:
        if selected_model == "Claude":
            model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        else:
            model_id = "cohere.command-r-plus-v1:0"
        agent_executor = initialize_agent(model_id=model_id)
    else:
        st.error("Selected model is not supported.")
        return

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
            temp_history[-1]["content"] = agent_prompt  # Replace last prompt with full context
            for chunk in query_agent(agent_executor, temp_history):
                # Check if the chunk contains a data URI for an image
                if chunk and "data:image/png;base64," in chunk:
                    # Split the response into text and image parts
                    parts = chunk.split("data:image/png;base64,")
                    text_part = parts[0]
                    image_data = parts[1].split('"')[0]  # Extract just the base64 data
                    
                    # Display any text before the image
                    if text_part:
                        agent_response += text_part
                        response_placeholder.markdown(agent_response)
                    
                    # Display the image
                    st.image(f"data:image/png;base64,{image_data}")
                    
                    # Continue with any remaining text
                    if len(parts) > 2:
                        remaining_text = "".join(parts[2:])
                        agent_response += remaining_text
                        response_placeholder.markdown(agent_response)
                else:
                    agent_response += chunk
                    response_placeholder.markdown(agent_response)

        # Log the agent's response
        logging.info(f"Agent response: {agent_response}")

        # Add the agent response to DynamoDB chat history
        if agent_response:
            add_ai_message(user_id, agent_response)

# Display the appropriate page based on login state
if st.session_state.logged_in:
    main_page()
else:
    login_page()
