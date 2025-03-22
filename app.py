import streamlit as st
import os
import logging
from agent import initialize_agent, query_agent
from local_vector_store import create_vector_store, add_documents_to_store, search_documents
from langchain_community.document_loaders import PDFPlumberLoader
from standard_chat import query_chat
import tempfile
from auth import login_page, logout, get_user_info, register_page, check_token  # Import the authentication functions
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
# Remove TavilySearchResults and its wrapper imports since we are using the official client
#from langchain_community.tools.tavily_search import TavilySearchResults
#from langchain.utilities.tavily_search import TavilySearchAPIWrapper
from tavily import TavilyClient  # Official Tavily Python client
from PIL import Image
import requests
from io import BytesIO

# Set page configuration - MUST be the first Streamlit command
st.set_page_config(
    page_title="DeepQuery",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === Set AWS Credentials as Environment Variables ===
os.environ["AWS_ACCESS_KEY_ID"] = st.secrets["default"]["ACCESS_KEY"]
os.environ["AWS_SECRET_ACCESS_KEY"] = st.secrets["default"]["SECRET_KEY"]
os.environ["AWS_DEFAULT_REGION"] = st.secrets["default"]["REGION"]

# === Immediately inject localStorage script for persistent login ===
def inject_localStorage_script():
    st.markdown("""
    <script>
    // Function to save auth data to localStorage and cookies
    function saveAuthData(token, username, userId) {
        console.log("Saving auth data to localStorage and cookies");
        localStorage.setItem("deepquery_token", token);
        localStorage.setItem("deepquery_username", username);
        localStorage.setItem("deepquery_user_id", userId);
        document.cookie = `deepquery_token=${token}; path=/; max-age=604800; SameSite=Lax`;
        document.cookie = `deepquery_username=${username}; path=/; max-age=604800; SameSite=Lax`;
        document.cookie = `deepquery_user_id=${userId}; path=/; max-age=604800; SameSite=Lax`;
        const url = new URL(window.location.href);
        url.searchParams.set("token", token);
        url.searchParams.set("username", username);
        url.searchParams.set("user_id", userId);
        window.location.href = url.toString();
    }
    
    function checkAuthData() {
        console.log("Checking for auth data in localStorage");
        const token = localStorage.getItem("deepquery_token");
        const username = localStorage.getItem("deepquery_username");
        const userId = localStorage.getItem("deepquery_user_id");
        if (token && username && userId) {
            console.log("Found auth data in localStorage");
            const url = new URL(window.location.href);
            if (!url.searchParams.has("token")) {
                console.log("Adding auth data to URL parameters");
                url.searchParams.set("token", token);
                url.searchParams.set("username", username);
                url.searchParams.set("user_id", userId);
                window.location.href = url.toString();
            }
        } else {
            console.log("No auth data in localStorage, checking cookies");
            const getCookie = (name) => {
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${name}=`);
                if (parts.length === 2) return parts.pop().split(';').shift();
                return null;
            };
            const cookieToken = getCookie("deepquery_token");
            const cookieUsername = getCookie("deepquery_username");
            const cookieUserId = getCookie("deepquery_user_id");
            if (cookieToken && cookieUsername && cookieUserId) {
                console.log("Found auth data in cookies");
                localStorage.setItem("deepquery_token", cookieToken);
                localStorage.setItem("deepquery_username", cookieUsername);
                localStorage.setItem("deepquery_user_id", cookieUserId);
                const url = new URL(window.location.href);
                if (!url.searchParams.has("token")) {
                    url.searchParams.set("token", cookieToken);
                    url.searchParams.set("username", cookieUsername);
                    url.searchParams.set("user_id", cookieUserId);
                    window.location.href = url.toString();
                }
            }
        }
    }
    
    function clearAuthData() {
        console.log("Clearing auth data from localStorage and cookies");
        localStorage.removeItem("deepquery_token");
        localStorage.removeItem("deepquery_username");
        localStorage.removeItem("deepquery_user_id");
        document.cookie = "deepquery_token=; path=/; max-age=0";
        document.cookie = "deepquery_username=; path=/; max-age=0";
        document.cookie = "deepquery_user_id=; path=/; max-age=0";
        window.location.href = window.location.pathname;
    }
    
    document.addEventListener("DOMContentLoaded", function() {
        checkAuthData();
        window.saveAuthData = saveAuthData;
        window.clearAuthData = clearAuthData;
    });
    checkAuthData();
    </script>
    
    <style>
    /* Main background and container styles */
    .main {
        background-color: #1e1e2e;
        color: #cdd6f4;
        font-family: 'Inter', sans-serif;
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
    }
    
    /* Container styling - remove max-width restriction */
    .stApp {
        max-width: none !important;
        margin: 0 !important;
        padding: 0 !important;
        width: 100vw !important;
        overflow-x: hidden !important;
    }
    
    /* Root layout fixes */
    [data-testid="stAppViewContainer"] {
        width: 100vw !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Force the main container to be full width */
    [data-testid="stAppViewContainer"] > section {
        width: 100vw !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Chat input fixes for full width */
    .stChatInput {
        border-radius: 16px !important;
        overflow: hidden !important;
        background-color: #313244 !important;
        width: 100% !important;
        margin-left: 0 !important;
    }
    
    /* More aggressive styles for chat input container */
    [data-testid="stChatInput"] {
        width: 100% !important;
        left: 0 !important;
        margin-left: 0 !important;
        padding-left: 0 !important;
        right: 0 !important;
        box-sizing: border-box !important;
    }
    
    [data-testid="stChatInput"] > div {
        width: 100% !important;
        padding-left: 0 !important;
        margin-left: 0 !important;
        box-sizing: border-box !important;
    }
    
    /* Target the parent of stChatInput to ensure full width */
    div:has(> [data-testid="stChatInput"]) {
        width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Remove any margin/padding from main container */
    .main .block-container {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Force the chat input to extend full width */
    div[data-testid="stChatInputContainer"] {
        width: 100% !important;
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    
    /* Fix any potential parent elements */
    div[data-testid="stChatInputContainer"] > div {
        width: 100% !important;
        margin-left: 0 !important;
        padding-left: 0 !important;
    }
    
    /* Fix footer to ensure proper alignment */
    footer {
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    
    /* Reset any potential hidden overflow */
    body {
        overflow-x: hidden !important;
    }
    
    /* Chat containers */
    .chat-container {
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #313244;
    }
    
    /* Chat message styling */
    .chat-message {
        padding: 1.2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        font-size: 16px;
        line-height: 1.5;
    }
    
    .user-message {
        background-color: #313244;
        color: #cdd6f4;
        margin-left: 2rem;
        border-top-left-radius: 2px;
    }
    
    .assistant-message {
        background-color: #45475a;
        color: #cdd6f4;
        margin-right: 2rem;
        border-top-right-radius: 2px;
    }
    
    /* Avatar styling */
    .avatar-container {
        padding: 0.5rem;
        background-color: #1e1e2e;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 48px;
        height: 48px;
        font-size: 2rem;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        margin: 0 auto;
    }
    
    .user-avatar {
        background-color: #89b4fa;
        color: #1e1e2e;
    }
    
    .assistant-avatar {
        background-color: #f38ba8;
        color: #1e1e2e;
    }
    
    /* Title and subtitle styling */
    .title {
        text-align: center;
        color: #cdd6f4;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 0px 2px 4px rgba(0, 0, 0, 0.1);
    }
    
    .subtitle {
        text-align: center;
        color: #a6adc8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Input fields */
    .stTextInput, .stTextArea, div[data-baseweb="input"] input, [data-testid="stFileUploader"] {
        background-color: #313244 !important;
        color: #cdd6f4 !important;
        border: 1px solid #45475a !important;
        border-radius: 8px !important;
    }
    
    /* Button styling */
    .stButton button {
        background-color: #cba6f7 !important;
        color: #1e1e2e !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton button:hover {
        background-color: #f5c2e7 !important;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Chat input styling */
    .stChatInput {
        border-radius: 16px !important;
        overflow: hidden !important;
        background-color: #313244 !important;
        width: 100% !important;
    }
    
    /* Make chat input container full width */
    [data-testid="stChatInput"] > div {
        width: 100% !important;
        max-width: 100% !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    
    /* Remove any potential padding in the container */
    .main .block-container {
        padding-left: 0 !important;
        padding-right: 0 !important;
        max-width: 100% !important;
    }
    
    /* Fix the gap by removing all margins from the chat container */
    footer {
        margin-left: 0 !important;
        padding-left: 0 !important;
        width: 100% !important;
    }
    
    /* ChatInput parent wrapper */
    .stChatInputContainer, 
    [data-testid="chatAnchor"] {
        padding-left: 0 !important;
        margin-left: 0 !important;
        width: 100vw !important;
        max-width: 100vw !important;
        left: 0 !important;
    }
    
    /* Fix the entire app container */
    .appview-container .main .block-container {
        max-width: 100% !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
    }
    
    /* Ensure main content area is full width */
    .main .block-container > div {
        width: 100% !important;
        max-width: 100% !important;
        padding: 0 !important;
    }
    
    /* Fix for chat message container width */
    [data-testid="stChatMessageContainer"] {
        width: 100% !important;
    }
    
    /* Make sidebar more modern */
    [data-testid="stSidebar"] {
        background-color: #181825 !important;
        border-right: 1px solid #313244 !important;
        padding: 1rem !important;
    }
    
    /* Headers in sidebar */
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #cba6f7 !important;
        font-weight: 600 !important;
    }
    
    /* Sidebar divider */
    [data-testid="stSidebar"] hr {
        border-color: #313244 !important;
        margin: 1.5rem 0 !important;
    }
    
    /* Images */
    img {
        border-radius: .5rem !important;
        margin: 1rem 0 !important;
    }
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #181825;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #45475a;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #cba6f7;
    }
    
    /* Error messages */
    .stAlert {
        background-color: #313244 !important;
        color: #f38ba8 !important;
        border-left-color: #f38ba8 !important;
    }
    
    /* Warning messages */
    .stWarning {
        background-color: #313244 !important;
        color: #fab387 !important;
        border-left-color: #fab387 !important;
    }
    
    /* Spinner */
    .stSpinner > div > div {
        border-color: #cba6f7 transparent transparent !important;
    }
    
    /* SelectBox styling */
    div[data-baseweb="select"] {
        background-color: #313244 !important;
    }
    
    div[data-baseweb="select"] > div {
        background-color: #313244 !important;
        border-color: #45475a !important;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #313244 !important;
        color: #cdd6f4 !important;
        border-radius: 8px !important;
    }
    
    .streamlit-expanderContent {
        background-color: #272839 !important;
        border-radius: 0 0 8px 8px !important;
        padding: 1rem !important;
    }
    
    /* Toggle styling */
    [data-testid="stToggleSwitch"] {
        background-color: #313244 !important;
    }
    
    /* Radio button styling */
    .stRadio > div {
        background-color: #313244 !important;
        padding: 0.5rem !important;
        border-radius: 8px !important;
    }
    
    /* Set page config */
    .stApp {
        background-color: #1e1e2e !important;
    }
    
    /* Message styling for chat */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    
    [data-testid="stChatMessageContent"] {
        padding: 1.2rem !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
    }
    
    [data-testid="stChatMessageContent"].user {
        background-color: #313244 !important;
        margin-left: 2rem !important;
        border-top-left-radius: 2px !important;
    }
    
    [data-testid="stChatMessageContent"].assistant {
        background-color: #45475a !important;
        margin-right: 2rem !important;
        border-top-right-radius: 2px !important;
    }
    
    /* Avatar styling for chat */
    [data-testid="stChatMessageAvatar"] {
        background-color: #1e1e2e !important;
        border-radius: 50% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 40px !important;
        height: 40px !important;
        font-size: 1.5rem !important;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2) !important;
    }
    
    [data-testid="stChatMessageAvatar"].user {
        background-color: #89b4fa !important;
        color: #1e1e2e !important;
    }
    
    [data-testid="stChatMessageAvatar"].assistant {
        background-color: #f38ba8 !important;
        color: #1e1e2e !important;
    }
    </style>
    """, unsafe_allow_html=True)

inject_localStorage_script()

def save_auth_data_to_browser():
    if st.session_state.logged_in and st.session_state.access_token:
        logging.info("Saving auth data to browser storage")
        token = st.session_state.access_token
        username = st.session_state.username or ""
        user_id = st.session_state.user_id or ""
        if not token or not username or not user_id:
            logging.warning("Missing token, username, or user_id - can't save to browser")
            return
        token = token.replace('"', '\\"')
        username = username.replace('"', '\\"')
        user_id = str(user_id).replace('"', '\\"')
        js_code = f"""
        <script>
        console.log("Executing saveAuthData from Streamlit");
        try {{
            if (typeof window.saveAuthData === 'function') {{
                window.saveAuthData(
                    "{token}", 
                    "{username}", 
                    "{user_id}"
                );
                console.log("Auth data saved successfully");
            }} else {{
                console.error("saveAuthData function not available - auth persistence may not work");
                localStorage.setItem("deepquery_token", "{token}");
                localStorage.setItem("deepquery_username", "{username}");
                localStorage.setItem("deepquery_user_id", "{user_id}");
                document.cookie = `deepquery_token={token}; path=/; max-age=604800; SameSite=Lax`;
                document.cookie = `deepquery_username={username}; path=/; max-age=604800; SameSite=Lax`;
                document.cookie = `deepquery_user_id={user_id}; path=/; max-age=604800; SameSite=Lax`;
            }}
        }} catch (e) {{
            console.error("Error saving auth data:", e);
        }}
        </script>
        """
        st.markdown(js_code, unsafe_allow_html=True)
        logging.info("Auth data save script injected")

def clear_auth_data_from_browser():
    js_code = """
    <script>
    if (typeof window.clearAuthData === 'function') {
        window.clearAuthData();
    } else {
        console.error("clearAuthData function not available");
    }
    </script>
    """
    st.markdown(js_code, unsafe_allow_html=True)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "logout_trigger" not in st.session_state:
    st.session_state.logout_trigger = False
if "show_login_page" not in st.session_state:
    st.session_state.show_login_page = False
if "register_trigger" not in st.session_state:
    st.session_state.register_trigger = False
if "username" not in st.session_state:
    st.session_state.username = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "clear_chat_trigger" not in st.session_state:
    st.session_state.clear_chat_trigger = False
if "should_save_auth" not in st.session_state:
    st.session_state.should_save_auth = False

def handle_clear_chat_history():
    if st.session_state.logged_in and st.session_state.access_token:
        user_id = str(st.session_state.user_info["id"])
        if clear_chat_history(user_id):
            st.session_state.messages = []
            st.session_state.clear_chat_trigger = True
        else:
            st.error("Failed to clear chat history")
    else:
        if "messages" in st.session_state:
            st.session_state.messages = []
            st.session_state.clear_chat_trigger = True

def toggle_login_page():
    st.session_state.show_login_page = not st.session_state.show_login_page

def load_user_chat_history():
    if st.session_state.logged_in and "user_info" in st.session_state:
        user_id = str(st.session_state.user_info["id"])
        chat_history = get_chat_history(user_id)
        logging.info(f"Retrieved chat history for user {user_id}: {len(chat_history)} messages")
        st.session_state.messages = chat_history
        return chat_history
    return []

def custom_logout():
    logging.info("User logged out.")
    st.session_state.logged_in = False
    st.session_state.access_token = None
    st.session_state.messages = []
    if "user_info" in st.session_state:
        del st.session_state.user_info
    st.session_state.logout_trigger = not st.session_state.logout_trigger
    clear_auth_data_from_browser()

def main_page():
    if st.session_state.clear_chat_trigger:
        st.session_state.clear_chat_trigger = False
    
    logging.info(f"Login state: logged_in={st.session_state.logged_in}, username={st.session_state.username}")
    if st.session_state.logged_in:
        logging.info(f"User info: {st.session_state.get('user_info', 'Not set')}")
        if 'user_info' not in st.session_state and st.session_state.access_token:
            logging.info("User logged in but user_info not found. Attempting to fetch it.")
            user_info = get_user_info(st.session_state.access_token)
            if user_info:
                st.session_state.user_info = user_info
                logging.info(f"User info fetched successfully: {user_info}")
                st.session_state.should_save_auth = True
            else:
                logging.error("Failed to fetch user_info despite having access token")
                st.warning("Your session has expired. Please log in again.")
                custom_logout()
                st.stop()
    
    # Replace the regular title with styled HTML title
    st.markdown("<h1 class='title'>DeepQuery</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle'>Dive Deeper!</p>", unsafe_allow_html=True)
    
    if st.session_state.logged_in and st.session_state.access_token:
        save_auth_data_to_browser()

    st.sidebar.title("Options")
    if st.session_state.logged_in:
        if "user_info" in st.session_state:
            display_name = st.session_state.user_info.get('username', st.session_state.username or 'User')
            st.sidebar.write(f"Logged in as: {display_name}")
        else:
            st.sidebar.write(f"Logged in as: {st.session_state.username or 'User'}")
        st.sidebar.button("Logout", on_click=custom_logout)
    else:
        st.sidebar.button("Login", on_click=toggle_login_page)

    if st.session_state.logged_in:
        create_dynamodb_table()
    
    # Create a container for the chat messages with proper styling
    with st.container():
        # Display messages with custom styling
        for message in st.session_state.messages:
            role = message["role"]
            content = message["content"]
            
            # Custom styling for chat messages
            if role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(content)
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(content)

    on = st.sidebar.toggle("Connected Apps/Services")
    if on:
        st.sidebar.page_link("https://boxflow.streamlit.app", label="Open Prompt Factory")
        st.sidebar.page_link("https://packman.streamlit.app", label="Open Pack Manager")

    media_gen_or_text_gen = st.sidebar.selectbox(
        "Select Query Type", ["Agent", "Sudo Search", "Standard Chat"]
    )

    if media_gen_or_text_gen == "Agent":
        model_options = ["Claude", "Cohere"]
        selected_model = st.sidebar.selectbox("Chat Model", model_options)
        st.sidebar.write(f"You selected: {selected_model}")
        vector_store = create_vector_store()
        uploaded_file = st.sidebar.file_uploader(
            "Upload a file for context",
            type=["txt", "pdf", "docx", "csv", "json", "xlsx"],
        )
        if uploaded_file is not None:
            file_id = uploaded_file.name
            metadata = {"type": uploaded_file.type}
            if uploaded_file.type == "application/pdf":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(uploaded_file.read())
                    temp_file_path = temp_file.name
                loader = PDFPlumberLoader(temp_file_path)
                documents = loader.load()
                file_content = "\n".join(doc.page_content for doc in documents)
                os.remove(temp_file_path)
            elif uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)
                preview = df.head(10).to_string()
                file_content = f"CSV Preview (First 10 rows):\n{preview}"
                with st.chat_message("assistant"):
                    st.markdown("I've loaded your CSV file. Here are the first 10 rows:")
                    st.dataframe(df.head(10))
                    if "graph_data" not in st.session_state:
                        st.session_state["graph_data"] = False
                    if st.button("Graph Data"):
                        st.session_state["graph_data"] = True
                    if st.session_state["graph_data"]:
                        option = st.selectbox(
                            "Which type of chart would you like to display?",
                            ("Area Chart", "Bar Chart", "Line Chart", "Scatter Chart"),
                        )
                        st.write("You selected:", option)
                        numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns
                        if numeric_cols.empty:
                            st.error("No numerical columns found in the uploaded file.")
                        else:
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
                                    if len(selected_columns) >= 2:
                                        x_axis = st.selectbox(
                                            "Select X-axis column:", options=selected_columns
                                        )
                                        y_axis = st.selectbox(
                                            "Select Y-axis column:",
                                            options=[col for col in selected_columns if col != x_axis],
                                        )
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
                            if st.button("Reset"):
                                st.session_state["graph_data"] = False
            else:
                file_content = uploaded_file.read().decode("utf-8")
            add_documents_to_store(vector_store, [(file_id, file_content, metadata)])
            st.sidebar.success("File uploaded and embedded successfully!")
        if st.session_state.logged_in:
            packs = get_current_packs()
            pack_options = ["No Pack"] + [pack["Pack Name"] for pack in packs]
            selected_pack = st.sidebar.selectbox("Connect to a Pack", pack_options)
            if selected_pack != "No Pack":
                selected_pack_info = next(
                    pack for pack in packs if pack["Pack Name"] == selected_pack
                )
                st.session_state.selected_pack_id = selected_pack_info["Pack ID"]
            else:
                st.session_state.selected_pack_id = None
            st.sidebar.write(f"You selected: {selected_pack}")
        else:
            st.sidebar.info("Login to access your Packs")
            selected_pack = "No Pack"
    elif media_gen_or_text_gen == "Standard Chat":
        st.sidebar.write("Standard Chat options will be displayed here.")
        model = st.sidebar.selectbox("Select a model", ["meta/meta-llama-3-8b-instruct", "anthropic/claude-3.5-haiku", "deepseek-ai/deepseek-r1"])
        st.sidebar.write(f"You selected: {model}")
        
        # Add vector store and file upload capabilities
        vector_store = create_vector_store()
        uploaded_file = st.sidebar.file_uploader(
            "Upload a file for context",
            type=["txt", "pdf", "docx", "csv", "json", "xlsx"],
        )
        
        # Process uploaded files (same as in Agent mode)
        if uploaded_file is not None:
            file_id = uploaded_file.name
            metadata = {"type": uploaded_file.type}
            if uploaded_file.type == "application/pdf":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(uploaded_file.read())
                    temp_file_path = temp_file.name
                loader = PDFPlumberLoader(temp_file_path)
                documents = loader.load()
                file_content = "\n".join(doc.page_content for doc in documents)
                os.remove(temp_file_path)
            elif uploaded_file.type == "text/csv":
                df = pd.read_csv(uploaded_file)
                preview = df.head(10).to_string()
                file_content = f"CSV Preview (First 10 rows):\n{preview}"
                with st.chat_message("assistant"):
                    st.markdown("I've loaded your CSV file. Here are the first 10 rows:")
                    st.dataframe(df.head(10))
                    if "graph_data" not in st.session_state:
                        st.session_state["graph_data"] = False
                    if st.button("Graph Data"):
                        st.session_state["graph_data"] = True
                    if st.session_state["graph_data"]:
                        option = st.selectbox(
                            "Which type of chart would you like to display?",
                            ("Area Chart", "Bar Chart", "Line Chart", "Scatter Chart"),
                        )
                        st.write("You selected:", option)
                        numeric_cols = df.select_dtypes(include=["float64", "int64"]).columns
                        if numeric_cols.empty:
                            st.error("No numerical columns found in the uploaded file.")
                        else:
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
                                    if len(selected_columns) >= 2:
                                        x_axis = st.selectbox(
                                            "Select X-axis column:", options=selected_columns
                                        )
                                        y_axis = st.selectbox(
                                            "Select Y-axis column:",
                                            options=[col for col in selected_columns if col != x_axis],
                                        )
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
                            if st.button("Reset"):
                                st.session_state["graph_data"] = False
            else:
                file_content = uploaded_file.read().decode("utf-8")
            add_documents_to_store(vector_store, [(file_id, file_content, metadata)])
            st.sidebar.success("File uploaded and embedded successfully!")
        
        # Add pack integration (same as in Agent mode)
        selected_pack = "No Pack"
        if st.session_state.logged_in:
            packs = get_current_packs()
            pack_options = ["No Pack"] + [pack["Pack Name"] for pack in packs]
            selected_pack = st.sidebar.selectbox("Connect to a Pack", pack_options)
            if selected_pack != "No Pack":
                selected_pack_info = next(
                    pack for pack in packs if pack["Pack Name"] == selected_pack
                )
                st.session_state.selected_pack_id = selected_pack_info["Pack ID"]
            else:
                st.session_state.selected_pack_id = None
            st.sidebar.write(f"You selected: {selected_pack}")
        else:
            st.sidebar.info("Login to access your Packs")
        
        # Chat input for Standard Chat
        if standard_chat_query := st.chat_input("Enter your message here..."):
            logging.info(f"Standard Chat query: {standard_chat_query}")
            
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": standard_chat_query})
            
            # Display the user message
            with st.chat_message("user"):
                st.markdown(standard_chat_query)
                
            # Save to DynamoDB if logged in
            if st.session_state.logged_in:
                user_id = str(st.session_state.user_info["id"])
                add_user_message(user_id, standard_chat_query)
            
            # Search for relevant documents
            search_results = search_documents(vector_store, standard_chat_query)
            search_results_content = "\n".join([doc.page_content for doc in search_results])
            
            # Format the query with search results
            enhanced_query = f"QUERY: {standard_chat_query}\nLOCAL SEARCH RESULTS: {search_results_content}"
            
            # Add pack results if available
            if st.session_state.logged_in and selected_pack != "No Pack":
                username = st.session_state.user_info.get("username")
                pinecone_results = query_pinecone_pack(username, selected_pack, standard_chat_query)
                if pinecone_results and isinstance(pinecone_results, dict):
                    try:
                        body = json.loads(pinecone_results.get("body", "{}"))
                        matches = body.get("message", {}).get("matches", [])
                        pack_texts = []
                        for match in matches:
                            if "metadata" in match and "text" in match["metadata"]:
                                pack_texts.append(match["metadata"]["text"])
                        if pack_texts:
                            pack_content = "\n".join(pack_texts)
                            enhanced_query += f"\nPINECONE PACK RESULTS: {pack_content}"
                    except json.JSONDecodeError as e:
                        logging.error(f"Error parsing Pinecone results: {e}")
            
            # Generate response using the query_chat function
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Call the query_chat function with the enhanced query
                        response = query_chat(enhanced_query, model)
                        
                        # Display the response
                        st.markdown(response)
                        
                        # Add to chat history
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        
                        # Save to DynamoDB if logged in
                        if st.session_state.logged_in:
                            user_id = str(st.session_state.user_info["id"])
                            add_ai_message(user_id, response)
                    except Exception as e:
                        error_msg = f"Error generating response: {str(e)}"
                        st.error(error_msg)
                        logging.error(error_msg)
    elif media_gen_or_text_gen == "Sudo Search":
        st.sidebar.write("Sudo Search options will be displayed here.")
        num_results = st.sidebar.slider(
            "Number of search results",
            min_value=1,
            max_value=10,
            value=3,
            help="Select how many search results you want to see"
        )
        st.sidebar.write(f"Showing {num_results} search results")
        logging.info(f"Initializing Tavily search with max_results={num_results}...")


        
        # Use the official Tavily Python client
        tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
        
        if sudo_query := st.chat_input("Enter your sudo search here."):
            logging.info(f"Sudo Search query: {sudo_query}")
            st.session_state.messages.append({"role": "user", "content": sudo_query})
            with st.chat_message("user"):
                st.write(sudo_query)
            if st.session_state.logged_in:
                user_id = str(st.session_state.user_info["id"])
                add_user_message(user_id, sudo_query)
            with st.chat_message("assistant"):
                with st.spinner("Searching..."):
                    # Call the search method with max_results parameter
                    search_results = tavily_client.search(sudo_query, max_results=num_results)
                try:
                    # Expecting search_results to be a dict with a "results" key
                    results_list = search_results.get("results", [])
                    formatted_results = f"## Search Results for: *{sudo_query}*\n\n"
                    for i, result in enumerate(results_list, 1):
                        content = result.get('content', result.get('snippet', 'No content available'))
                        url = result.get('url', result.get('link', '#'))
                        formatted_results += f"### {i}.\n\n"
                        formatted_results += f"{content}\n\n"
                        formatted_results += f"*Source: [{url}]({url})*\n\n"
                        formatted_results += "---\n\n"
                    st.markdown(formatted_results)
                    st.session_state.messages.append({"role": "assistant", "content": formatted_results})
                    if st.session_state.logged_in:
                        user_id = str(st.session_state.user_info["id"])
                        add_ai_message(user_id, formatted_results)
                except Exception as e:
                    st.markdown(f"### Search Results:\n\n{search_results}")
                    logging.error(f"Error formatting search results: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": str(search_results)})
                    if st.session_state.logged_in:
                        user_id = str(st.session_state.user_info["id"])
                        add_ai_message(user_id, str(search_results))
    st.sidebar.button("Clear Chat History", on_click=handle_clear_chat_history)
    if media_gen_or_text_gen == "Agent" and 'selected_model' in locals():
        if selected_model == "Claude":
            model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"
        else:
            model_id = "cohere.command-r-plus-v1:0"
        agent_executor = initialize_agent(model_id=model_id)
    else:
        agent_executor = None
    tool_logs = []
    if media_gen_or_text_gen == "Agent" and agent_executor and (prompt := st.chat_input("What is up?")):
        logging.info(f"User prompt: {prompt}")
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        if st.session_state.logged_in:
            user_id = str(st.session_state.user_info["id"])
            add_user_message(user_id, prompt)
        search_results = search_documents(vector_store, prompt)
        search_results_content = "\n".join([doc.page_content for doc in search_results])
        agent_prompt = f"PROMPT: {prompt}\nLOCAL SEARCH RESULTS: {search_results_content}"
        if st.session_state.logged_in and selected_pack != "No Pack":
            username = st.session_state.user_info.get("username")
            pinecone_results = query_pinecone_pack(username, selected_pack, prompt)
            if pinecone_results and isinstance(pinecone_results, dict):
                try:
                    body = json.loads(pinecone_results.get("body", "{}"))
                    matches = body.get("message", {}).get("matches", [])
                    pack_texts = []
                    for match in matches:
                        if "metadata" in match and "text" in match["metadata"]:
                            pack_texts.append(match["metadata"]["text"])
                    if pack_texts:
                        pack_content = "\n".join(pack_texts)
                        agent_prompt += f"\nPINECONE PACK RESULTS: {pack_content}"
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing Pinecone results: {e}")
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            agent_response = ""
            temp_history = st.session_state.messages.copy()
            temp_history[-1]["content"] = agent_prompt
            for chunk in query_agent(agent_executor, temp_history):
                if chunk["type"] == "response":
                    agent_response += chunk["content"]
                    response_placeholder.markdown(agent_response)
                elif chunk["type"] == "tool_log":
                    tool_logs.append(chunk["content"])
                elif chunk["type"] == "error":
                    st.error(chunk["content"])
        logging.info(f"Agent response: {agent_response}")
        if agent_response:
            st.session_state.messages.append({"role": "assistant", "content": agent_response})
            if st.session_state.logged_in:
                user_id = str(st.session_state.user_info["id"])
                add_ai_message(user_id, agent_response)
    if tool_logs:
        with st.expander("Tool Usage Logs", expanded=False):
            st.write("Here are the details of the tool usage:")
            for log in tool_logs:
                st.text(log)

# Main app flow
auth_data = check_token()
if auth_data and not st.session_state.logged_in:
    token = auth_data['token']
    logging.info(f"Attempting auto-login with token from query params: {token[:10]}...")
    try:
        user_info = get_user_info(token)
        if user_info:
            st.session_state.logged_in = True
            st.session_state.access_token = token
            st.session_state.username = auth_data['username']
            st.session_state.user_id = auth_data['user_id']
            st.session_state.user_info = user_info
            load_user_chat_history()
            logging.info(f"Auto-login successful for user: {auth_data['username']}")
            st.session_state.should_save_auth = True
        else:
            logging.error("Failed to get user info with token from query params")
            clear_auth_data_from_browser()
            logging.warning("Invalid token found in cookies, cleared")
    except Exception as e:
        logging.error(f"Error during auto-login: {e}")
        clear_auth_data_from_browser()
if st.session_state.logged_in and st.session_state.get("should_save_auth", False):
    save_auth_data_to_browser()
    st.session_state.should_save_auth = False
if st.session_state.register_trigger:
    register_page()
elif st.session_state.show_login_page and not st.session_state.logged_in:
    login_page()
    if st.button("Back to Main Page"):
        st.session_state.show_login_page = False
else:
    if st.session_state.logged_in:
        access_token = st.session_state.access_token
        if access_token:
            if "user_info" not in st.session_state:
                user_info = get_user_info(access_token)
                if user_info:
                    st.session_state.user_info = user_info
                    logging.info(f"User Info: {user_info}")
                    save_auth_data_to_browser()
                    load_user_chat_history()
                else:
                    logging.warning("Failed to retrieve user info.")
                    st.session_state.logged_in = False
            else:
                if not st.session_state.messages:
                    load_user_chat_history()
    main_page()
