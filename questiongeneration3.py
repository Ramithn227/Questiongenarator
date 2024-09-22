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
from flask import Flask, request, jsonify

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
            text = "".join(page.extract_text() or "" for page in pdf_reader.pages)
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
        r'\bC++\b', r'\bC#\b', r'\bRuby\b', r'\bKotlin\b', r'\bTypeScript\b', r'\bAngular\b', r'\bFlask\b',
        r'\bSpring Boot\b', r'\bAWS\b', r'\bAzure\b', r'\bGoogle Cloud\b', r'\bDocker\b', r'\bKubernetes\b',
        r'\bGit\b', r'\bJenkins\b', r'\bLinux\b', r'\bREST API\b', r'\bGraphQL\b', r'\bjQuery\b', r'\bNext.js\b',
        r'\bExpress.js\b', r'\bMongoDB\b', r'\bFlutter\b', r'\bReact Native\b', r'\bHadoop\b', r'\bJIRA\b',
        r'\bSalesforce\b', r'\bPower BI\b', r'\bBash\b', r'\bShell Scripting\b', r'\bBig Data\b', r'\bData Analytics\b',
        r'\bData Visualization\b', r'\bR\b', r'\bMATLAB\b', r'\bScikit-learn\b', r'\bNLTK\b', r'\bOpenCV\b', r'\bApache\b',
        r'\bExpress\b', r'\bFastAPI\b'
    ]
    skills_found = set()
    for pattern in skill_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            skills_found.add(pattern.replace(r'\b', ''))
    print(f"Skills extracted: {skills_found}")
    return list(skills_found)

def speak(text):
    try:
        tts = gTTS(text=text, lang='en')
        audio_file = 'temp_audio.mp3'
        tts.save(audio_file)
        playsound.playsound(audio_file)
        os.remove(audio_file)
    except Exception as e:
        print(f"Error in text-to-speech conversion: {e}")

def speak_introduction(user_name, skills):
    skills_list = ', '.join(skills)
    intro_text = (
        f"Hi {user_name}, my name is Netica, and I will be your instructor for today's Interview. "
        f"By going through your resume, you seem well-versed in skills like {skills_list}. "
        f"So let's get started with your Interview."
    )
    print(intro_text)
    speak(intro_text)

def update_resume(file_path, person_id):
    resume_text = extract_text_from_pdf(file_path)
    skills = extract_skills(resume_text)
    db = client['resume_analysis']
    collection = db[person_id]
    return collection, skills

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

def generate_followup_question(question, user_answer):
    prompt = (
        f"Generate a follow-up question based on the question: {question} and the user's answer: {user_answer}."
    )
    return generate_questions_with_backoff(prompt)

def generate_hr_question():
    hr_prompt = "Generate a relevant HR question. Consider common HR topics such as teamwork, challenges, strengths, or experience."
    return generate_questions_with_backoff(hr_prompt)

def generate_hr_followup_question(hr_question, hr_answer):
    hr_followup_prompt = (
        f"Based on the HR question: {hr_question} and the user's answer: {hr_answer}, generate a follow-up question "
        "to explore the user's response further."
    )
    return generate_questions_with_backoff(hr_followup_prompt)

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

def generate_questions_based_on_skills(skill, collection):
    primary_prompt = f"Generate a question about {skill}."
    primary_question = generate_questions_with_backoff(primary_prompt)
    print(f"Question: {primary_question}")
    speak(primary_question)
    user_answer = get_user_answer()
    is_relevant, _ = analyze_answer(primary_question, user_answer, skill, collection)

    follow_up_count = 0
    while is_relevant and follow_up_count < 2:
        follow_up_question = generate_followup_question(primary_question, user_answer)
        if follow_up_question:
            print(f"Follow-up Question: {follow_up_question}")
            speak(follow_up_question)
            user_answer = get_user_answer()
            is_relevant, _ = analyze_answer(follow_up_question, user_answer, skill, collection)
            follow_up_count += 1

def get_user_answer():
    method = input("Enter 1 to type your answer or 2 to speak: ").strip()
    if method == '1':
        return input("Your Answer: ")
    elif method == '2':
        return capture_spoken_answer()
    else:
        return input("Your Answer: ")
    
def capture_spoken_answer():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)
    try:
        return recognizer.recognize_google(audio)
    except Exception as e:
        print(f"Error capturing speech: {e}")
        return ""
    
def extract_username_from_person_id(person_id):
    match = re.match(r'^[a-zA-Z]+', person_id)
    if match:
        return match.group(0).capitalize()  
    return "User"

@app.route('/interview', methods=['POST'])
def interview_process_api():
    if 'resume' not in request.files:
        return jsonify({"error": "No resume file found"}), 400
    if 'person_id' not in request.form:
        return jsonify({"error": "No person ID provided"}), 400

    resume_file = request.files['resume']
    person_id = request.form['person_id']
    file_path = os.path.join(resume_file.filename)
    resume_file.save(file_path)

    collection, skills = update_resume(file_path, person_id)
    os.remove(file_path)

    user_name = extract_username_from_person_id(person_id)
    speak_introduction(user_name, skills)

    for skill in skills:
        generate_questions_based_on_skills(skill, collection)

    hr_question = generate_hr_question()
    print(f"HR Question: {hr_question}")
    speak(hr_question)
    user_answer = get_user_answer()
    generate_hr_followup_question(hr_question, user_answer)

    return jsonify({"status": "Interview processed successfully"}), 200

if __name__ == '__main__':
    app.run(debug=True)
