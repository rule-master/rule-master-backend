import streamlit as st
from restaurant_assistant import handle_user_message
from logger_utils import logger, log_operation

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
    logger.info("Initialized new chat session")
if 'last_data' not in st.session_state:
    st.session_state.last_data = None

st.set_page_config(page_title="Restaurant Staffing Chatbot")
st.title("🍽️ Restaurant Staffing Assistant")

# Input box for new user message
user_input = st.chat_input("Type your message here...")
if user_input:
    logger.info(f"Received user input: {user_input[:100]}...")  # Log first 100 chars
    
    # Store user message
    st.session_state.messages.append({'role': 'user', 'content': user_input})

    # Handle user message with logging
    try:
        logger.debug("Processing user message...")
        result = handle_user_message(user_input)
        
        # Log the operation
        log_operation('chat_interaction', {
            'user_input': user_input,
            'result_status': result.get('status'),
            'has_data': bool(result.get('data'))
        })
        
    except Exception as e:
        error_msg = f"Error in handle_user_message: {str(e)}"
        logger.error(error_msg, exc_info=True)
        st.error(f"🔴 {error_msg}")
        log_operation('chat_interaction', {'user_input': user_input}, error=e)
        raise

    # Show the raw result for inspection in debug mode
    logger.debug(f"Chat result: {result}")
    st.write("🔧 Debug result:", result)

    assistant_text = result['assistant']
    # Store assistant reply
    st.session_state.messages.append({'role': 'assistant', 'content': assistant_text})
    
    # If complete, save structured data
    if result.get('status') == 'complete':
        st.session_state.last_data = result.get('data')
        logger.info("Collected complete restaurant data")
        log_operation('data_collection', {'collected_data': result.get('data')})

# Display chat history
for msg in st.session_state.messages:
    st.chat_message(msg['role']).write(msg['content'])

# Show collected data if available
if st.session_state.last_data is not None:
    st.markdown("---")
    st.subheader("✅ Collected Restaurant Data")
    st.json(st.session_state.last_data)

# Reset conversation button
if st.button("🔄 Reset Conversation"):
    logger.info("Resetting conversation")
    st.session_state.messages = []
    st.session_state.last_data = None
    log_operation('reset_conversation')
    st.experimental_rerun()
