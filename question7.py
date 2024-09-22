import os
import re
import time
from dotenv import load_dotenv
from flask import Flask, request, jsonify
import google.generativeai as gen_ai
from PyPDF2 import PdfReader
from pymongo import MongoClient
from gtts import gTTS
import playsound
import tempfile

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")

# Configure Gemini-Pro AI model
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-pro')

# Initialize MongoDB client
client = MongoClient(MONGO_URI)

# Flask app initialization
app = Flask(__name__)

# Function to extract text from PDF
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

# Function to extract skills from resume text
def extract_skills(text):
    skill_patterns = [
        r'\bPython\b', r'\bJava\b', r'\bJavaScript\b', r'\bSQL\b', r'\bMachine Learning\b',
        r'\bData Science\b', r'\bDjango\b', r'\bReact\b', r'\bNode.js\b', r'\bHTML\b', r'\bCSS\b',
        r'\bC++\b', r'\bC#\b', r'\bRuby\b', r'\bKotlin\b', r'\bTypeScript\b', r'\bAngular\b',
        r'\bFlask\b', r'\bSpring Boot\b', r'\bAWS\b', r'\bAzure\b', r'\bGoogle Cloud\b', r'\bDocker\b',
        r'\bKubernetes\b', r'\bGit\b', r'\bJenkins\b', r'\bLinux\b', r'\bREST API\b', r'\bGraphQL\b',
        r'\bjQuery\b', r'\bNext.js\b', r'\bExpress.js\b', r'\bMongoDB\b', r'\bGraphQL\b', r'\bFlutter\b',
        r'\bReact Native\b', r'\bHadoop\b', r'\bJIRA\b', r'\bSalesforce\b', r'\bPower BI\b',
        r'\bBash\b', r'\bShell Scripting\b', r'\bBig Data\b', r'\bData Analytics\b',
        r'\bData Visualization\b', r'\bR\b', r'\bMATLAB\b', r'\bScikit-learn\b', r'\bNLTK\b', r'\bOpenCV\b',
        r'\bApache\b', r'\bFastAPI\b'
    ]
    skills_found = set()
    for pattern in skill_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            skills_found.add(pattern.replace(r'\b', ''))
    print(f"Skills extracted: {skills_found}")
    return list(skills_found)

# Function to update resume text and skills
def update_resume(file_path, person_id):
    print("Extracting text from the resume...")
    resume_text = extract_text_from_pdf(file_path)
    if resume_text.strip() == "":
        print("No text found in the resume.")
        return None, []

    print("Extracting skills from the resume text...")
    skills = extract_skills(resume_text)

    # Creating folder for the particular person inside the database
    db = client['resume_analysis']
    collection = db[person_id]
    return collection, skills

# Function to generate questions with retry and exponential backoff
def generate_questions_with_backoff(prompt, max_retries=5):
    retries = 0
    backoff_time = 2
    while retries < max_retries:
        try:
            response = model.start_chat().send_message(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e):
                print(f"Rate limit hit: {e}. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= 2
            else:
                print(f"Error generating questions: {e}")
                break
    return ""


# Function to store data into MongoDB
def store_to_mongodb(question, user_answer, model_answer, skill, is_relevant, collection, hr_question=False):
    try:
        existing_document = collection.find_one({'skill': skill})
        if existing_document:
            collection.update_one(
                {'skill': 'HR'} if hr_question else {'skill': skill},
                {'$push': {'questions': {'question': question, 'user_answer': user_answer, 'model_answer': model_answer, 'relevant': is_relevant}}}
            )
        else:
            document = {
                'skill': 'HR' if hr_question else skill,
                'questions': [{'question': question, 'user_answer': user_answer, 'model_answer': model_answer, 'relevant': is_relevant}]
            }
            collection.insert_one(document)
        print(f"Stored data for skill '{skill}' in MongoDB collection '{collection.name}'.")
    except Exception as e:
        print(f"Error storing data in MongoDB: {e}")
        
BASE_FOLDER = r'C:\Users\SPURGE\HRMANAGEMENT22'
UPLOAD_FOLDER = os.path.join(BASE_FOLDER, 'temp_file')

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/upload_resume', methods=['POST'])
def upload_resume():
    try:
        if 'resume' not in request.files:
            return jsonify({"error": "No resume file found"}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        
        person_id = request.form.get('person_id')
        if not person_id:
            return jsonify({"error": "Person ID is required"}), 400
        
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)

        # Ensure the UPLOAD_FOLDER exists
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        
        file.save(file_path)
        
        # Process the file (assuming update_resume is defined elsewhere)
        collection, skills = update_resume(file_path, person_id)
        
        os.remove(file_path)
        return jsonify({"message": "Resume processed successfully", "skills": skills}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_questions_based_on_skills(skill):
    if not skill:
        return [], [], []

    prompt = (
        f"Generate a list of specific interview questions directly related to the skill '{skill}'. "
        f"Only list clear, direct questions without any extra text."
    )

    # Generate questions using the backoff mechanism
    gemini_response_text = generate_questions_with_backoff(prompt)

    if not gemini_response_text:
        return [], [], []

    # Process and clean up the questions
    questions = [q.strip() for q in gemini_response_text.split('\n') if q.strip()]
    questions = [re.sub(r'^[\*\d+\.]+[\s\-]*', '', q).strip() for q in questions]
    questions = [q for q in questions if q and q[-1] == '?']

    # Categorize questions into easy, normal, and hard
    easy, normal, hard = categorize_questions(questions)
    return easy, normal, hard

# Function to categorize questions based on their order
def categorize_questions(questions):
    easy, normal, hard = [], [], []
    if len(questions) >= 3:
        easy = [questions[0]] 
        normal = [questions[1]] if len(questions) > 1 else []  
        hard = [questions[2]] if len(questions) > 2 else []  
    else:
        easy = questions[:1]
        normal = questions[1:2]
        hard = questions[2:3]
    return easy, normal, hard

# Function to generate questions with backoff mechanism
def generate_questions_with_backoff(prompt, max_retries=5):
    retries = 0
    backoff_time = 2
    while retries < max_retries:
        try:
            # Example call to your model; replace with actual call if necessary
            response = model.start_chat().send_message(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e):
                print(f"Rate limit hit: {e}. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= 2
            else:
                print(f"Error generating questions: {e}")
                break
    return ""

# API endpoint to generate questions based on skill
@app.route('/generate_questions', methods=['POST'])
def generate_questions_api():
    try:
        data = request.json
        skills = data.get('skills', [])

        if not skills:
            return jsonify({"error": "Skills list is required."}), 400

        # Dictionary to store questions for each skill
        questions_per_skill = {}

        for skill in skills:
            # Generate questions for each skill
            easy, normal, hard = generate_questions_based_on_skills(skill)

            # Check if each category has at least one question
            if not easy or not normal or not hard:
                print(f"Failed to generate a full set for {skill}. Easy: {easy}, Normal: {normal}, Hard: {hard}")
                return jsonify({"error": f"Failed to generate a balanced set of questions for {skill}."}), 400

            # Store the questions for each skill
            questions_per_skill[skill] = {
                "easy": easy[0] if easy else "No Easy Question Generated",
                "normal": normal[0] if normal else "No Normal Question Generated",
                "hard": hard[0] if hard else "No Hard Question Generated"
            }

        # Return the questions as JSON response
        return jsonify(questions_per_skill), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Endpoint to analyze answers and store results
@app.route('/analyze_answer', methods=['POST'])
def analyze_answer():
    try:
        data = request.json
        question = data['question']
        user_answer = data['user_answer']
        skill = data['skill']
        person_id = data['person_id']
        collection = client['resume_analysis'][person_id]
        prompt = f"Your a expert answer generator. Generate a direct answer for the following question: {question}. The answer generated should be medium and understandable."
        model_answer = model.start_chat().send_message(prompt).text.strip()
        analysis_prompt = f"Evaluate the following answer to determine if it is relevant. Question: {question} Answer: {user_answer} Is the answer relevant? Respond with 'Yes' or 'No'."
        feedback = model.start_chat().send_message(analysis_prompt).text.strip().lower()
        is_relevant = feedback == 'yes'
        store_to_mongodb(question, user_answer, model_answer, skill, is_relevant, collection)
        return jsonify({"relevant": is_relevant, "model_answer": model_answer}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to generate HR questions
@app.route('/generate_hr_questions', methods=['POST'])
def generate_hr_questions():
    try:
        prompt = "Generate a list of HR-related interview questions that evaluate communication skills, teamwork, conflict resolution, and leadership."
        response_text = generate_questions_with_backoff(prompt)
        questions = [q.strip() for q in response_text.split('\n') if q.strip() and q.endswith('?')]
        return jsonify({"hr_questions": questions}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint to calculate the overall score based on answers
@app.route('/get_overall_score', methods=['POST'])
def get_overall_score():
    try:
        person_id = request.json['person_id']
        collection = client['resume_analysis'][person_id]
        documents = list(collection.find({}))
        total_score = 0
        total_questions = 0
        for doc in documents:
            questions = doc.get('questions', [])
            for q in questions:
                if q.get('relevant') is not None:
                    total_score += int(q.get('relevant'))
                    total_questions += 1
        overall_score = (total_score / total_questions) * 100 if total_questions > 0 else 0
        return jsonify({"overall_score": overall_score}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Ensure the static directory exists
TEMP_DIR = tempfile.gettempdir()
AUDIO_FILE_PATH = os.path.join(TEMP_DIR, 'response.mp3')

@app.route('/speak_introduction', methods=['POST'])
def speak_introduction_route():
    try:
        # Ensure the request content type is JSON
        if request.content_type != 'application/json':
            return jsonify({"error": "Content-Type must be application/json"}), 415
        
        data = request.get_json()
        user_name = data.get('user_name')
        skills = data.get('skills')

        # Validate the input data
        if not user_name:
            return jsonify({"error": "User name is required"}), 400
        if not skills or not isinstance(skills, list):
            return jsonify({"error": "Skills must be a list"}), 400

        # Generate introduction text
        skills_list = ', '.join(skills)
        intro_text = (
            f"Hi {user_name}, my name is Netica, and I will be your instructor for today's test.By going through your resume, you seem well-versed in skills like {skills_list}.So let's get started with your test."
        )

        # Convert introduction text to speech
        speak(intro_text)
        
        return jsonify({"message": "Introduction spoken successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def speak(text):
    try:
        # Convert text to speech and save to the temporary path
        tts = gTTS(text=text, lang='en')
        tts.save(AUDIO_FILE_PATH)
        
        try:
            # Play the audio file
            playsound.playsound(AUDIO_FILE_PATH)
        finally:
            # Ensure the file is removed after playback
            if os.path.exists(AUDIO_FILE_PATH):
                os.remove(AUDIO_FILE_PATH)
                
    except Exception as e:
        print(f"Error speaking text: {e}")

# Run the Flask application
if __name__ == '__main__':
    app.run(debug=True)
