import streamlit as st
import json
import logging
import os
import requests

# --- 1) ENSURE CONFIGURATION IS LOADED ---
# API URL - use environment variable or default to localhost
API_URL = os.getenv('API_URL', 'http://localhost:5000')

def check_token():
    """Check for authentication token in cookies via query parameters.
    This function is used to maintain login state across page refreshes.
    Returns a dict with token, username, and user_id if found, None otherwise."""
    try:
        # Get query parameters (populated by our JavaScript code)
        query_params = st.query_params
        
        # Check if we have auth info in query params (set by JavaScript)
        if 'token' in query_params:
            token = query_params.get('token')
            username = query_params.get('username')
            user_id = query_params.get('user_id')
            
            logging.info(f"Query params: token={token[:10]}... (truncated), username={username}, user_id={user_id}")
            
            if token:
                logging.info(f"Found token in query parameters for user: {username}")
                return {
                    'token': token,
                    'username': username,
                    'user_id': user_id
                }
        return None
    except Exception as e:
        logging.error(f"Error checking token: {e}")
        return None

# --- 3) DEFINE LOGIN PAGE ---
def login_page():
    st.title("Login Page")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit_button = st.form_submit_button("Login")
    
    # Create a button to navigate to the registration page if register_trigger exists
    if "register_trigger" in st.session_state:
        st.button("Don't have an account? Register here", on_click=register_trigger)

    if submit_button:
        logging.info("Login attempt for user: %s", username)
        
        try:
            # Make a request to the API for login
            response = requests.post(
                f'{API_URL}/login',
                json={
                    'username': username,
                    'password': password
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                st.session_state.logged_in = True
                st.session_state.access_token = data['access_token']
                st.session_state.username = username
                st.session_state.user_id = data['user_id']
                
                # Get user info and set it in session state
                user_info = get_user_info(data['access_token'])
                if user_info:
                    st.session_state.user_info = user_info
                    logging.info(f"User info retrieved: {user_info}")
                
                # Flag that we should save auth data to browser storage
                st.session_state.should_save_auth = True
                
                # Hide the login page after successful login
                st.session_state.show_login_page = False
                logging.info("User %s logged in successfully.", username)
                st.success("Logged in successfully!")
            else:
                logging.warning("Invalid login attempt for user: %s", username)
                st.error("Invalid username or password")
                
        except Exception as e:
            logging.error("Error during login: %s", e)
            st.error("An error occurred while processing your request.")

# --- 4) DEFINE LOGOUT ---
def logout():
    logging.info("User logged out.")
    st.session_state.logged_in = False
    st.session_state.access_token = None
    st.session_state.username = None
    if "user_id" in st.session_state:
        st.session_state.user_id = None
    if "user_info" in st.session_state:
        del st.session_state.user_info
    st.session_state.logout_trigger = not st.session_state.logout_trigger  # Toggle the trigger

# --- 5) GET USER INFO ---
def get_user_info(access_token):
    try:
        # Make a request to the API to get user info
        headers = {'Authorization': f'Bearer {access_token}'}
        logging.info(f"Requesting user info from {API_URL}/user")
        response = requests.get(f'{API_URL}/user', headers=headers)
        
        logging.info(f"User info response status: {response.status_code}")
        
        if response.status_code == 200:
            user_info = response.json()
            logging.info(f"User info retrieved successfully: {user_info}")
            
            # Make sure we have the required fields in user_info
            if 'id' not in user_info and 'user_id' in user_info:
                user_info['id'] = user_info['user_id']
                
            return user_info
        else:
            logging.warning(f"Failed to retrieve user info. Status code: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        logging.error(f"Error retrieving user info: {e}")
        return None

# --- 6) REGISTER FUNCTIONS ---
def register_trigger():
    """Toggle the registration page display"""
    if "register_trigger" in st.session_state:
        st.session_state.register_trigger = True
    # For backward compatibility
    st.session_state.show_login_page = True

def back_to_login():
    """Go back to login page from registration"""
    if "register_trigger" in st.session_state:
        st.session_state.register_trigger = False

def register_page():
    """Display registration page"""
    st.title("Register Page")
    
    # Add a button to go back to login
    st.button("Back to Login", on_click=back_to_login)
    
    with st.form("register_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submit_button = st.form_submit_button("Register")

        if submit_button:
            if not username or not email or not password:
                st.error("Please fill in all required fields")
            elif password != confirm_password:
                st.error("Passwords do not match")
            else:
                try:
                    # Make a request to the API to register a new user
                    response = requests.post(
                        f'{API_URL}/register',
                        json={
                            'username': username,
                            'email': email,
                            'password': password
                        }
                    )
                    
                    if response.status_code == 201:
                        st.success("Registration successful! You can now log in.")
                        # Go back to login page after successful registration
                        if "register_trigger" in st.session_state:
                            st.session_state.register_trigger = False
                        # No rerun needed - success message will display and page will rerun automatically
                    elif response.status_code == 409:
                        data = response.json()
                        st.error(f"Registration failed: {data.get('message', 'Username or email already exists')}")
                    else:
                        st.error(f"Registration failed: {response.status_code}")
                        
                except Exception as e:
                    logging.error("Error during registration: %s", e)
                    st.error("An error occurred during registration. Please try again later.")
