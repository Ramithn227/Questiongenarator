from flask import Flask, request, jsonify
import os
import re
import time
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as gen_ai
from PyPDF2 import PdfReader
from pymongo import MongoClient
from gtts import gTTS
import playsound
import speech_recognition as sr

# Environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Gemini-Pro AI model
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-pro')

# MongoDB
client = MongoClient(MONGO_URI)

app = Flask(__name__)

# Extract text from resume
def extract_text_from_pdf(file_path):
    try:
        with open(file_path, "rb") as file:
            pdf_reader = PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text() or ""
                text += page_text
            print("Text successfully extracted from the PDF.")
            return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

# Extract skills from resume text
def extract_skills(text):
    skill_patterns = [
        r'\bPython\b', r'\bJava\b', r'\bJavaScript\b', r'\bSQL\b', r'\bMachine Learning\b',
        r'\bData Science\b', r'\bDjango\b', r'\bReact\b', r'\bNode.js\b', r'\bHTML\b', r'\bCSS\b',
        # Add more skill patterns as needed
    ]
    skills_found = set()
    for pattern in skill_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            skills_found.add(pattern.replace(r'\b', ''))
    print(f"Skills extracted: {skills_found}")
    return list(skills_found)

# Text-to-Speech conversion
def speak(text):
    try:
        tts = gTTS(text=text, lang='en')
        audio_file = 'temp_audio.mp3'
        tts.save(audio_file)
        playsound.playsound(audio_file)
        os.remove(audio_file)
    except Exception as e:
        print(f"Error in text-to-speech conversion: {e}")

# Update resume texts and skills
def update_resume(file_path, person_id):
    resume_text = extract_text_from_pdf(file_path)
    skills = extract_skills(resume_text)
    db = client['resume_analysis']
    collection = db[person_id]
    return collection, skills

# Generate questions with retry and backoff
def generate_questions_with_backoff(prompt, max_retries=5):
    retries = 0
    backoff_time = 2
    while retries < max_retries:
        try:
            response = model.start_chat().send_message(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e):
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= 2
            else:
                break
    return ""

# Analyze the user's answer
def analyze_answer(question, user_answer, skill, collection):
    prompt = (
        f"Generate a concise answer for the following question: {question}. "
        f"Include an example to make the answer understandable."
    )
    model_answer = generate_questions_with_backoff(prompt)
    analysis_prompt = (
        f"Evaluate the user's answer: {user_answer} to the question: {question}. "
        "Respond with 'Yes' if the answer is relevant, otherwise respond with 'No'."
    )
    feedback = generate_questions_with_backoff(analysis_prompt).lower()
    is_relevant = feedback == 'yes'
    store_to_mongodb(question, user_answer, model_answer, skill, is_relevant, collection)
    return is_relevant, model_answer

# Store data in MongoDB
def store_to_mongodb(question, user_answer, model_answer, skill, is_relevant, collection):
    document = {
        'skill': skill,
        'questions': [{
            'question': question,
            'user_answer': user_answer,
            'model_answer': model_answer,
            'relevant': is_relevant
        }]
    }
    collection.insert_one(document)
    print(f"Stored data for skill '{skill}'.")

# Generate and ask questions based on skills
def generate_questions_based_on_skills(skill, collection):
    primary_prompt = f"Generate a question about {skill}."
    primary_question = generate_questions_with_backoff(primary_prompt)
    print(f"Skill Question: {primary_question}")
    # For the sake of the API, we'll skip speech interaction
    return primary_question

# Main route to start the interview
@app.route('/start-interview', methods=['POST'])
def start_interview():
    try:
        data = request.json
        file_path = data.get('file_path')
        person_id = data.get('person_id')

        if not file_path or not person_id:
            return jsonify({"error": "Missing file path or person ID"}), 400

        collection, skills = update_resume(file_path, person_id)
        user_name = extract_username_from_person_id(person_id)

        speak_introduction(user_name, skills)
        
        interview_results = {"skills": skills, "questions": []}

        # Ask skill-based questions first
        for skill in skills:
            question = generate_questions_based_on_skills(skill, collection)
            interview_results["questions"].append({"skill": skill, "question": question})
        
        return jsonify({"message": "Interview completed successfully.", "results": interview_results}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Utility to extract username from person_id
def extract_username_from_person_id(person_id):
    match = re.match(r'^[a-zA-Z]+', person_id)
    if match:
        return match.group(0).capitalize()  # Capitalize the username
    return "User"

# Introduction speech
def speak_introduction(user_name, skills):
    skills_list = ', '.join(skills)
    intro_text = (
        f"Hi {user_name}, my name is Netica, and I will be your instructor for today's test. "
        f"By going through your resume, you seem well-versed in skills like {skills_list}. "
        f"So let's get started with your test."
    )
    print(intro_text)
    speak(intro_text)

if __name__ == "__main__":
    app.run(debug=True)
