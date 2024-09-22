import os
import re
import time
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as gen_ai
from PyPDF2 import PdfReader
from pymongo import MongoClient
from gtts import gTTS  # Google Text-to-Speech
import playsound  # To play the generated audio

# Environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")  # MongoDB connection URI from environment variables

# Gemini-Pro AI model
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-pro')

resume_texts = []
skills = []
questions = []

# MongoDB 
client = MongoClient(MONGO_URI)

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
    try:
        # Simple skill extraction based on patterns or keywords
        skill_patterns = [
            r'\bPython\b', r'\bJava\b', r'\bJavaScript\b', r'\bSQL\b', r'\bMachine Learning\b',
            r'\bData Science\b', r'\bDjango\b', r'\bReact\b', r'\bNode.js\b', r'\bHTML\b', r'\bCSS\b'
        ]
        skills_found = set()
        for pattern in skill_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                skills_found.add(pattern.replace(r'\b', ''))
        
        print(f"Skills extracted: {skills_found}")
        return list(skills_found)
    except Exception as e:
        print(f"Error extracting skills: {e}")
        return []

# Update resume texts and skills
def update_resume(file_path, person_id):
    global resume_texts, skills
    print("Extracting text from the resume...")
    resume_text = extract_text_from_pdf(file_path)
    resume_texts = [resume_text]
    
    if resume_text.strip() == "":
        print("No text found in the resume.")
        return

    print("Extracting skills from the resume text...")
    skills = extract_skills(resume_text)
    # Creating folder for the particular person inside the database
    db = client['resume_analysis']  
    collection = db[person_id]
    return collection

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

# Function to generate an analysis prompt for evaluating answers
def generate_analysis_prompt(question, answer):
    return (
        f"Evaluate the following answer to determine if it is relevant to the question provided."
        f"Question: {question}\n"
        f"Answer: {answer}\n"
        f"Is the answer relevant to the question? Respond with 'Yes' if it is relevant, otherwise respond with 'No'."
    )

# Function to analyze the answer and store the result
def analyze_answer(question, user_answer, skill, collection):
    # Generate the model's answer with an example
    prompt = (
        f"Generate a short and direct answer for the following question: {question}. "
        f"Include only one answer and provide an example related to that answer."
    )
    try:
        model_answer = model.start_chat().send_message(prompt).text.strip()
        print(f"Model generated answer: {model_answer}")

        # Generate feedback on user's answer
        analysis_prompt = generate_analysis_prompt(question, user_answer)
        response = model.start_chat().send_message(analysis_prompt)
        feedback = response.text.strip().lower()
        print(f"Model response: {feedback}")

        # Check if the response is either 'yes' or 'no'
        is_relevant = feedback == 'yes'
        store_to_mongodb(question, user_answer, model_answer, skill, is_relevant, collection)
        return is_relevant, model_answer
    except Exception as e:
        print(f"Error analyzing answer: {e}")
        return False, ""

# Function to store data into MongoDB
def store_to_mongodb(question, user_answer, model_answer, skill, is_relevant, collection):
    try:
        document = {
            'skill': skill,
            'question': question,
            'user_answer': user_answer,
            'model_answer': model_answer,
            'relevant': is_relevant
        }
        collection.insert_one(document)
        print(f"Stored question, user answer, model answer, and relevance for skill '{skill}' into MongoDB collection '{collection.name}'.")
    except Exception as e:
        print(f"Error storing data into MongoDB: {e}")

# Function to categorize questions into easy, normal, and hard levels
def categorize_questions(questions):
    # Mock categorization: Splitting questions into easy, normal, and hard
    easy, normal, hard = [], [], []
    if len(questions) >= 3:
        easy = [questions[0]]  # First question as easy
        normal = [questions[1]] if len(questions) > 1 else []  # Second question as normal
        hard = [questions[2]] if len(questions) > 2 else []  # Third question as hard
    else:
        # If there are fewer questions, adjust categorization
        easy = questions[:1]
        normal = questions[1:2]
        hard = questions[2:3]
    return easy, normal, hard

# Function to generate questions based on skills with categorization
def generate_questions_based_on_skills(skill):
    if not skills:
        return "No skills found in the resume."

    prompt = (
        f"Generate a list of specific interview questions directly related to the skill '{skill}'. "
        f"Only list clear, direct questions without any extra text."
    )

    gemini_response_text = generate_questions_with_backoff(prompt)

    if not gemini_response_text:
        return [], [], []

    questions = [q.strip() for q in gemini_response_text.split('\n') if q.strip() and q.strip()[-1] == '?']
    
    easy, normal, hard = categorize_questions(questions)
    return easy, normal, hard

# Function to validate if the response is a direct question
def is_valid_question(question):
    unwanted_patterns = ['Interview Questions', 'Technical Skills', 'Summary:', '**']
    for pattern in unwanted_patterns:
        if pattern.lower() in question.lower():
            return False
    return True

# Function to generate an overall score based on the relevance of answers
def generate_overall_score(collection):
    try:
        # Retrieve data from MongoDB
        data = list(collection.find({}, {'_id': 0, 'relevant': 1}))
        df = pd.DataFrame(data)

        # Check if there's data to analyze
        if df.empty:
            print("No data available to generate a score.")
            return

        # Count relevant and non-relevant answers
        total_answers = len(df)
        relevant_answers = df['relevant'].sum()  

        # Calculate the relevance ratio
        relevance_ratio = relevant_answers / total_answers

        # Scale the ratio to a score from 1 to 10
        score = max(0, min(10, round(relevance_ratio * 10)))  

        print(f"\nOverall Relevance Score: {score}/10")

    except Exception as e:
        print(f"Error generating overall score: {e}")

# Function to generate speech from text
def speak(text):
    try:
        tts = gTTS(text=text, lang='en')
        audio_file = "question.mp3"
        tts.save(audio_file)
        playsound.playsound(audio_file)
        os.remove(audio_file)  # Remove the audio file after playing
    except Exception as e:
        print(f"Error during TTS: {e}")

# Main function to run the application
def main():
    person_id = input("Enter the unique identifier for the person (e.g., name or ID): ")
    if not person_id:
        print("Invalid identifier. Please provide a unique identifier for the person.")
        return

    file_path = input("Enter the path of the resume (PDF format): ")
    if not os.path.isfile(file_path):
        print("Invalid file path. Please provide a valid path to the resume.")
        return

    collection = update_resume(file_path, person_id)
    if collection is None:
        return

    for skill in skills:
        easy, normal, hard = generate_questions_based_on_skills(skill)

        questions_dict = {
            "Easy": easy,
            "Normal": normal,
            "Hard": hard
        }

        print(f"\nGenerating questions for the skill: {skill}")
        
        # Loop through the questions by level and process them
        for level, questions in questions_dict.items():
            for question in questions:
                if is_valid_question(question):
                    print(f"\nLevel: {level} | Question: {question}")
                    speak(question)  # Read the question aloud

                    user_answer = input(f"\nYour Answer: ")
                    is_relevant, model_answer = analyze_answer(question, user_answer, skill, collection)

                    if not is_relevant:
                        if level == "Easy":
                            print(f"Skipping to the next question for skill '{skill}' due to irrelevant answer.")
                            break
                        elif level == "Normal":
                            print("Skipping to the next skill question due to mistake in normal level.")
                            break

    generate_overall_score(collection)

if __name__ == "__main__":
    main()
