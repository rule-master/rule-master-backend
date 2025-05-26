import os
from dotenv import load_dotenv
import streamlit as st
# from DroolsLLMAgent import DroolsLLMAgent
from logger_utils import logger, log_operation

# Load environment variables
logger.info("Loading environment variables in RuleAgent_app.py...")
load_dotenv()

# Log environment status
logger.debug("Environment check - OPENAI_API_KEY exists: %s", "Yes" if os.getenv("OPENAI_API_KEY") else "No")
from DroolsLLMAgent_updated import DroolsLLMAgent

# Initialize the Drools LLM Agent in session state
# if 'agent' not in st.session_state:
#     openai_key = os.getenv("OPENAI_API_KEY")
#     if not openai_key:
#         st.error("Please set the OPENAI_API_KEY environment variable.")
#         st.stop()
#     st.session_state.agent = DroolsLLMAgent(api_key=openai_key)

if 'agent' not in st.session_state:
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        error_msg = "OPENAI_API_KEY environment variable not set"
        logger.error(error_msg)
        st.error(error_msg)
        st.stop()
    
    logger.info("Initializing DroolsLLMAgent")
    try:
        st.session_state.agent = DroolsLLMAgent(api_key=openai_key)
        logger.info("DroolsLLMAgent initialized successfully")
        log_operation('agent_initialization', {'status': 'success'})
    except Exception as e:
        error_msg = f"Failed to initialize DroolsLLMAgent: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_operation('agent_initialization', {'status': 'failed'}, error=e)
        st.error(error_msg)
        st.stop()
    
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

# Initialize chat history in session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
    logger.info("Initialized new chat session")
    log_operation('session_initialization')

st.title("🤖 Drools Rule Assistant")
st.markdown("Interact with the agent to add, search, edit or delete Drools rules.")

# Chat input
user_input = st.chat_input("Type your message here...")
if user_input:
    logger.info(f"Received user input: {user_input[:100]}...")  # Log first 100 chars
    
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Get assistant response with logging
    try:
        logger.debug("Processing user message with DroolsLLMAgent...")
        assistant_reply = st.session_state.agent.handle_user_message(user_input)
        
        # Log successful interaction
        log_operation('agent_interaction', {
            'user_input': user_input,
            'reply_length': len(assistant_reply) if assistant_reply else 0
        })
        
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        
    except Exception as e:
        error_msg = f"Error processing message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        log_operation('agent_interaction', {'user_input': user_input}, error=e)
        st.error(f"🔴 {error_msg}")

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        st.chat_message("assistant").write(msg["content"])
