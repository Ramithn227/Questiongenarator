import os
import re
import time
from dotenv import load_dotenv
import google.generativeai as gen_ai
from PyPDF2 import PdfReader

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Set up Google Gemini-Pro AI model
gen_ai.configure(api_key=GOOGLE_API_KEY)
model = gen_ai.GenerativeModel('gemini-pro')

# Initialize storage for resume content and skill set
resume_texts = []
skills = []
questions = []  # To store generated questions

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
        f"Evaluate the following answer to determine if it appropriately addresses the given question. "
        f"Provide feedback on whether the answer is relevant and complete.\n\n"
        f"Question: {question}\n"
        f"Answer: {answer}\n"
        f"Feedback:"
    )

# Function to analyze the answer
def analyze_answer(question, answer):
    prompt = generate_analysis_prompt(question, answer)
    try:
        response = model.start_chat().send_message(prompt)
        feedback = response.text.strip()
        print(f"Feedback: {feedback}")
        # If feedback suggests the answer is relevant, return True, otherwise return False
        if "relevant" in feedback.lower() or "appropriate" in feedback.lower():
            return True
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
        f"I dont need any line also i just need the question without any prefixs with numbers as such."
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

    all_answers = []  # List to store all questions and their answers

    # Generate and filter questions based on each extracted skill
    for skill in skills:
        print(f"\nGenerating questions for skill: {skill}")
        generated_questions = generate_questions_based_on_skills(skill)

        if isinstance(generated_questions, str):
            print(generated_questions)  # Output the message if no skills were found
            continue

        # Display only valid questions
        filtered_questions = [q for q in generated_questions if is_valid_question(q)]
        if not filtered_questions:
            print(f"No valid questions generated for {skill}.")
            continue

        for i, question in enumerate(filtered_questions):
            while True:
                print(f"\nQuestion {i + 1}: {question}")
                answer = input(f"Your Answer {i + 1}: ")
                # Analyze the answer and decide whether to proceed to the next question
                if analyze_answer(question, answer):
                    all_answers.append((question, answer))
                    break
                else:
                    # If the answer is irrelevant, move to the next skill's questions
                    break

    # Final Summary of all questions and answers
    print("\nAll Questions and Answers:")
    for i, (q, a) in enumerate(all_answers, start=1):
        print(f"\nQuestion {i}: {q}")
        print(f"Your Answer {i}: {a}")

    print("\nThank you for your responses! Analysis completed.")

if __name__ == "__main__":
    main()
