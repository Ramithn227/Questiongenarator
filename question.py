import os
import re
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as gen_ai
from PyPDF2 import PdfReader

# Load environment variables
load_dotenv()

# Configure Streamlit page settings
st.set_page_config(
    page_title="Resume Skill Question Generator",
    page_icon=":brain:",  # Favicon emoji
    layout="centered",  # Page layout option
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Set up Google Gemini-Pro AI model
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-pro')

# Initialize storage for resume content and skill set
resume_texts = []
skills = []

# Function to extract text from PDF resume
def extract_text_from_pdf(file):
    pdf_reader = PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

# Function to extract skills from resume text
def extract_skills(text):
    # Simple skill extraction based on patterns or keywords
    
    skill_patterns = [
        r'\bPython\b', r'\bJava\b', r'\bJavaScript\b', r'\bSQL\b', r'\bMachine Learning\b',
        r'\bData Science\b', r'\bDjango\b', r'\bReact\b', r'\bNode.js\b', r'\bHTML\b', r'\bCSS\b'
    ]
    skills_found = set()
    for pattern in skill_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            skills_found.add(pattern.replace(r'\b', ''))
    return list(skills_found)

# Function to update resume texts and skills
def update_resume(file):
    global resume_texts, skills
    resume_text = extract_text_from_pdf(file)
    resume_texts = [resume_text]
    skills = extract_skills(resume_text)

# Function to generate questions based on skills
def generate_questions_based_on_skills():
    if not skills:
        return "No skills found in the resume."
    
    # Prepare prompt to generate questions
    prompt = "Generate a list of questions based on the following skills:\n\n"
    prompt += "Skills:\n" + ', '.join(skills)
    
    # Generate questions using Gemini-Pro model
    gemini_response = model.start_chat().send_message(prompt)
    
    # Return generated questions
    return gemini_response.text

# Display the page title
st.title("Resume Skill Question Generator")

# File uploader for resume
uploaded_file = st.file_uploader("Upload your resume (PDF format)", type="pdf")
if uploaded_file:
    update_resume(uploaded_file)
    st.success("Resume uploaded successfully!")

# Button to generate questions based on skills
if st.button("Generate Questions Based on Skills"):
    if not skills:
        st.warning("Please upload a resume first or no skills found.")
    else:
        # Generate and display questions based on extracted skills
        generated_questions = generate_questions_based_on_skills()
        st.subheader("Generated Questions Based on Skills:")
        st.markdown(generated_questions)
