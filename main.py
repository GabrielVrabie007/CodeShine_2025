import requests
import pyaudio
import wave
import threading
import time
import os
from io import BytesIO
from datetime import datetime

# Configurare audio optimizată pentru ElevenLabs
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # ElevenLabs preferă 16kHz
RECORD_SECONDS = 8  # Chunks mai mici pentru răspuns mai rapid

# Configurare salvare
SAVE_AUDIO = True
AUDIO_FOLDER = "recorded_audio"
TRANSCRIPTS_FOLDER = "transcripts"
COMBINED_TRANSCRIPT_FILE = "full_conversation.txt"

# Variabile globale
is_recording = False
audio_interface = None
audio_counter = 0
session_start_time = None

def create_folders():
    """Creează folderele necesare"""
    folders = [AUDIO_FOLDER, TRANSCRIPTS_FOLDER]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Folder creat: {folder}")

def save_audio_chunk(audio_data, chunk_number):
    """Salvează un chunk de audio pe disk"""
    if not SAVE_AUDIO:
        return None
    
    try:
        # Nume fișier cu timestamp și număr chunk
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_chunk_{timestamp}_{chunk_number:04d}.wav"
        filepath = os.path.join(AUDIO_FOLDER, filename)
        
        # Salvează fișierul WAV
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio_interface.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(audio_data))
        
        print(f"💾 Audio salvat: {filename}")
        return filepath
        
    except Exception as e:
        print(f"❌ Eroare la salvarea audio: {e}")
        return None

def save_individual_transcript(text, chunk_number, timestamp_str):
    """Salvează transcripția individuală"""
    try:
        filename = f"transcript_{timestamp_str}_{chunk_number:04d}.txt"
        filepath = os.path.join(TRANSCRIPTS_FOLDER, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Chunk #{chunk_number}\n")
            f.write(f"Timestamp: {timestamp_str}\n")
            f.write(f"Durată: {RECORD_SECONDS}s\n")
            f.write("-" * 40 + "\n")
            f.write(text)
        
        print(f"📝 Transcripție individuală: {filename}")
        return filepath
        
    except Exception as e:
        print(f"❌ Eroare salvare transcripție: {e}")
        return None

def append_to_combined_transcript(text, chunk_number):
    """Adaugă la transcripția combinată"""
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        filepath = os.path.join(TRANSCRIPTS_FOLDER, COMBINED_TRANSCRIPT_FILE)
        
        # Dacă e primul chunk din sesiune, adaugă header
        if chunk_number == 1:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"SESIUNE NOUĂ - {session_start_time}\n")
                f.write(f"{'='*60}\n\n")
        
        # Adaugă transcripția
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {text}\n")
        
        print(f"📋 Adăugat la conversația completă")
        
    except Exception as e:
        print(f"❌ Eroare la transcripția combinată: {e}")

def test_api_key(api_key):
    """Testează validitatea cheii API cu headerele corecte pentru ElevenLabs"""
    try:
        print("🔍 Testez cheia API ElevenLabs...")
        
        # Test cu endpoint-ul de user info - cel mai simplu test
        user_url = "https://api.elevenlabs.io/v1/user"
        headers = {
            "xi-api-key": api_key
        }
        
        print("🔗 Testez accesul de bază...")
        response = requests.get(user_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Acces validat pentru utilizatorul: {user_data.get('email', 'N/A')}")
        else:
            print(f"⚠️ Status neașteptat pentru user info: {response.status_code}")
            print(f"📝 Răspuns: {response.text}")
        
        # Testează Speech-to-Text cu headerele corecte
        print("🎤 Testez Speech-to-Text...")
        stt_url = "https://api.elevenlabs.io/v1/speech-to-text"
        
        # Headerele TREBUIE să fie doar xi-api-key pentru multipart/form-data
        stt_headers = {
            "xi-api-key": api_key
        }
        
        # Creează un fișier audio de test valid
        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # Audio silence de 0.5 secunde
            silence_duration = 0.5
            silence_frames = b'\x00\x00' * int(16000 * silence_duration)
            wf.writeframes(silence_frames)
        
        wav_buffer.seek(0)
        
        files = {
            'audio': ('test.wav', wav_buffer.getvalue(), 'audio/wav')
        }
        
        response = requests.post(stt_url, headers=stt_headers, files=files, timeout=15)
        
        print(f"📊 Status STT: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Cheia API funcționează perfect pentru Speech-to-Text!")
            return True
        elif response.status_code == 401:
            print("❌ Cheia API nu are permisiuni pentru Speech-to-Text")
            print("💡 Verifică că ai activat Speech-to-Text în dashboard-ul ElevenLabs")
            print(f"📝 Răspuns: {response.text}")
            return False
        elif response.status_code == 402:
            print("❌ Contul nu are credite suficiente")
            print(f"📝 Răspuns: {response.text}")
            return False
        elif response.status_code == 422:
            print("✅ Cheia API este validă! (Audio de test a fost respins, dar cheia funcționează)")
            return True
        elif response.status_code == 429:
            print("⚠️ Rate limit temporar, dar cheia pare validă")
            return True
        else:
            print(f"❌ Eroare neașteptată STT: {response.status_code}")
            print(f"📝 Răspuns complet: {response.text}")
            print(f"📝 Headers trimise: {stt_headers}")
            return False
            
    except requests.exceptions.Timeout:
        print("⏰ Timeout la testarea API - încearcă din nou")
        return False
    except Exception as e:
        print(f"❌ Eroare la testarea API: {e}")
        return False

def transcribe_audio(api_key, audio_data, chunk_number):
    """Trimite audio la ElevenLabs pentru transcripție optimizată"""
    print(f"🎯 TRANSCRIBE #{chunk_number}: Început transcripție")
    
    try:
        # Verifică dimensiunea audio
        audio_bytes = b''.join(audio_data)
        print(f"📏 TRANSCRIBE #{chunk_number}: Audio bytes: {len(audio_bytes)}")
        
        if len(audio_bytes) < 1000:  # Redus de la 2000
            print(f"⚠️ TRANSCRIBE #{chunk_number}: Audio prea scurt ({len(audio_bytes)} bytes), dar încerc oricum")
            # Nu returnam None, continuăm pentru debugging
        
        # Salvează audio-ul local
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"💾 TRANSCRIBE #{chunk_number}: Salvez audio local...")
        saved_file = save_audio_chunk(audio_data, chunk_number)
        
        if saved_file:
            print(f"✅ TRANSCRIBE #{chunk_number}: Audio salvat: {saved_file}")
        else:
            print(f"❌ TRANSCRIBE #{chunk_number}: Eșec salvare audio")
        
        # Creează WAV optimizat pentru ElevenLabs
        print(f"🔧 TRANSCRIBE #{chunk_number}: Creez WAV buffer...")
        wav_buffer = BytesIO()
        with wave.open(wav_buffer, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio_interface.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(audio_bytes)
        
        wav_buffer.seek(0)
        file_size = len(wav_buffer.getvalue())
        print(f"📊 TRANSCRIBE #{chunk_number}: WAV size: {file_size} bytes")
        
        # Request către ElevenLabs cu headerele corecte
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {
            "xi-api-key": api_key
        }
        
        files = {
            'audio': ('audio.wav', wav_buffer.getvalue(), 'audio/wav')
        }
        
        print(f"🔗 TRANSCRIBE #{chunk_number}: Trimit request la ElevenLabs...")
        response = requests.post(url, headers=headers, files=files, timeout=30)
        
        print(f"📡 TRANSCRIBE #{chunk_number}: Status response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            text = result.get('text', '').strip()
            
            print(f"📝 TRANSCRIBE #{chunk_number}: Raw text: '{text}'")
            
            if text and len(text) > 0:
                print(f"🎤 #{chunk_number}: {text}")
                
                # Salvează transcripția individuală
                print(f"💾 TRANSCRIBE #{chunk_number}: Salvez transcripția individuală...")
                save_individual_transcript(text, chunk_number, timestamp_str)
                
                # Adaugă la transcripția combinată
                print(f"📋 TRANSCRIBE #{chunk_number}: Adaug la transcripția combinată...")
                append_to_combined_transcript(text, chunk_number)
                
                return text
            else:
                print(f"🔇 #{chunk_number}: Response empty sau whitespace only")
                return None
                
        elif response.status_code == 422:
            print(f"❌ #{chunk_number}: Format audio problematic (422)")
            print(f"📝 Response text: {response.text}")
        elif response.status_code == 429:
            print(f"⏳ #{chunk_number}: Rate limit - așteaptă...")
            time.sleep(3)
        elif response.status_code == 402:
            print(f"💳 #{chunk_number}: Credite insuficiente!")
            return None
        elif response.status_code == 401:
            print(f"🔑 #{chunk_number}: Problemă autentificare!")
            print(f"📝 Response: {response.text}")
            return None
        else:
            print(f"❌ #{chunk_number}: Eroare {response.status_code}")
            print(f"📝 Response text: {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"⏰ #{chunk_number}: Timeout la transcripție")
    except Exception as e:
        print(f"❌ #{chunk_number}: Eroare transcripție: {e}")
        import traceback
        traceback.print_exc()
    
    return None

def record_audio_chunk():
    """Înregistrează un chunk de audio cu detectare de zgomot"""
    global is_recording, audio_interface
    
    try:
        stream = audio_interface.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        frames = []
        peak_level = 0
        chunks_to_read = int(RATE / CHUNK * RECORD_SECONDS)
        
        print(f"🎤 Înregistrez {chunks_to_read} chunks pentru {RECORD_SECONDS}s...")
        
        for i in range(chunks_to_read):
            if not is_recording:
                print("🛑 Înregistrarea a fost oprită")
                break
                
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                
                # Calculează nivelul de zgomot pentru această bucată
                import struct
                chunk_data = struct.unpack(f'{len(data)//2}h', data)
                chunk_peak = max(abs(x) for x in chunk_data) if chunk_data else 0
                peak_level = max(peak_level, chunk_peak)
                
                # Progress indicator
                if i % 10 == 0:
                    print(f"📊 Chunk {i}/{chunks_to_read}, nivel: {chunk_peak}")
                    
            except Exception as read_error:
                print(f"❌ Eroare la citirea chunk-ului {i}: {read_error}")
                break
        
        stream.stop_stream()
        stream.close()
        
        print(f"🔊 Înregistrare completă. Nivel maxim: {peak_level}")
        
        # Threshold mai mic pentru a nu pierde speech-ul
        if peak_level < 300:  # Threshold redus
            print(f"🔇 Audio prea silențios (nivel: {peak_level}), dar îl procesez oricum pentru test")
            # Nu returnez None, ci procesez oricum pentru debugging
        
        return frames
        
    except Exception as e:
        print(f"❌ Eroare la înregistrare: {e}")
        import traceback
        traceback.print_exc()
        return None

def process_audio_chunk(api_key, audio_chunk, chunk_number):
    """Procesează un chunk de audio în thread separat cu debugging"""
    print(f"🧵 THREAD #{chunk_number}: Început procesare")
    
    try:
        if not audio_chunk or len(audio_chunk) == 0:
            print(f"❌ THREAD #{chunk_number}: Audio chunk gol!")
            return
            
        print(f"✅ THREAD #{chunk_number}: Audio chunk valid, lansez transcripția")
        result = transcribe_audio(api_key, audio_chunk, chunk_number)
        
        if result:
            print(f"🎉 THREAD #{chunk_number}: Transcripție reușită!")
        else:
            print(f"🔇 THREAD #{chunk_number}: Fără transcripție")
            
    except Exception as e:
        print(f"❌ THREAD #{chunk_number}: Eroare în procesare: {e}")
        import traceback
        traceback.print_exc()

def start_real_time_recording(api_key):
    """Începe înregistrarea în timp real cu transcripție continuă"""
    global is_recording, audio_interface, audio_counter, session_start_time
    
    session_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("🎤 Începe înregistrarea în timp real...")
    print("📢 Vorbește în microfon. Apasă Ctrl+C pentru a opri.")
    print(f"⏱️  Procesez audio la fiecare {RECORD_SECONDS} secunde")
    if SAVE_AUDIO:
        print(f"💾 Fișierele se salvează în: {AUDIO_FOLDER}/ și {TRANSCRIPTS_FOLDER}/")
    print("-" * 60)
    print("ℹ️  IMPORTANT: Lasă programul să ruleze și vorbește continuu!")
    print("-" * 60)
    
    is_recording = True
    audio_counter = 0
    
    try:
        print("🚀 Începem bucla de înregistrare...")
        consecutive_empty = 0
        
        while is_recording:
            print(f"\n📡 === CICLU {audio_counter + 1} ===")
            
            # Înregistrează un chunk de audio
            audio_chunk = record_audio_chunk()
            
            if audio_chunk and len(audio_chunk) > 0:
                audio_counter += 1
                consecutive_empty = 0
                print(f"✅ Audio chunk #{audio_counter} înregistrat cu succes!")
                print(f"📦 Dimensiune chunk: {len(audio_chunk)} frame-uri")
                
                # Procesează transcripția într-un thread separat
                print(f"🔄 Lansez thread pentru transcripția chunk-ului #{audio_counter}")
                thread = threading.Thread(
                    target=process_audio_chunk,
                    args=(api_key, audio_chunk, audio_counter),
                    daemon=True
                )
                thread.start()
                
                # Așteaptă puțin să se proceseze
                print("⏳ Așteaptă procesarea...")
                time.sleep(1)
                
            else:
                consecutive_empty += 1
                print(f"❌ Chunk gol #{consecutive_empty}")
                
                if consecutive_empty >= 5:
                    print("⚠️ Prea multe chunk-uri goale consecutive")
                    print("💡 Verifică dacă microfonul funcționează și vorbește mai tare")
                    consecutive_empty = 0  # Reset counter
            
            # Pauză scurtă pentru performanță
            print("💤 Pauză scurtă...")
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n🛑 Oprire înregistrare prin Ctrl+C...")
        stop_recording()
    except Exception as e:
        print(f"\n❌ Eroare în bucla principală: {e}")
        import traceback
        traceback.print_exc()
        stop_recording()

def stop_recording():
    """Oprește înregistrarea și afișează statistici"""
    global is_recording, audio_interface
    
    is_recording = False
    if audio_interface:
        audio_interface.terminate()
    
    # Finalizează transcripția combinată
    try:
        filepath = os.path.join(TRANSCRIPTS_FOLDER, COMBINED_TRANSCRIPT_FILE)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"SESIUNE ÎNCHEIATĂ - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*60}\n\n")
    except:
        pass
    
    print("✅ Înregistrarea s-a oprit.")

def check_microphone():
    """Verifică microfonul cu test de zgomot"""
    try:
        audio = pyaudio.PyAudio()
        
        # Test mai detaliat
        stream = audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        print("🎤 Testez microfonul... vorbește ceva!")
        
        # Testează 2 secunde
        max_level = 0
        for _ in range(20):  # 20 * 0.1s = 2s
            data = stream.read(CHUNK, exception_on_overflow=False)
            
            import struct
            chunk_data = struct.unpack(f'{len(data)//2}h', data)
            level = max(abs(x) for x in chunk_data) if chunk_data else 0
            max_level = max(max_level, level)
            time.sleep(0.1)
        
        stream.close()
        audio.terminate()
        
        if max_level > 1000:
            print(f"✅ Microfonul funcționează! Nivel maxim: {max_level}")
            return True
        else:
            print(f"⚠️ Microfonul pare silențios. Nivel maxim: {max_level}")
            print("💡 Verifică volumul microfonului și permisiunile")
            return True  # Permitem să continue
        
    except Exception as e:
        print(f"❌ Eroare microfon: {e}")
        return False

def main():
    """Funcția principală optimizată"""
    global audio_interface

    # Setează cheia API
    API_KEY = os.getenv('ELEVENLABS_API_KEY', "sk_998ae6de9aa2d56d017f56cfbf881aa48834c22b8ae90de4")
    
    if not API_KEY:
        print("⚠️ Setează cheia API ElevenLabs!")
        print("export ELEVENLABS_API_KEY='cheia-ta'")
        return
    
    print("🚀 ElevenLabs Real-Time Speech-to-Text OPTIMIZAT")
    print("=" * 60)
    
    # Creează folderele
    create_folders()
    
    # Afișează configurația
    print(f"🎵 Audio: {RATE}Hz, {CHANNELS} canal, chunks de {RECORD_SECONDS}s")
    print(f"💾 Salvare: Audio={SAVE_AUDIO}")
    print(f"📁 Foldere: {AUDIO_FOLDER}/ și {TRANSCRIPTS_FOLDER}/")
    
    # Verifică microfonul
    if not check_microphone():
        return
    
    # Inițializează PyAudio
    audio_interface = pyaudio.PyAudio()
    
    # Testează cheia API
    if not test_api_key(API_KEY):
        audio_interface.terminate()
        return
    
    print("\n" + "=" * 60)
    print("🎯 Gata de înregistrare! Transcripțiile vor apărea în timp real.")
    print("=" * 60)
    
    try:
        # Începe înregistrarea în timp real
        start_real_time_recording(API_KEY)
        
    except KeyboardInterrupt:
        print("\n🛑 Programul a fost oprit de utilizator.")
    except Exception as e:
        print(f"❌ Eroare neașteptată: {e}")
    finally:
        stop_recording()
        
        # Afișează statistici finale
        print(f"\n📊 Statistici finale:")
        print(f"   • Total chunks procesate: {audio_counter}")
        if SAVE_AUDIO and audio_counter > 0:
            print(f"   • Fișiere audio: {os.path.abspath(AUDIO_FOLDER)}/")
            print(f"   • Transcripții: {os.path.abspath(TRANSCRIPTS_FOLDER)}/")
            print(f"   • Conversație completă: {os.path.join(TRANSCRIPTS_FOLDER, COMBINED_TRANSCRIPT_FILE)}")

if __name__ == "__main__":
    main()