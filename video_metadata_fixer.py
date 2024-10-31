import os
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import ffmpeg
import langid
import speech_recognition as sr

# Configuration
AUDIO_FORMAT = ".wav"
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov")

# Global variable to store extracted audio files for cleanup
extracted_audio_files = []

# Set up the main application window
app = tk.Tk()
app.title("Video Metadata Fixer")
app.geometry("450x580")

# Create a label for overall instructions
instruction_label = tk.Label(
    app, text="Please follow the steps below:", font=("Arial", 11), pady=(5)
)
instruction_label.pack(pady=(0, 5))

# Create a label for the folder input instructions
folder_instruction_label = tk.Label(app, text="Select a folder containing video files:")
folder_instruction_label.pack(anchor="w", padx=40)

# Create a frame to hold the entry and button
frame = tk.Frame(app)
frame.pack(pady=5)

# Create an input box for folder path
entry = tk.Entry(frame, width=52, bg="lightskyblue1", fg="black")
entry.grid(row=0, column=0, padx=5)

# Create a button to browse for a folder
browse_button = tk.Button(
    frame, text="Browse", bg="snow", fg="black", command=lambda: browse_folder()
)
browse_button.grid(row=0, column=1)

# Create a label for the folder input instructions
file_list_instruction_label = tk.Label(app, text="The files will be listed below:")
file_list_instruction_label.pack(anchor="w", padx=40)

# Create a frame for the list boxes and progress bar
output_frame = tk.Frame(app)
output_frame.pack(pady=(10, 0))

# Create a listbox to display video files
file_list = tk.Listbox(output_frame, height=10, width=60, bg="grey", fg="black")
file_list.grid(row=0, column=0, padx=5, pady=5)

# Create a progress bar with adjusted width and padding
width = 370
progress_bar = ttk.Progressbar(
    output_frame, orient="horizontal", mode="determinate", length=width - 12
)
progress_bar.grid(row=1, column=0, pady=0, sticky="", padx=0, ipadx=2, ipady=2)

# Create a label for the folder input instructions
log_instruction_label = tk.Label(
    app, text="Individual success or failure will appear here:"
)
log_instruction_label.pack(anchor="w", padx=40)

# Create a listbox for logging
log_listbox = tk.Listbox(output_frame, height=10, width=60, bg="grey", fg="black")
log_listbox.grid(row=2, column=0, padx=5, pady=5)

# Set uniform weight for the column
output_frame.columnconfigure(0, weight=1)


def browse_folder():
    folder_path = filedialog.askdirectory()
    if folder_path:
        entry.delete(0, tk.END)
        entry.insert(0, folder_path)
        list_video_files(folder_path)


def list_video_files(folder_path):
    video_files = [
        f for f in os.listdir(folder_path) if f.lower().endswith(VIDEO_EXTENSIONS)
    ]
    file_list.delete(0, tk.END)
    for file in video_files:
        file_list.insert(tk.END, file)


def process_video_files():
    folder_path = entry.get()
    video_files = file_list.get(0, tk.END)

    for index, filename in enumerate(video_files):
        full_path = os.path.join(folder_path, filename)

        show_progress(f"Processing {filename}...")

        try:
            audio_tracks = check_audio_tracks(full_path)
            if audio_tracks:
                for track in audio_tracks:
                    if not has_language_metadata(full_path):
                        show_progress(f"Extracting audio from {filename}...")
                        audio_file = extract_audio(full_path)
                        extracted_audio_files.append(audio_file)
                        if audio_file:
                            transcription = transcribe_audio(audio_file)
                            if transcription:
                                language = identify_language(transcription)
                                if language:
                                    show_progress(
                                        f"Updating metadata for {filename}..."
                                    )
                                    update_metadata(full_path, language)

            else:
                log_message(f"No audio tracks found in {filename}.")
        except Exception as e:
            error_message = f"Error processing {filename}: {str(e)}"
            log_message(error_message)

        # Update progress bar
        progress_bar["value"] = (index + 1) / len(video_files) * 100
        app.update_idletasks()

    messagebox.showinfo("Done", "Processing complete!")


def show_progress(message):
    log_message(message)
    progress_bar.start()


def log_message(message):
    log_listbox.insert(tk.END, message)
    log_listbox.see(tk.END)


def check_audio_tracks(video_path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index,tag:language",
                "-of",
                "csv=p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        audio_streams = result.stdout.strip().split("\n")
        return audio_streams if audio_streams[0] else []
    except Exception as e:
        raise Exception(f"Error checking audio tracks: {e}")


def extract_audio(video_path: str) -> str:
    audio_path = os.path.splitext(video_path)[0] + AUDIO_FORMAT
    try:
        result = subprocess.run(
            ["ffmpeg", "-i", video_path, "-ac", "2", audio_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        log_message(f"Extracted audio from {video_path} to {audio_path}.")
        return audio_path
    except subprocess.CalledProcessError as e:
        log_message(f"FFmpeg error for {video_path}: {e.stderr.decode()}")
        raise Exception("Audio extraction failed")


def transcribe_audio(audio_path: str) -> str:
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            log_message(f"Transcribing audio from {audio_path}.")
            transcription = recognizer.recognize_google(audio_data)
            log_message(f"Transcription successful: {transcription}")
            return transcription
    except sr.RequestError as e:
        log_message(f"API request error: {e}")
        raise Exception("Transcription request failed")
    except sr.UnknownValueError:
        log_message("Could not understand audio.")
        raise Exception("Audio not understood")
    except Exception as e:
        log_message(f"Unexpected error during transcription: {e}")
        raise Exception("Transcription failed")


def identify_language(transcription):
    if transcription:
        lang, _ = langid.classify(transcription)
        return lang
    return None


def update_metadata(video_path, language):
    try:
        ffmpeg.input(video_path).output(
            video_path, **{"metadata": f"language={language}"}
        ).run(overwrite_output=True)
        log_message(f"Updated metadata for {video_path} with language: {language}.")
    except Exception as e:
        raise Exception(f"Error updating metadata: {e}")


def has_language_metadata(video_path):
    """Check if the video already has language metadata."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index,tag:language",
                "-of",
                "csv=p=0",
                video_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        languages = result.stdout.strip().split("\n")
        return any(lang for lang in languages if lang)
    except Exception as e:
        log_message(f"Error checking language metadata: {e}")
        return False


# Create a frame for buttons
button_frame = tk.Frame(app)
button_frame.pack(pady=(5, 0))

# Create a button to start processing video files
process_button = tk.Button(
    button_frame,
    text="Process Videos",
    bg="snow",
    fg="black",
    command=lambda: threading.Thread(target=process_video_files).start(),
)
process_button.pack(side=tk.LEFT, padx=5)

# Create a button to quit the application
quit_button = tk.Button(
    button_frame, text="Quit", bg="snow", fg="black", command=lambda: app.quit()
)
quit_button.pack(side=tk.LEFT, padx=5)

# Run the application
app.mainloop()
