import os
from dotenv import load_dotenv
import streamlit as st
from logger_utils import logger, log_operation
from src.chat_session import ChatSession, ChatSessionManager
from datetime import datetime
from DroolsLLMAgent_updated import DroolsLLMAgent


# Load environment variables
logger.info("Loading environment variables in RuleAgent_app.py...")
load_dotenv()

# Log environment status
logger.debug("Environment check - OPENAI_API_KEY exists: %s", "Yes" if os.getenv("OPENAI_API_KEY") else "No")

# Initialize session manager
if 'session_manager' not in st.session_state:
    st.session_state.session_manager = ChatSessionManager()

# Initialize the Drools LLM Agent in session state
if 'agent' not in st.session_state:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        error_msg = "OPENAI_API_KEY environment variable not set"
        logger.error(error_msg)
        st.error(error_msg)
        st.stop()
    
    logger.info("Initializing DroolsLLMAgent")
    try:
        # Get Java directory from environment variable
        java_dir = os.getenv("JAVA_DIR", "")
        
        # Get rules directory from environment variable or use default
        rules_dir = os.getenv("RULES_DIR", os.path.join(os.getcwd(), "rules"))
        
        # Initialize agent with directories
        st.session_state.agent = DroolsLLMAgent(
            api_key=openai_key,
            rules_dir=rules_dir,
            java_dir=java_dir
        )
        logger.info("DroolsLLMAgent initialized successfully")
        log_operation('agent_initialization', {'status': 'success'})
    except Exception as e:
        error_msg = f"Failed to initialize DroolsLLMAgent: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_operation('agent_initialization', {'status': 'failed'}, error=e)
        st.error(error_msg)
        st.stop()

def load_chat_session(session: ChatSession):
    """Load a chat session and sync it with the LLM agent's context."""
    st.session_state.current_session = session
    # Reset agent's message history and add all messages from the session
    st.session_state.agent.messages = []
    for msg in session.messages:
        st.session_state.agent.messages.append(msg)

# Initialize or load chat session
if 'current_session' not in st.session_state:
    st.session_state.current_session = ChatSession()

# Sidebar for session management
with st.sidebar:
    st.title("Chat Sessions")
    
    # New chat button
    if st.button("New Chat"):
        st.session_state.current_session = ChatSession()
        # Reset agent's message history
        st.session_state.agent.messages = []
        st.rerun()
    
    # List existing sessions
    st.subheader("Previous Sessions")
    sessions = st.session_state.session_manager.list_sessions()
    
    for session in sessions:
        created_at = datetime.fromisoformat(session["created_at"]).strftime("%Y-%m-%d %H:%M")
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button(f"📝 {created_at} ({session['message_count']} messages)", key=f"load_{session['session_id']}"):
                loaded_session = st.session_state.session_manager.load_session(session["session_id"])
                if loaded_session:
                    load_chat_session(loaded_session)
                    st.rerun()
        with col2:
            if st.button("🗑️", key=f"delete_{session['session_id']}"):
                st.session_state.session_manager.delete_session(session["session_id"])
                st.rerun()

# Main chat interface
st.title("🤖 Drools Rule Assistant")
st.markdown("Interact with the agent to add, search, edit or delete Drools rules.")

# Chat input
user_input = st.chat_input("Type your message here...")
if user_input:
    logger.info(f"Received user input: {user_input[:100]}...")  # Log first 100 chars
    
    # Add message to current session
    st.session_state.current_session.add_message("user", user_input)
    
    # Get assistant response with logging
    try:
        logger.debug("Processing user message with DroolsLLMAgent...")
        assistant_reply = st.session_state.agent.handle_user_message(user_input)
        
        # Log successful interaction
        log_operation('agent_interaction', {
            'user_input': user_input,
            'reply_length': len(assistant_reply) if assistant_reply else 0
        })
        
        # Add assistant reply to session
        st.session_state.current_session.add_message("assistant", assistant_reply)
        
        # Save session after each interaction
        st.session_state.session_manager.save_session(st.session_state.current_session)
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_operation('agent_interaction', {'user_input': user_input}, error=e)
        st.error(f"🔴 {error_msg}")

# Display chat history
for msg in st.session_state.current_session.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        st.chat_message("assistant").write(msg["content"])
