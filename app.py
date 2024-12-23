from flask import Flask, render_template, request, abort
import subprocess
import os
import re
from transformers import pipeline
from googletrans import Translator

app = Flask(__name__)

# Route to render the homepage
@app.route('/')
def home():
    return render_template('index.html')

# Route to handle the summary generation
@app.route('/summary', methods=['POST'])
def summary():
    video_url = request.form['linkInput']  # Get the YouTube link from the form
    try:
        # Process the video to extract and summarize subtitles
        video_summary = process_video(video_url)
        return render_template('summary.html', summary=video_summary)
    except Exception as e:
        return render_template('summary.html', summary=f"An error occurred: {e}")

# Function to download VTT subtitles from a YouTube video
def download_vtt(video_url):
    output_vtt_path = "temp_subtitles.%(ext)s"
    try:
        subprocess.run(
            [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-lang", "en",
                "--skip-download",
                "-o", output_vtt_path,
                video_url
            ],
            check=True
        )
        print(f"Downloaded subtitles for: {video_url}")
    except subprocess.CalledProcessError as e:
        print("Failed to download subtitles:", str(e))
        raise

    # Find the downloaded .vtt file
    vtt_file = None
    for file in os.listdir():
        if file.endswith(".vtt"):
            vtt_file = file
            break

    if not vtt_file:
        raise FileNotFoundError("Subtitle file not found!")

    # Read the content of the .vtt file
    with open(vtt_file, "r", encoding="utf-8") as file:
        vtt_content = file.read()

    # Remove the temporary .vtt file
    os.remove(vtt_file)
    return vtt_content

# Function to clean the VTT subtitles
def clean_vtt_content(vtt_text):
    vtt_text = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}", '', vtt_text)  # Remove timestamps
    vtt_text = re.sub(r'align:start position:\d+%', '', vtt_text)  # Remove position info
    vtt_text = re.sub(r'<.*?>', '', vtt_text)  # Remove formatting tags
    clean_text = '\n'.join(
        [line.strip() for line in vtt_text.splitlines() if line.strip() and not line.startswith(('WEBVTT', 'Kind:', 'Language:'))]
    )
    return clean_text

# Function to remove repeated lines
def remove_repeated_lines(text):
    lines = text.splitlines()
    unique_lines = []
    prev_line = None

    for line in lines:
        if line != prev_line:
            unique_lines.append(line)
        prev_line = line

    return '\n'.join(unique_lines)

# Function to clean and combine text lines
def clean_text_lines(text):
    lines = text.splitlines()
    cleaned_lines = []
    current_line = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if current_line and line[0].islower() and not current_line[-1] in ".!?":
            current_line += " " + line  # Append the line if it's a continuation
        else:
            if current_line:
                cleaned_lines.append(current_line)
            current_line = line

    if current_line:
        cleaned_lines.append(current_line)

    return '\n'.join(cleaned_lines)

# Function to summarize text using a pre-trained model
def summarize_text(text, max_length=300, min_length=200):
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    try:
        summary = summarizer(
            text,
            max_length=max_length,
            min_length=min_length,
            do_sample=False,
            clean_up_tokenization_spaces=True
        )[0]['summary_text']
    except Exception as e:
        print(f"Error during summarization: {e}")
        return None

    return summary

# Main function to process the video and generate a summary
def process_video(video_url):
    print("Downloading and processing subtitles...")
    vtt_content = download_vtt(video_url)

    # Step 1: Clean the VTT content
    cleaned_content = clean_vtt_content(vtt_content)
    unique_cleaned_content = remove_repeated_lines(cleaned_content)
    final_cleaned_text = clean_text_lines(unique_cleaned_content)

    # Step 2: Summarize the text
    print("Summarizing subtitles...")
    summary = summarize_text(final_cleaned_text)

    return summary
@app.route('/translate', methods=['POST'])
def translate():
    # Get the summary and target language from the form
    original_summary = request.form['summary']
    target_language = request.form['language']

    # Initialize the translator
    translator = Translator()
    try:
        # Perform the translation
        translated_summary = translator.translate(original_summary, dest=target_language).text
    except Exception as e:
        translated_summary = f"Error during translation: {e}"

    # Render the summary page with the translated text
    return render_template('summary.html', summary=translated_summary)

if __name__ == '__main__':
    app.run(debug=True)
