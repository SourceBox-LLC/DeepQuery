import streamlit as st
import os
import logging
from dotenv import load_dotenv
from agent import initialize_agent, query_agent
from local_vector_store import create_vector_store, add_documents_to_store, search_documents
from langchain_community.document_loaders import PDFPlumberLoader
import tempfile
from auth import login_page, logout  # Import the login and logout functions

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

# Function to display the main page
def main_page():
    logging.info(f"Access Token: {st.session_state.access_token}")
    st.sidebar.title("Options")

    # Select box for chatbot model
    model_options = ["Claude", "Cohere"]
    selected_model = st.sidebar.selectbox("Chat Model", model_options)
    st.sidebar.write(f"You selected: {selected_model}")

    # Select box for conversation history
    history_options = ["New Conversation", "History 1", "History 2"]
    selected_history = st.sidebar.selectbox("Conversation History", history_options)
    st.sidebar.write(f"You selected: {selected_history}")

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
        else:
            # Decode other text-based files
            file_content = uploaded_file.read().decode('utf-8')

        # Add the uploaded file content to the vector store
        add_documents_to_store(vector_store, [(file_id, file_content, metadata)])
        st.sidebar.success("File uploaded and embedded successfully!")

    # Select box in the sidebar for packs
    pack_options = ["No Pack", "Pack 1", "Pack 2"]
    selected_pack = st.sidebar.selectbox("Connect to a Pack", pack_options)
    st.sidebar.write(f"You selected: {selected_pack}")

    # Activate voice toggle
    voice_toggle = st.sidebar.toggle("Activate Voice", value=False)
    if voice_toggle:
        audio_input = st.sidebar.audio_input("Record a voice message")
        if audio_input:
            st.sidebar.audio(audio_input)

    # Logout button in the sidebar
    st.sidebar.button("Logout", on_click=logout)

    # Initialize the agent
    if selected_model in model_options:
        if selected_model == "Claude":  
            model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        else:
            model_id = "cohere.command-r-plus-v1:0"

        agent_executor = initialize_agent(model_id=model_id)

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.title("DeepQuery")
    st.subheader("Dive Deeper!")

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("What is up?"):
        # Query the vector store with the user's prompt
        search_results = search_documents(vector_store, prompt)
        search_results_content = "\n".join([doc.page_content for doc in search_results])

        # Construct the complete prompt
        complete_prompt = f"PROMPT: {prompt}\nVECTOR SEARCH RESULTS: {search_results_content}"

        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": complete_prompt})
        with st.chat_message("user"):
            st.markdown(complete_prompt)

        # Get the agent's response and display it dynamically
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            agent_response = ""

            for chunk in query_agent(agent_executor, complete_prompt):
                agent_response += chunk
                response_placeholder.markdown(agent_response)
        
        # Add the agent response to the chat history if it exists
        if agent_response:
            st.session_state.messages.append({"role": "assistant", "content": agent_response})

# Display the appropriate page based on login state
if st.session_state.logged_in:
    main_page()
else:
    login_page()

# --- Helper Functions ---
def get_user_info(access_token):
    pass

def get_user_data(access_token):
    pass
