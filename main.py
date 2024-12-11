import streamlit as st
import boto3
import json
import logging
import os
from dotenv import load_dotenv

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
    st.title("Main Page")
    st.write("Welcome to the main page!")
    st.write(f"Access Token: {st.session_state.access_token}")
    st.sidebar.title("Navigation")
    st.sidebar.button("Logout", on_click=logout)

# Display the appropriate page based on login state
if st.session_state.logged_in:
    main_page()
else:
    login_page()
