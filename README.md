# 📄 Resume Analysis and Interview Bot 🤖

This project is a **resume analysis** and **interview bot** that leverages Google's Gemini-Pro AI model to extract skills from resumes, generate skill-based and HR interview questions, and analyze candidate responses. The system integrates MongoDB for storing data and Google Text-to-Speech (gTTS) for voice interaction.

## ✨ Features

- 📑 **Resume Parsing**: Extracts text from PDF resumes using `PyPDF2`.
- 🛠️ **Skill Extraction**: Detects a wide range of technical skills from resume text using regex patterns.
- 🤖 **AI-Powered Interview Bot**: Generates questions based on extracted skills and HR topics using Google's Gemini-Pro model.
- 🔄 **Follow-up Questions**: Dynamically generates follow-up questions based on user responses.
- 🧠 **Answer Evaluation**: Analyzes candidate answers for relevance and provides feedback.
- 🗄️ **MongoDB Integration**: Stores interview questions, user answers, and feedback in MongoDB.
- 🗣️ **Voice Interaction**: Uses `gTTS` for text-to-speech and `SpeechRecognition` for capturing user answers via voice.

## 🛠️ Installation

1. **Clone the repository**:

    ```bash
    git clone https://github.com/Ramithn227/Questiongenarator.git
    cd Questiongenarator
    ```

2. **Install the required Python packages**:

    ```bash
    pip install -r requirements.txt
    ```

3. **Set up environment variables**:
   
   Create a `.env` file in the root directory with the following contents:

    ```env
    GOOGLE_API_KEY=<your-google-api-key>
    MONGO_URI=<your-mongo-uri>
    ```

4. **Ensure MongoDB is running**:
   
   You can use a local instance of MongoDB or a cloud service like MongoDB Atlas.

5. **Install `ffmpeg` for audio playback** (required by `gTTS`):

    - **For Ubuntu**:
      ```bash
      sudo apt install ffmpeg
      ```

    - **For macOS** (using Homebrew):
      ```bash
      brew install ffmpeg
      ```

6. **Run the application**:

    ```bash
    python your_file.py
    ```

## 📂 Project Structure

```bash
📦resume-interview-bot
 ┣ 📂data                   # Sample resumes or test data (if any)
 ┣ 📂notebooks              # Jupyter notebooks for experiments 
 ┣ 📜main.py                # Main script to run the interview bot
 ┣ 📜requirements.txt       # List of dependencies
 ┣ 📜README.md              # This README file
 ┗ 📜.env                   # Environment variables file

## 🚀 Usage

1. **Start the bot**: Upon running the script, it will prompt you to input the resume file path and the person's ID.
2. **Skill extraction**: The bot extracts skills from the resume and prepares skill-based questions.
3. **Interview simulation**: The bot asks the user questions, analyzes their responses, and generates follow-up questions.
4. **Voice interaction**: Optionally, you can answer using your voice (via `SpeechRecognition`) or by typing.

## 💡 Technologies Used

- **Google's Gemini-Pro AI Model**: For generating interview questions and analyzing responses.
- **MongoDB**: To store interview data.
- **gTTS (Google Text-to-Speech)**: For converting text into speech.
- **PyPDF2**: For extracting text from PDF resumes.
- **SpeechRecognition**: To capture spoken answers from the user.
- **pymongo**: For MongoDB interaction.

## 👨‍💻 Author
 @Ramithn227 (https://github.com/Ramithn227)
