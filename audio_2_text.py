import speech_recognition as sr
import pyaudio
import wave
import os
from datetime import datetime
import threading
import time

# Global variables for recording control
recording = False
audio_frames = []

def install_requirements():
    """Print installation requirements"""
    print("Required packages:")
    print("pip install speechrecognition pyaudio pydub")
    print("For better accuracy, also install:")
    print("pip install google-cloud-speech")
    print("\nFor audio file support:")
    print("pip install pydub[mp3]")

def record_audio(filename="recording.wav", sample_rate=44100, chunk_size=1024, channels=1):
    """Record audio from microphone and save to file"""
    global recording, audio_frames
    
    audio = pyaudio.PyAudio()
    
    # Start recording
    stream = audio.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk_size
    )
    
    print(f"🎤 Recording started. Press Enter to stop...")
    recording = True
    audio_frames = []
    
    # Record in separate thread
    def record_thread():
        while recording:
            data = stream.read(chunk_size)
            audio_frames.append(data)
    
    thread = threading.Thread(target=record_thread)
    thread.start()
    
    # Wait for user input to stop
    input()  # Press Enter to stop
    recording = False
    thread.join()
    
    # Stop and close stream
    stream.stop_stream()
    stream.close()
    audio.terminate()
    
    # Save recorded audio
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(audio_frames))
    
    print(f"✅ Recording saved as: {filename}")
    return filename

def transcribe_audio_file(audio_file_path, engine='google', language='en-US'):
    """Transcribe audio file to text"""
    recognizer = sr.Recognizer()
    
    # Load audio file
    try:
        with sr.AudioFile(audio_file_path) as source:
            print(f"🔄 Loading audio file: {audio_file_path}")
            audio_data = recognizer.record(source)
            
        print(f"🔄 Transcribing with {engine} engine...")
        
        # Choose transcription engine
        if engine == 'google':
            text = recognizer.recognize_google(audio_data, language=language)
        elif engine == 'sphinx':
            text = recognizer.recognize_sphinx(audio_data)
        elif engine == 'wit':
            text = recognizer.recognize_wit(audio_data, key="YOUR_WIT_KEY")
        else:
            text = recognizer.recognize_google(audio_data, language=language)
            
        return text
        
    except sr.UnknownValueError:
        return "❌ Could not understand audio"
    except sr.RequestError as e:
        return f"❌ Error with transcription service: {e}"
    except FileNotFoundError:
        return f"❌ Audio file not found: {audio_file_path}"
    except Exception as e:
        return f"❌ Error: {e}"

def live_transcribe(duration=5, language='en-US'):
    """Live speech recognition from microphone"""
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    
    # Adjust for ambient noise
    print("🔄 Adjusting for ambient noise... Please wait.")
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
    
    print(f"🎤 Listening for {duration} seconds. Speak now!")
    
    try:
        with microphone as source:
            audio_data = recognizer.listen(source, timeout=duration)
        
        print("🔄 Processing speech...")
        text = recognizer.recognize_google(audio_data, language=language)
        return text
        
    except sr.WaitTimeoutError:
        return "❌ No speech detected within time limit"
    except sr.UnknownValueError:
        return "❌ Could not understand speech"
    except sr.RequestError as e:
        return f"❌ Error with speech recognition service: {e}"

def save_transcription_to_file(text, filename=None):
    """Save transcribed text to file"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"transcription_{timestamp}.txt"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"Transcription Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("-" * 50 + "\n")
            f.write(text)
            f.write("\n")
        
        print(f"✅ Transcription saved to: {filename}")
        return filename
        
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return None

def batch_transcribe_folder(folder_path, output_file="batch_transcriptions.txt"):
    """Transcribe all audio files in a folder"""
    supported_formats = ['.wav', '.mp3', '.m4a', '.flac', '.aiff']
    transcriptions = []
    
    if not os.path.exists(folder_path):
        print(f"❌ Folder not found: {folder_path}")
        return
    
    print(f"🔄 Processing audio files in: {folder_path}")
    
    for filename in os.listdir(folder_path):
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext in supported_formats:
            file_path = os.path.join(folder_path, filename)
            print(f"\n📁 Processing: {filename}")
            
            # Convert non-wav files if needed
            if file_ext != '.wav':
                converted_path = convert_audio_to_wav(file_path)
                if converted_path:
                    text = transcribe_audio_file(converted_path)
                    os.remove(converted_path)  # Clean up converted file
                else:
                    text = "❌ Could not convert audio file"
            else:
                text = transcribe_audio_file(file_path)
            
            transcriptions.append({
                'filename': filename,
                'text': text,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
            print(f"📝 Result: {text[:100]}..." if len(text) > 100 else f"📝 Result: {text}")
    
    # Save all transcriptions to file
    if transcriptions:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Batch Transcription Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            for item in transcriptions:
                f.write(f"File: {item['filename']}\n")
                f.write(f"Date: {item['timestamp']}\n")
                f.write(f"Transcription:\n{item['text']}\n")
                f.write("-" * 40 + "\n\n")
        
        print(f"✅ Batch transcription saved to: {output_file}")

def convert_audio_to_wav(input_file):
    """Convert audio file to WAV format using pydub"""
    try:
        from pydub import AudioSegment
        
        # Load audio file
        audio = AudioSegment.from_file(input_file)
        
        # Convert to WAV
        output_file = os.path.splitext(input_file)[0] + "_converted.wav"
        audio.export(output_file, format="wav")
        
        return output_file
        
    except ImportError:
        print("❌ pydub not installed. Install with: pip install pydub[mp3]")
        return None
    except Exception as e:
        print(f"❌ Error converting audio: {e}")
        return None

def main_menu():
    """Interactive main menu"""
    print("\n" + "=" * 50)
    print("🎙️  AUDIO TO TEXT TRANSCRIPTION TOOL")
    print("=" * 50)
    print("1. Record and transcribe speech")
    print("2. Transcribe existing audio file")
    print("3. Live speech recognition")
    print("4. Batch transcribe folder")
    print("5. Show requirements")
    print("0. Exit")
    print("-" * 50)
    
    while True:
        try:
            choice = input("\n📝 Select option (0-5): ").strip()
            
            if choice == '1':
                # Record and transcribe
                filename = input("📁 Enter recording filename (default: recording.wav): ").strip()
                if not filename:
                    filename = "recording.wav"
                
                audio_file = record_audio(filename)
                text = transcribe_audio_file(audio_file)
                
                print(f"\n📝 Transcription:\n{text}")
                
                save_choice = input("\n💾 Save to text file? (y/n): ").strip().lower()
                if save_choice == 'y':
                    save_transcription_to_file(text)
            
            elif choice == '2':
                # Transcribe existing file
                file_path = input("📁 Enter audio file path: ").strip()
                if os.path.exists(file_path):
                    text = transcribe_audio_file(file_path)
                    print(f"\n📝 Transcription:\n{text}")
                    
                    save_choice = input("\n💾 Save to text file? (y/n): ").strip().lower()
                    if save_choice == 'y':
                        save_transcription_to_file(text)
                else:
                    print("❌ File not found!")
            
            elif choice == '3':
                # Live transcription
                duration = input("⏱️  Enter listening duration in seconds (default: 5): ").strip()
                duration = int(duration) if duration.isdigit() else 5
                
                text = live_transcribe(duration)
                print(f"\n📝 Transcription:\n{text}")
                
                save_choice = input("\n💾 Save to text file? (y/n): ").strip().lower()
                if save_choice == 'y':
                    save_transcription_to_file(text)
            
            elif choice == '4':
                # Batch transcribe folder
                folder_path = input("📁 Enter folder path: ").strip()
                output_file = input("📁 Enter output filename (default: batch_transcriptions.txt): ").strip()
                if not output_file:
                    output_file = "batch_transcriptions.txt"
                
                batch_transcribe_folder(folder_path, output_file)
            
            elif choice == '5':
                # Show requirements
                install_requirements()
            
            elif choice == '0':
                print("👋 Goodbye!")
                break
            
            else:
                print("❌ Invalid option. Please try again.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# Quick usage examples for direct function calls
def quick_examples():
    """Example usage without menu"""
    
    # Example 1: Record and transcribe
    print("Example 1: Recording audio...")
    audio_file = record_audio("recorded_audio\audio_chunk_20250920_145217_0001.wav")
    text = transcribe_audio_file(audio_file)
    save_transcription_to_file(text, "my_transcription.txt")
    
    # Example 2: Transcribe existing file
    print("Example 2: Transcribing existing file...")
    # text = transcribe_audio_file("existing_audio.wav")
    # print(text)
    
    # Example 3: Live transcription
    print("Example 3: Live transcription...")
    # text = live_transcribe(duration=10)
    # save_transcription_to_file(text)
    
    # Example 4: Batch processing
    print("Example 4: Batch processing...")
    # batch_transcribe_folder("./audio_files/", "all_transcriptions.txt")

if __name__ == "__main__":
    main_menu()