import streamlit as st
from restaurant_assistant import handle_user_message

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'last_data' not in st.session_state:
    st.session_state.last_data = None

st.set_page_config(page_title="Restaurant Staffing Chatbot")
st.title("🍽️ Restaurant Staffing Assistant")

# Input box for new user message
user_input = st.chat_input("Type your message here...")
if user_input:
    # Store user message
    st.session_state.messages.append({'role': 'user', 'content': user_input})
    # Process through our assistant logic
    result = handle_user_message(user_input)
    assistant_text = result['assistant']
    # Store assistant reply
    st.session_state.messages.append({'role': 'assistant', 'content': assistant_text})
    # If complete, save structured data
    if result.get('status') == 'complete':
        st.session_state.last_data = result.get('data')

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
    st.session_state.messages = []
    st.session_state.last_data = None
    st.experimental_rerun()