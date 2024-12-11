import streamlit as st
import boto3
import json
import logging
import os
from dotenv import load_dotenv
import random
import time

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

# Initialize a session using Boto3
session = boto3.Session(
    aws_access_key_id=os.getenv('ACCESS_KEY'),
    aws_secret_access_key=os.getenv('SECRET_KEY'),
    region_name=os.getenv('REGION')
)

# Create a Lambda client
lambda_client = session.client('lambda')

# Function to display the login page
def login_page():
    st.title("Login Page")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")

    if submit_button:
        logging.info("Login attempt for user: %s", username)
        
        # Define the payload for the Lambda function
        payload = {
            "action": "LOGIN_USER",
            "data": {
                "username": username,
                "password": password
            }
        }

        # Invoke the Lambda function
        try:
            response = lambda_client.invoke(
                FunctionName='sb-user-auth-sbUserAuthFunction-3StRr85VyfEC',
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            logging.info("Lambda function invoked successfully.")
        except Exception as e:
            logging.error("Error invoking Lambda function: %s", e)
            st.error("An error occurred while processing your request.")
            return

        # Read the response
        response_payload = json.loads(response['Payload'].read())
        logging.info("Received response from Lambda: %s", response_payload)

        # Check the response and update session state
        if response_payload.get('statusCode') == 200:
            st.session_state.logged_in = True
            st.session_state.access_token = json.loads(response_payload['body'])['token']
            logging.info("User %s logged in successfully.", username)
            st.success("Logged in successfully!")
            st.rerun()
        else:
            logging.warning("Invalid login attempt for user: %s", username)
            st.error("Invalid username or password")

# Function to log out the user
def logout():
    logging.info("User logged out.")
    st.session_state.logged_in = False
    st.session_state.access_token = None
    st.session_state.logout_trigger = not st.session_state.logout_trigger  # Toggle the trigger

# Function to display the main page
def main_page():
    logging.info(f"Access Token: {st.session_state.access_token}")
    st.sidebar.title("Options")

    # select box for conversation history
    options = ["New Conversation", "Option 2", "Option 3"]
    selected_option = st.sidebar.selectbox("Conversation History", options)
    st.sidebar.write(f"You selected: {selected_option}")

    # File upload for context in the sidebar
    uploaded_file = st.sidebar.file_uploader("Upload a file for context", type=["txt", "pdf", "docx"])
    if uploaded_file is not None:
        # Process the uploaded file
        file_content = uploaded_file.read()
        # You can add logic here to parse the file and extract useful information
        st.session_state.file_content = file_content
        st.sidebar.success("File uploaded successfully!")

    # Select box in the sidebar for packs
    options = ["No Pack", "Option 2", "Option 3"]
    selected_option = st.sidebar.selectbox("Connect to a Pack", options)
    st.sidebar.write(f"You selected: {selected_option}")

    # Activate voice toggle
    voice_toggle = st.sidebar.toggle("Activate Voice", value=False)

    # Microphone input under the toggle button
    if voice_toggle:
        audio_input = st.sidebar.audio_input("Record a voice message")
        if audio_input:
            st.sidebar.audio(audio_input)
    

    # Logout button in the sidebar
    st.sidebar.button("Logout", on_click=logout)

    # Streamed response emulator
    def response_generator():
        response = random.choice(
            [
                "Hello there! How can I assist you today?",
                "Hi, human! Is there anything I can help you with?",
                "Do you need help?",
            ]
        )
        for word in response.split():
            yield word + " "
            time.sleep(0.05)

    st.title("DeepQuery")

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("What is up?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            response = st.write_stream(response_generator())
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

# Display the appropriate page based on login state
if st.session_state.logged_in:
    main_page()
else:
    login_page()





#---Helper Functions---

def get_user_info(access_token):
    pass

def get_user_data(access_token):
    pass


