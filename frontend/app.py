import streamlit as st
import requests
import json
import os
import pandas as pd

# Configuration
BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Autonomous QA Agent", layout="wide")
st.markdown(
    """
    <style>
    div[data-testid="stTable"], div[data-testid="stDataFrame"] table {
        white-space: normal !important;
        word-break: break-word;
    }
    div[data-testid="stTable"] tbody td,
    div[data-testid="stTable"] th {
        white-space: normal !important;
        word-break: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🤖 Autonomous QA Agent")
st.markdown("Generate Test Cases and Selenium Scripts from Documentation")

# Sidebar for Setup
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Google Gemini API Key", type="password")
    if api_key:
        st.session_state['api_key'] = api_key
    
    st.info("Ensure the Backend API is running on port 8000.")

# Tabs
tab1, tab2, tab3 = st.tabs(["📂 Knowledge Base", "🧪 Test Case Generation", "📜 Script Generation"])

# --- Tab 1: Knowledge Base ---
with tab1:
    st.header("1. Upload Assets")
    
    uploaded_docs = st.file_uploader("Upload Support Documents (MD, TXT, JSON)", accept_multiple_files=True)
    uploaded_html = st.file_uploader("Upload Target HTML (checkout.html)", type=["html"])
    st.markdown("**Or paste the checkout HTML below** if a file is not available.")
    pasted_html = st.text_area("checkout.html Contents", height=200)
    
    if st.button("Build Knowledge Base"):
        if not uploaded_docs:
            st.error("Please upload at least one support document before building the knowledge base.")
            st.stop()
        html_payload = None
        html_content_str = None
        if uploaded_html:
            html_bytes = uploaded_html.getvalue()
            html_payload = ('files', (uploaded_html.name, html_bytes, uploaded_html.type))
            html_content_str = html_bytes.decode("utf-8")
        elif pasted_html.strip():
            html_bytes = pasted_html.encode("utf-8")
            html_payload = ('files', ('pasted_checkout.html', html_bytes, 'text/html'))
            html_content_str = pasted_html
        else:
            st.error("Please upload or paste the checkout HTML before building the knowledge base.")
            st.stop()

        files_to_send = []
        for doc in uploaded_docs:
            files_to_send.append(('files', (doc.name, doc.getvalue(), doc.type)))
        files_to_send.append(html_payload)

        if html_content_str:
            st.session_state['html_content'] = html_content_str
            st.session_state['html_name'] = html_payload[1][0]

        with st.spinner("Uploading and Ingesting..."):
            try:
                upload_response = requests.post(f"{BACKEND_URL}/upload-documents", files=files_to_send)
                if upload_response.status_code == 200:
                    build_response = requests.post(f"{BACKEND_URL}/build-knowledge-base")
                    if build_response.status_code == 200:
                        st.success(f"Knowledge Base Built! {build_response.json().get('chunks_processed')} chunks processed.")
                    else:
                        st.error(f"Build failed: {build_response.text}")
                else:
                    st.error(f"Upload failed: {upload_response.text}")
            except Exception as e:
                st.error(f"Connection error: {e}")

# --- Tab 2: Test Case Generation ---
with tab2:
    st.header("2. Generate Test Cases")
    
    query = st.text_area("Describe the tests you want to generate", value="Generate all positive and negative test cases for the discount code feature.")
    
    if st.button("Generate Test Cases"):
        headers = {}
        if 'api_key' in st.session_state:
            headers['x-api-key'] = st.session_state['api_key']
            
        with st.spinner("Analyzing Knowledge Base..."):
            try:
                response = requests.post(f"{BACKEND_URL}/generate-test-cases", json={"query": query}, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state['test_plan'] = data
                    st.success("Test Cases Generated!")
                else:
                    st.error(f"Generation failed: {response.text}")
            except Exception as e:
                st.error(f"Error: {e}")

    if 'test_plan' in st.session_state:
        test_plan = st.session_state['test_plan']
        test_cases = test_plan.get('test_cases', [])
        viewpoints = test_plan.get('test_viewpoints', [])

        if viewpoints:
            st.subheader("Test Viewpoints")
            for viewpoint in viewpoints:
                st.markdown(f"- {viewpoint}")

        st.write(f"Found {len(test_cases)} test cases:")
        if test_cases:
            df = pd.DataFrame(test_cases)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No test cases returned. Try refining your query.")

        with st.expander("View Raw JSON"):
            st.json(test_plan)

# --- Tab 3: Script Generation ---
with tab3:
    st.header("3. Generate Selenium Script")
    
    if 'test_plan' not in st.session_state:
        st.warning("Please generate test cases in Tab 2 first.")
    elif 'html_content' not in st.session_state:
        st.warning("Please upload the HTML file in Tab 1 first.")
    else:
        test_cases = st.session_state['test_plan'].get('test_cases', [])
        test_case_options = {f"{tc['test_id']}: {tc['test_scenario']}": tc for tc in test_cases}
        if not test_case_options:
            st.warning("No test cases available. Please regenerate them in Tab 2.")
            st.stop()

        selected_option = st.selectbox("Select a Test Case", list(test_case_options.keys()))
        
        if st.button("Generate Script"):
            selected_test_case = test_case_options[selected_option]
            
            headers = {}
            if 'api_key' in st.session_state:
                headers['x-api-key'] = st.session_state['api_key']
            
            with st.spinner("Generating Python Selenium Script..."):
                try:
                    payload = {
                        "test_case": selected_test_case
                    }
                    response = requests.post(f"{BACKEND_URL}/generate-script", json=payload, headers=headers)
                    
                    if response.status_code == 200:
                        script_code = response.json().get("script_code")
                        st.subheader("Generated Python Script")
                        st.code(script_code, language="python")
                        st.download_button("Download Script", script_code, file_name=f"test_{selected_test_case['test_id']}.py")
                    else:
                        st.error(f"Script generation failed: {response.text}")
                except Exception as e:
                    st.error(f"Error: {e}")
