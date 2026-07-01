import streamlit as st
import streamlit.components.v1 as components
import os

def render():
    html_path = os.path.join(os.path.dirname(__file__), "..", "resource_list.html")
    
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        components.html(html_content, height=900, scrolling=True)
    else:
        st.error("resource_list.html not found. Make sure it's in the project root folder.")
