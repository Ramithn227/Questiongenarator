import os
import re
import time
from dotenv import load_dotenv
import google.generativeai as gen_ai
from PyPDF2 import PdfReader
from pymongo import MongoClient


# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Set up Google Gemini-Pro AI model
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-pro')

# Initialize storage for resume content and skill set
resume_texts = []
skills = []
questions = []  



# Function to extract text from PDF resume
def extract_text_from_pdf(file_path):
    try:
        with open(file_path, "rb") as file:
            pdf_reader = PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text() or ""  # Handle NoneType if text extraction fails
                text += page_text
            print("Text successfully extracted from the PDF.")
            return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""

# Function to extract skills from resume text
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

# Function to update resume texts and skills
def update_resume(file_path):
    global resume_texts, skills
    print("Extracting text from the resume...")
    resume_text = extract_text_from_pdf(file_path)
    resume_texts = [resume_text]
    
    if resume_text.strip() == "":
        print("No text found in the resume.")
        return

    print("Extracting skills from the resume text...")
    skills = extract_skills(resume_text)

# Function to generate questions based on skills with retry and exponential backoff
def generate_questions_with_backoff(prompt, max_retries=5):
    retries = 0
    backoff_time = 2  # Starting backoff time in seconds
    while retries < max_retries:
        try:
            response = model.start_chat().send_message(prompt)
            return response.text
        except Exception as e:
            if "429" in str(e):
                print(f"Rate limit hit: {e}. Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= 2  # Double the wait time for the next retry
            else:
                print(f"Error generating questions: {e}")
                break
    return ""

# Function to generate an analysis prompt for evaluating answers
def generate_analysis_prompt(question, answer):
    return (
        f"Evaluate the following answer to determine if it is relevant to the question provided. "
        f"Question: {question}\n"
        f"Answer: {answer}\n"
        f"Is the answer relevant to the question? Respond with 'Yes' if it is relevant, otherwise respond with 'No'."
    )

# Function to analyze the answer
def analyze_answer(question, answer):
    prompt = generate_analysis_prompt(question, answer)
    try:
        response = model.start_chat().send_message(prompt)
        feedback = response.text.strip().lower()
        print(f"Model response: {feedback}")  # Log the model's response

        # Check if the response is either 'yes' or 'no'
        if feedback in ['yes', 'no']:
            return feedback == 'yes'
        else:
            print("Unexpected response format. Expected 'Yes' or 'No'.")
            return False

    except Exception as e:
        print(f"Error analyzing answer: {e}")
        return False

# Function to generate questions based on skills
def generate_questions_based_on_skills(skill):
    global questions
    if not skills:
        return "No skills found in the resume."

    # Prepare prompt to generate specific interview questions based on a skill
    prompt = (
        f"Generate a list of specific interview questions directly related to the skill '{skill}'. "
        f"Do not include any extra text, headings, or phrases like 'Interview Questions'. Only list clear, direct questions."
        f"Ensure that the questions are listed without any numbering, headings, or extra text. "
        f"While providing or generating the question do not provide any numbering to the questions."
        f"I don't need any line also I just need the question without any prefixes with numbers."
    )

    gemini_response_text = generate_questions_with_backoff(prompt)

    if not gemini_response_text:
        return []

    # Filter responses to include only valid, clean questions
    questions = [q.strip() for q in gemini_response_text.split('\n') if q.strip() and q.strip()[-1] == '?']
    return questions

# Function to validate if the response is a direct question
def is_valid_question(question):
    # Filter out any responses that contain unwanted patterns or headers
    unwanted_patterns = ['Interview Questions', 'Technical Skills', 'Summary:', '**']
    for pattern in unwanted_patterns:
        if pattern.lower() in question.lower():
            return False
    return True

# Main function to run the application
def main():
    file_path = input("Enter the path of your resume (PDF format): ")
    if not os.path.isfile(file_path):
        print("Invalid file path. Please provide a valid path to a PDF file.")
        return

    # Update resume and extract skills
    update_resume(file_path)
    if not skills:
        print("No skills found in the resume.")
        return

    print("\nSkills extracted from the resume:", ', '.join(skills))

    all_answers = []

    # Generate and filter questions based on each extracted skill
    for skill in skills:
        print(f"\nGenerating questions for skill: {skill}")
        generated_questions = generate_questions_based_on_skills(skill)

        if isinstance(generated_questions, str):
            print(generated_questions)  # Output the message if no questions were generated
            continue

        # Display only valid questions
        filtered_questions = [q for q in generated_questions if is_valid_question(q)]
        if not filtered_questions:
            print(f"No valid questions generated for {skill}.")
            continue

        # Flag to check if at least one question was relevant
        skill_relevant = False  

        for i, question in enumerate(filtered_questions):
            print(f"\nQuestion {i + 1}: {question}")
            answer = input(f"Your Answer {i + 1}: ")

            # Analyze the answer and decide whether to proceed
            if analyze_answer(question, answer):
                all_answers.append((question, answer))
                store_to_mongodb(question, answer, skill)
                skill_relevant = True  # Mark skill as relevant
                continue 
            else:
                print("Answer was not relevant. Moving to next skill set...")
                skill_relevant = False
                break  # Exit current question loop and move to the next skill set

        # Skip to next skill if no relevant answers for the current skill
        if not skill_relevant:
            print(f"No relevant answers for skill: {skill}. Moving to next skill set...")

    # Final Summary of all questions and answers
    print("\nAll Questions and Answers:")
    for i, (q, a) in enumerate(all_answers, start=1):
        print(f"\nQuestion {i}: {q}")
        print(f"Your Answer {i}: {a}")

    print("\nThank you for your responses! we will get through you later.")
    
    
    
MONGO_URI = os.getenv("MONGO_URI")  # MongoDB connection URI from environment variables
client = MongoClient(MONGO_URI)
db = client['resume_analysis']  # Name of the database
collection = db['questions_answers']
    


MONGO_URI = os.getenv("MONGO_URI")  # MongoDB connection URI from environment variables
client = MongoClient(MONGO_URI)
db = client['resume_analysis']  # Name of the database
collection = db['questions_answers']


def store_to_mongodb(question, answer, skill):
    try:
        document = {
            'skill': skill,
            'question': question,
            'answer': answer
        }
        collection.insert_one(document)
        print(f"Stored question and answer for skill '{skill}' into MongoDB.")
    except Exception as e:
        print(f"Error storing data into MongoDB: {e}")
        
        
        
        
        
if __name__ == "__main__":
    main()
