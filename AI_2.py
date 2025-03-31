import streamlit as st
import os
import zipfile
import moviepy.editor as mp
from PIL import Image
import shutil
import mysql.connector
import requests
import base64
import logging
import subprocess
import imghdr
from reverie_sdk import ReverieClient
import speech_recognition as sr
import re
import moviepy.config as mp_config
from concurrent.futures import ThreadPoolExecutor
import time
import keyboard

# Set ImageMagick path
mp_config.IMAGEMAGICK_BINARY = r"C:\Program Files\ImageMagick-7.1.1-Q16-HDRI\magick.exe"

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Check for FFmpeg
try:
    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    logger.info("FFmpeg is installed and accessible.")
except (subprocess.CalledProcessError, FileNotFoundError) as e:
    logger.error("FFmpeg is not installed or not found in PATH. Please install FFmpeg.")
    st.error("FFmpeg is required but not found. Please install FFmpeg and add it to your PATH.")
    st.stop()

# Folders for file handling
UPLOAD_FOLDER = "uploads"
EXTRACT_FOLDER = "extracted_files"
OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"
for folder in [UPLOAD_FOLDER, EXTRACT_FOLDER, OUTPUT_FOLDER, TEMP_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# MySQL Database Configuration
db_config = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'pictory_db'
}

# API Configuration
GEMINI_API_KEY = "AIzaSyBnrZ6cb6whzoOfCZ0XHEgjzkO555ELCAM"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_API_VERSION = "v1"
GEMINI_MODEL = "gemini-1.5-flash"

# Initialize Reverie client
reverie_client = ReverieClient(
    api_key="5d9ef1b241e043cd692a0ae4f188e1b18985b141",
    app_id="com.adarshk0904",
)

# Supported languages
SUPPORTED_LANGUAGES = {
    "1": {"code": "hi-IN", "name": "Hindi", "rev_code": "hi", "speakers": ["hi_male", "hi_female"]},
    "2": {"code": "bn-IN", "name": "Bengali", "rev_code": "bn", "speakers": ["bn_male", "bn_female"]},
    "3": {"code": "kn-IN", "name": "Kannada", "rev_code": "kn", "speakers": ["kn_male", "kn_female"]},
    "4": {"code": "ml-IN", "name": "Malayalam", "rev_code": "ml", "speakers": ["ml_male", "ml_female"]},
    "5": {"code": "ta-IN", "name": "Tamil", "rev_code": "ta", "speakers": ["ta_male", "ta_female"]},
    "6": {"code": "te-IN", "name": "Telugu", "rev_code": "te", "speakers": ["te_male", "te_female"]},
    "7": {"code": "gu-IN", "name": "Gujarati", "rev_code": "gu", "speakers": ["gu_male", "gu_female"]},
    "8": {"code": "or-IN", "name": "Odia", "rev_code": "or", "speakers": ["or_male", "or_female"]},
    "9": {"code": "as-IN", "name": "Assamese", "rev_code": "as", "speakers": ["as_male", "as_female"]},
    "10": {"code": "mr-IN", "name": "Marathi", "rev_code": "mr", "speakers": ["mr_male", "mr_female"]},
    "11": {"code": "pa-IN", "name": "Punjabi", "rev_code": "pa", "speakers": ["pa_male", "pa_female"]},
    "12": {"code": "en-IN", "name": "Indian English", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "13": {"code": "kok-IN", "name": "Konkani", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "14": {"code": "doi-IN", "name": "Dogri", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "15": {"code": "brx-IN", "name": "Bodo", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "16": {"code": "ur-IN", "name": "Urdu", "rev_code": "ur", "speakers": ["ur_male", "ur_female"]},
    "17": {"code": "ks-IN", "name": "Kashmiri", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "18": {"code": "sd-IN", "name": "Sindhi", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "19": {"code": "mai-IN", "name": "Maithili", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "20": {"code": "mni-IN", "name": "Manipuri", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "21": {"code": "sa-IN", "name": "Sanskrit", "rev_code": "en", "speakers": ["en_male", "en_female"]},
    "22": {"code": "ne-IN", "name": "Nepali", "rev_code": "ne", "speakers": ["ne_male", "ne_female"]},
    "23": {"code": "sat-IN", "name": "Santali", "rev_code": "en", "speakers": ["en_male", "en_female"]},
}

# Custom CSS for better UI
st.markdown("""
    <style>
    .main {background-color: #f0f2f6;}
    .stButton>button {background-color: #4CAF50; color: white; border-radius: 5px;}
    .stTextInput>input, .stTextArea>textarea {border-radius: 5px; border: 1px solid #ccc;}
    .stSelectbox>div {background-color: #fff; border-radius: 5px;}
    .recording-feedback {font-size: 16px; color: #FF5733; font-weight: bold; animation: blink 1s infinite;}
    @keyframes blink {
        50% {opacity: 0;}
    }
    </style>
""", unsafe_allow_html=True)

# Database connection
db_conn = None
db_cursor = None

def init_db():
    global db_conn, db_cursor
    try:
        db_conn = mysql.connector.connect(**db_config)
        db_cursor = db_conn.cursor()
        db_cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db_cursor.execute('''
            CREATE TABLE IF NOT EXISTS stories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                user_text TEXT NOT NULL,
                detected_lang VARCHAR(10),
                output_lang VARCHAR(10),
                video_path VARCHAR(255),
                status VARCHAR(20) DEFAULT 'published',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        db_conn.commit()
        logger.info("Database connection established and tables created.")
        st.success("Database connection established and tables created.")
    except mysql.connector.Error as e:
        logger.error(f"Database connection failed: {str(e)}")
        st.error(f"Database connection failed: {str(e)}")
        st.stop()

def register(username, password):
    global db_conn, db_cursor
    try:
        db_cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        db_conn.commit()
        return True
    except mysql.connector.Error as e:
        logger.error(f"Registration failed: {str(e)}")
        return False

def login(username, password):
    global db_conn, db_cursor
    try:
        db_cursor.execute("SELECT id FROM users WHERE username = %s AND password = %s", (username, password))
        user = db_cursor.fetchone()
        return user[0] if user else None
    except mysql.connector.Error as e:
        logger.error(f"Login failed: {str(e)}")
        return None

@st.cache_data
def process_input(text_input, media_paths=None):
    if not text_input or text_input == "Example description or no description":
        text_input = "A journey through the snowy mountains of Manali in December."
    detected_lang = "en"
    gemini_url = f"{GEMINI_BASE_URL}/{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": f"Detect the language of the following text and return the language code (e.g., 'en', 'hi'): {text_input}"}]}],
            "generationConfig": {"maxOutputTokens": 10}
        }
        response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", json=payload, headers=headers)
        response.raise_for_status()
        detected_lang = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "en")
        if detected_lang not in [lang["rev_code"] for lang in SUPPORTED_LANGUAGES.values()]:
            detected_lang = "en"
        logger.info(f"Detected language from text: {detected_lang}")
    except requests.RequestException as e:
        logger.error(f"Failed to detect language: {str(e)}")
        logger.warning("Defaulting to English.")
    if media_paths:
        for media_path in media_paths:
            try:
                with open(media_path, "rb") as file:
                    file_content = base64.b64encode(file.read()).decode("utf-8")
                mime_type = "image/jpeg" if media_path.lower().endswith(('.jpg', '.jpeg', '.png')) else "video/mp4"
                payload = {
                    "contents": [{"parts": [{"inline_data": {"mime_type": mime_type, "data": file_content}}, {"text": "Detect the language of any text in this media. Return the language code (e.g., 'hi', 'en')."}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                }
                response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", json=payload, headers=headers)
                response.raise_for_status()
                media_detected_lang = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "en")
                if media_detected_lang not in [lang["rev_code"] for lang in SUPPORTED_LANGUAGES.values()]:
                    media_detected_lang = "en"
                logger.info(f"Detected language from media {media_path}: {media_detected_lang}")
                if media_detected_lang != "en":
                    detected_lang = media_detected_lang
                    break
            except requests.RequestException as e:
                logger.error(f"Failed to detect language from media {media_path}: {str(e)}")
    return text_input, detected_lang

@st.cache_data
def analyze_single_image(image_path, mime_type="image/jpeg"):
    gemini_url = f"{GEMINI_BASE_URL}/{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    try:
        with open(image_path, "rb") as file:
            file_content = base64.b64encode(file.read()).decode("utf-8")
        payload = {
            "contents": [{"parts": [{"inline_data": {"mime_type": mime_type, "data": file_content}}, {"text": "Describe this image in a short sentence in English."}]}],
            "generationConfig": {"maxOutputTokens": 50}
        }
        response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", json=payload, headers=headers)
        response.raise_for_status()
        description = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        logger.info(f"Image description for {image_path}: {description}")
        return description
    except requests.RequestException as e:
        logger.error(f"Image analysis failed for {image_path}: {str(e)}")
        return "Failed to analyze image."

@st.cache_data
def analyze_single_video(video_path):
    gemini_url = f"{GEMINI_BASE_URL}/{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    try:
        # Extract frames from video
        clip = mp.VideoFileClip(video_path)
        duration = clip.duration
        frame_interval = max(1, duration / 3)  # Extract up to 3 frames, at least 1 second apart
        frame_paths = []
        for t in [frame_interval * i for i in range(min(3, int(duration // frame_interval) + 1))]:
            frame_path = os.path.join(TEMP_FOLDER, f"frame_{os.path.basename(video_path)}_{t}.jpg")
            clip.save_frame(frame_path, t=t)
            frame_paths.append(frame_path)
        clip.close()

        # Analyze frames
        frame_descriptions = []
        for frame_path in frame_paths:
            with open(frame_path, "rb") as file:
                file_content = base64.b64encode(file.read()).decode("utf-8")
            payload = {
                "contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": file_content}}, {"text": "Describe this frame from a video in a short sentence in English."}]}],
                "generationConfig": {"maxOutputTokens": 50}
            }
            response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", json=payload, headers=headers)
            response.raise_for_status()
            desc = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            frame_descriptions.append(desc)
        
        # Combine into a single description
        combined_desc = " ".join(frame_descriptions)
        logger.info(f"Video description for {video_path}: {combined_desc}")
        return combined_desc
    except Exception as e:
        logger.error(f"Video analysis failed for {video_path}: {str(e)}")
        return "Failed to analyze video."

@st.cache_data
def generate_continuous_story(media_descriptions, user_description, output_language_code, detected_lang, num_segments):
    gemini_url = f"{GEMINI_BASE_URL}/{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    target_lang = output_language_code.split('-')[0]
    media_desc_text = "\n".join([f"Media {i+1}: {desc}" for i, desc in enumerate(media_descriptions)])
    prompt = f"Based on the following user description: '{user_description}', and the descriptions of {num_segments} media items (images or videos):\n{media_desc_text}\nGenerate a continuous story in {target_lang} that flows naturally across the media, describing a journey in Manali in December. The story should be cohesive, reflecting the specific details of each media item in sequence, and should include a narrative arc with a beginning, middle, and end. Split the story into exactly {num_segments} non-empty parts, each corresponding to one media item. Each part should be a concise sentence of 15-20 words, suitable for narration within 8 seconds at a normal speaking pace (120-150 words per minute). Ensure each part builds on the previous part and maintains the context of a journey. Return the parts as a list separated by newlines, without any numbering or labels."
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 500}}
    for attempt in range(3):
        try:
            response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", json=payload, headers=headers)
            response.raise_for_status()
            story_text = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            story_segments = [segment.strip() for segment in story_text.split("\n") if segment.strip()]
            cleaned_segments = [re.sub(r'^\d+\.\s*|\d+\s*', '', segment).strip() for segment in story_segments if re.sub(r'^\d+\.\s*|\d+\s*', '', segment).strip()]
            if len(cleaned_segments) != num_segments:
                logger.warning(f"Expected {num_segments} segments, got {len(cleaned_segments)}. Retrying...")
                continue
            logger.info(f"Generated story segments: {cleaned_segments}")
            return cleaned_segments
        except requests.RequestException as e:
            logger.error(f"Story generation failed (attempt {attempt + 1}): {str(e)}")
            if attempt == 2:
                st.error("Failed to generate story after multiple attempts. Please try again.")
                return None
    story_segments = [f"In {target_lang}, we continued our journey in Manali, enjoying the scenery of media {i+1}." for i in range(num_segments)]
    logger.warning("Using fallback story segments due to repeated failures.")
    return story_segments

def translate_text(text, source_lang, target_lang):
    gemini_url = f"{GEMINI_BASE_URL}/{GEMINI_API_VERSION}/models/{GEMINI_MODEL}:generateContent"
    headers = {"Content-Type": "application/json"}
    prompt = f"Translate the following text from {source_lang} to {target_lang}: '{text}'"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 100}}
    try:
        response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", json=payload, headers=headers)
        response.raise_for_status()
        translated_text = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", text)
        logger.info(f"Translated text from {source_lang} to {target_lang}: {translated_text}")
        return translated_text
    except requests.RequestException as e:
        logger.error(f"Translation failed: {str(e)}")
        st.error(f"Translation failed: {str(e)}. Using original text as fallback.")
        return text

def generate_tts_audio(text, output_path, language_code, voice="female"):
    lang_info = next((info for info in SUPPORTED_LANGUAGES.values() if info["code"] == language_code), None)
    rev_lang = lang_info["rev_code"]
    speaker = f"{rev_lang}_{voice}"
    if speaker not in lang_info["speakers"]:
        speaker = lang_info["speakers"][0]
    try:
        resp = reverie_client.tts.tts(text=text, speaker=speaker)
        resp.save_audio(output_path, create_parents=True, overwrite_existing=True)
        logger.info(f"Generated audio at {output_path} in {rev_lang} with {speaker}")
        return True
    except Exception as e:
        logger.error(f"TTS Error: {str(e)}")
        st.error(f"Failed to generate audio narration: {str(e)}")
        return False

def create_video_snippet(media_path, audio_path, output_path, text, duration=8):
    try:
        if not os.path.exists(media_path):
            logger.error(f"Media file does not exist: {media_path}")
            return False
        if media_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            try:
                img = Image.open(media_path)
                img.verify()
                img.close()
            except Exception as e:
                logger.error(f"Invalid image file {media_path}: {str(e)}")
                return False
            media_clip = mp.ImageClip(media_path).set_duration(duration).resize((854, 480))
        elif media_path.lower().endswith('.mp4'):
            media_clip = mp.VideoFileClip(media_path)
            media_clip = media_clip.subclip(0, min(duration, media_clip.duration)).resize((854, 480))
        else:
            logger.error(f"Unsupported media type: {media_path}")
            return False

        audio = mp.AudioFileClip(audio_path)
        final_duration = min(duration, audio.duration, media_clip.duration if media_path.lower().endswith('.mp4') else duration)
        audio = audio.subclip(0, final_duration)
        media_clip = media_clip.set_duration(final_duration)
        logger.info(f"Loaded media: {media_path}, duration: {final_duration}")

        try:
            text = text[:100]
            txt_clip = mp.TextClip(
                text,
                fontsize=20,
                color='white',
                bg_color='black',
                size=(854, 80),
                method='caption'
            )
            txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(final_duration)
            logger.info("Created text overlay")
        except Exception as e:
            logger.error(f"Failed to create text overlay: {str(e)}")
            if "ImageMagick" in str(e):
                st.error("ImageMagick is not installed or configured correctly. Text overlays will be skipped.")
            txt_clip = None

        if txt_clip:
            video = mp.CompositeVideoClip([media_clip, txt_clip]).set_audio(audio)
        else:
            video = media_clip.set_audio(audio)
        
        video.write_videofile(
            output_path,
            fps=24,
            codec="libx264",
            audio_codec="aac",
            verbose=True,
            logger=None
        )
        logger.info(f"Created video snippet at {output_path}")
        if not os.path.exists(output_path):
            logger.error(f"Video file {output_path} was not created.")
            return False
        return True
    except Exception as e:
        logger.error(f"Failed to create video snippet: {str(e)}")
        st.error(f"Failed to create video snippet: {str(e)}")
        return False

def concatenate_videos(video_paths, output_path, background_music_path=None):
    try:
        clips = []
        for video_path in video_paths:
            if os.path.exists(video_path):
                clip = mp.VideoFileClip(video_path)
                clips.append(clip)
            else:
                logger.warning(f"Video file {video_path} does not exist, skipping.")
        if not clips:
            logger.error("No valid video clips to concatenate.")
            st.error("No valid video clips available to concatenate.")
            return False
        final_clip = mp.concatenate_videoclips(clips, method="compose")
        if background_music_path and os.path.exists(background_music_path):
            bg_audio = mp.AudioFileClip(background_music_path).set_duration(final_clip.duration).volumex(0.3)
            final_audio = mp.CompositeAudioClip([final_clip.audio, bg_audio])
            final_clip = final_clip.set_audio(final_audio)
        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            verbose=True,
            logger=None
        )
        for clip in clips:
           
            clip.close()
        final_clip.close()
        logger.info(f"Concatenated video saved at {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to concatenate videos: {str(e)}")
        st.error(f"Failed to concatenate videos: {str(e)}")
        return False

def process_snippet(args):
    i, media_path, segment, output_lang_code, voice = args
    audio_path = os.path.join(TEMP_FOLDER, f"audio_segment_{i}.mp3")
    video_path = os.path.join(TEMP_FOLDER, f"video_segment_{i}.mp4")
    if generate_tts_audio(segment, audio_path, output_lang_code, voice):
        if create_video_snippet(media_path, audio_path, video_path, segment):
            return video_path
    return None

def process_files(media_paths, user_description, output_lang_code, voice="female"):
    user_description, detected_lang = process_input(user_description, media_paths)
    media_descriptions = []
    for media_path in media_paths:
        with st.spinner(f"Analyzing {os.path.basename(media_path)}..."):
            if media_path.lower().endswith(('.jpg', '.jpeg', '.png')):
                desc = analyze_single_image(media_path)
            elif media_path.lower().endswith('.mp4'):
                desc = analyze_single_video(media_path)
            else:
                desc = "Unsupported media type."
            media_descriptions.append(desc)
    st.write("### Media Descriptions:")
    for i, desc in enumerate(media_descriptions):
        st.write(f"Media {i+1}: {desc}")
    with st.spinner("Generating story..."):
        story_segments = generate_continuous_story(media_descriptions, user_description, output_lang_code, detected_lang, len(media_paths))
    if not story_segments:
        st.error("Failed to generate story.")
        return None, None, None, None, None
    return media_paths, story_segments, user_description, detected_lang, output_lang_code

def cleanup_temp():
    for folder in [TEMP_FOLDER, EXTRACT_FOLDER, UPLOAD_FOLDER]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            os.makedirs(folder)

def main():
    global db_conn, db_cursor
    st.title("PicStory: Generate Stories from Images and Videos")
    init_db()

    # Initialize session state variables
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_id = None
    if 'recording' not in st.session_state:
        st.session_state.recording = False
    if 'user_description' not in st.session_state:
        st.session_state.user_description = "Example description or no description"
    if 'media_paths' not in st.session_state:
        st.session_state.media_paths = None
    if 'story_segments' not in st.session_state:
        st.session_state.story_segments = None
    if 'english_segments' not in st.session_state:
        st.session_state.english_segments = None
    if 'user_desc' not in st.session_state:
        st.session_state.user_desc = None
    if 'det_lang' not in st.session_state:
        st.session_state.det_lang = None
    if 'out_lang' not in st.session_state:
        st.session_state.out_lang = None
    if 'output_lang_code' not in st.session_state:
        st.session_state.output_lang_code = None
    if 'voice' not in st.session_state:
        st.session_state.voice = None
    if 'edited_segments' not in st.session_state:
        st.session_state.edited_segments = None
    if 'edited_english_segments' not in st.session_state:
        st.session_state.edited_english_segments = None
    if 'show_complete_story' not in st.session_state:
        st.session_state.show_complete_story = False
    if 'video_snippets' not in st.session_state:
        st.session_state.video_snippets = None
    if 'selected_snippets' not in st.session_state:
        st.session_state.selected_snippets = None
    if 'show_edit_section' not in st.session_state:
        st.session_state.show_edit_section = False

    if not st.session_state.logged_in:
        tab1, tab2 = st.tabs(["Login", "Register"])
        with tab1:
            st.subheader("Login")
            login_username = st.text_input("Username", key="login_username")
            login_password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login"):
                user_id = login(login_username, login_password)
                if user_id:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_id
                    st.success(f"Welcome back, {login_username}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        with tab2:
            st.subheader("Register")
            reg_username = st.text_input("Username", key="reg_username")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            if st.button("Register"):
                if register(reg_username, reg_password):
                    st.success("Registration successful! Please login.")
                else:
                    st.error("Username already exists or registration failed.")
    else:
        st.sidebar.header("User Options")
        if st.sidebar.button("Logout"):
            st.session_state.clear()
            st.rerun()

        uploaded_file = st.file_uploader("Upload a ZIP file containing images (.jpg, .jpeg, .png) or videos (.mp4)", type=["zip"])
        st.write("### Story Description")
        col1, col2 = st.columns([3, 1])
        with col1:
            user_description = st.text_area(
                "Enter a description (optional):",
                value=st.session_state.user_description,
                key="user_desc_input",
                help="You can type a description here or use the microphone to record one."
            )
            st.session_state.user_description = user_description
        with col2:
            mic_lang_choice = st.selectbox("Mic Language:", [f"{lang['name']} ({lang['code']})" for lang in SUPPORTED_LANGUAGES.values()], index=0)
            mic_lang_code = SUPPORTED_LANGUAGES[[key for key, val in SUPPORTED_LANGUAGES.items() if f"{val['name']} ({val['code']})" == mic_lang_choice][0]]["code"]
            
            if st.button("🎤 Start/Stop Recording"):
                if not st.session_state.recording:
                    # Start recording
                    st.session_state.recording = True
                    st.write(f"<div class='recording-feedback'>Recording in {mic_lang_code}... Click again to stop</div>", unsafe_allow_html=True)
                    
                    # Initialize recognizer
                    recognizer = sr.Recognizer()
                    st.session_state.audio_data = []
                    
                    # We need to run this in a separate thread to keep the UI responsive
                    def record_audio():
                        with sr.Microphone() as source:
                            recognizer.adjust_for_ambient_noise(source, duration=1)
                            st.session_state.recording = True
                            while st.session_state.recording:
                                try:
                                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=5)
                                    st.session_state.audio_data.append(audio)
                                except sr.WaitTimeoutError:
                                    continue
                    
                    import threading
                    recording_thread = threading.Thread(target=record_audio)
                    recording_thread.start()
                else:
                    # Stop recording
                    st.session_state.recording = False
                    st.write("Processing audio...")
                    
                    # Process the recorded audio
                    full_text = ""
                    for audio_chunk in st.session_state.audio_data:
                        try:
                            text = recognizer.recognize_google(audio_chunk, language=mic_lang_code)
                            full_text += text + " "
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError as e:
                            st.error(f"Speech recognition error: {e}")
                            continue
                    
                    if full_text.strip():
                        st.session_state.user_description = full_text.strip()
                        st.success("Transcription complete!")
                    else:
                        st.error("No speech detected or could not understand the audio.")
                    
                    del st.session_state.audio_data
                    st.rerun()

            if 'user_description' in st.session_state and st.session_state.user_description != "Example description or no description":
                st.write(f"Transcribed Description: {st.session_state.user_description}")

        language_choice = st.selectbox("Select output language:", [f"{lang['name']} ({lang['code']})" for lang in SUPPORTED_LANGUAGES.values()], index=0)
        output_lang_code = SUPPORTED_LANGUAGES[[key for key, val in SUPPORTED_LANGUAGES.items() if f"{val['name']} ({val['code']})" == language_choice][0]]["code"]
        voice = st.selectbox("Select voice:", ["male", "female"])
        background_music = st.file_uploader("Upload background music (optional, MP3)", type=["mp3"])

        if st.button("Generate Story"):
            if not uploaded_file:
                st.error("Please upload a ZIP file to proceed.")
                return

            if not uploaded_file.name.endswith('.zip'):
                st.error("Only ZIP files are accepted. Please upload a ZIP file containing images (.jpg, .jpeg, .png) or videos (.mp4).")
                return

            with st.spinner("Processing files and generating story..."):
                # Clear folders to avoid residual files
                cleanup_temp()

                file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                media_paths = []
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(EXTRACT_FOLDER)
                for root, _, files in os.walk(EXTRACT_FOLDER):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4')):
                            media_paths.append(file_path)
                            logger.info(f"Found media: {file_path}")
                        else:
                            logger.info(f"Ignoring unsupported file: {file}")

                num_images = len([p for p in media_paths if p.lower().endswith(('.jpg', '.jpeg', '.png'))])
                num_videos = len([p for p in media_paths if p.lower().endswith('.mp4')])
                st.info(f"Processed {num_images + num_videos} files: {num_images} images, {num_videos} videos")

                if not media_paths:
                    st.error("No valid images or videos found in the ZIP file. Please upload a ZIP with supported files.")
                    return

                media_paths, story_segments, user_desc, det_lang, out_lang = process_files(media_paths, st.session_state.user_description, output_lang_code, voice)
                if not story_segments:
                    st.error("Failed to generate story. Please try again.")
                    return

                st.session_state.media_paths = media_paths
                st.session_state.story_segments = story_segments
                st.session_state.user_desc = user_desc
                st.session_state.det_lang = det_lang
                st.session_state.out_lang = out_lang
                st.session_state.output_lang_code = output_lang_code
                st.session_state.voice = voice
                st.session_state.edited_segments = story_segments.copy()
                st.session_state.edited_english_segments = None
                st.session_state.english_segments = None
                st.session_state.show_complete_story = False
                st.session_state.show_edit_section = False
                st.session_state.video_snippets = None
                st.session_state.selected_snippets = None

        if st.session_state.story_segments:
            target_lang = st.session_state.output_lang_code.split('-')[0]
            
            if st.session_state.english_segments is None:
                st.session_state.english_segments = []
                for segment in st.session_state.story_segments:
                    with st.spinner(f"Translating segment to English for review..."):
                        segment_in_english = translate_text(segment, target_lang, "en") if target_lang != "en" else segment
                    st.session_state.english_segments.append(segment_in_english)

            st.write("### AI-Generated Story Segments")
            for i, (segment, english_segment) in enumerate(zip(st.session_state.story_segments, st.session_state.english_segments)):
                st.write(f"Segment {i+1} (in {target_lang}): {segment}")
                st.write(f"Segment {i+1} (in English): {english_segment}")
            
            if st.button("Edit Story Segments"):
                st.session_state.show_edit_section = True
                st.session_state.edited_english_segments = st.session_state.english_segments.copy()
                st.rerun()

        if st.session_state.show_edit_section and st.session_state.story_segments:
            st.write("### Edit Story Segments (in English)")
            target_lang = st.session_state.output_lang_code.split('-')[0]
            
            edited_english_segments = []
            for i, (original_segment, english_segment) in enumerate(zip(st.session_state.story_segments, st.session_state.edited_english_segments)):
                st.write(f"Original Segment {i+1} (in {target_lang}): {original_segment}")
                st.write(f"Original English Translation: {english_segment}")
                edited_segment = st.text_input(
                    f"Edit Segment {i+1} (in English):",
                    value=english_segment,
                    key=f"edit_segment_{i}",
                    help="Edit this segment in English. It will be translated back to the target language."
                )
                edited_english_segments.append(edited_segment)
            
            st.session_state.edited_english_segments = edited_english_segments

            if st.button("Generate Edited Story"):
                with st.spinner("Translating edited segments to target language..."):
                    edited_segments = []
                    for i, edited_segment in enumerate(st.session_state.edited_english_segments):
                        translated_segment = translate_text(edited_segment, "en", target_lang) if target_lang != "en" else edited_segment
                        edited_segments.append(translated_segment)
                    st.session_state.edited_segments = edited_segments
                    st.session_state.show_edit_section = False
                    st.rerun()

        if st.session_state.edited_segments and not st.session_state.show_edit_section:
            st.write("### Edited Story Segments (in Target Language)")
            for i, segment in enumerate(st.session_state.edited_segments):
                st.write(f"Segment {i+1}: {segment}")

            if st.button("View Complete Edited Story"):
                st.session_state.show_complete_story = True
                st.rerun()

        if st.session_state.show_complete_story and st.session_state.edited_segments:
            st.write("### Complete Edited Story")
            complete_story = " ".join(st.session_state.edited_segments)
            st.write(complete_story)

            if st.button("Create Video Snippets"):
                if not st.session_state.media_paths or not st.session_state.edited_segments:
                    st.error("Required data is missing. Please generate the story again.")
                    return

                with st.spinner("Generating video snippets..."):
                    video_snippets = []
                    with ThreadPoolExecutor() as executor:
                        video_snippets = list(executor.map(
                            process_snippet,
                            [(i, media, seg, st.session_state.output_lang_code, st.session_state.voice)
                             for i, (media, seg) in enumerate(zip(st.session_state.media_paths, st.session_state.edited_segments))]
                        ))
                    video_snippets = [v for v in video_snippets if v]

                    if not video_snippets:
                        st.error("Failed to generate video snippets. Please check the logs for details.")
                        return

                    st.session_state.video_snippets = video_snippets
                    st.session_state.selected_snippets = list(range(len(video_snippets)))

        if st.session_state.video_snippets:
            st.write("### Preview Video Snippets")
            for i, video_path in enumerate(st.session_state.video_snippets):
                if i in st.session_state.selected_snippets:
                    st.write(f"Snippet {i+1}:")
                    with open(video_path, "rb") as video_file:
                        st.video(video_file, format="video/mp4")
                    if st.button(f"Remove Snippet {i+1}", key=f"remove_{i}"):
                        st.session_state.selected_snippets.remove(i)
                        st.rerun()

            if st.session_state.selected_snippets:
                if st.button("Concatenate Selected Snippets"):
                    with st.spinner("Concatenating selected snippets..."):
                        final_snippets = [st.session_state.video_snippets[i] for i in st.session_state.selected_snippets]
                        final_video_path = os.path.join(OUTPUT_FOLDER, "final_story.mp4")
                        bg_music_path = os.path.join(UPLOAD_FOLDER, background_music.name) if background_music else None
                        if bg_music_path:
                            with open(bg_music_path, "wb") as f:
                                f.write(background_music.getbuffer())
                        success = concatenate_videos(final_snippets, final_video_path, bg_music_path)
                        if success:
                            st.write("### Final Concatenated Video:")
                            with open(final_video_path, "rb") as final_video:
                                st.video(final_video, format="video/mp4")
                            with open(final_video_path, "rb") as file:
                                st.download_button(
                                    label="Download Video",
                                    data=file,
                                    file_name="final_story.mp4",
                                    mime="video/mp4"
                                )
                            cleanup_temp()

                            try:
                                db_cursor.executemany(
                                    'INSERT INTO stories (user_id, user_text, detected_lang, output_lang, video_path) VALUES (%s, %s, %s, %s, %s)',
                                    [(st.session_state.user_id, st.session_state.user_desc, st.session_state.det_lang, st.session_state.out_lang, video_path)
                                     for video_path in final_snippets]
                                )
                                db_conn.commit()
                                st.success(f"Saved {len(final_snippets)} story segments to database.")
                            except mysql.connector.Error as e:
                                logger.error(f"Failed to save to database: {e}")
                                st.error(f"Failed to save to database: {e}")
                        else:
                            st.error("Failed to concatenate videos. Please check the logs for details.")
            else:
                st.warning("No snippets selected. Please keep at least one snippet to concatenate.")

if __name__ == "__main__":
    try:
        import keyboard
    except ImportError:
        print("Please install the 'keyboard' module: pip install keyboard")
        exit()
    main()