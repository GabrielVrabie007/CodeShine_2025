import google.generativeai as genai
from flask import Flask, request, jsonify
from logger import logger
import os
from translate_and_classify import classify_expense, translate_text
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS
from elevenlabs.client import ElevenLabs

######## TEST ENDPOINTS IN SWAGGER  #########
SWAGGER_URL = '/docs'
API_URL = '/static/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Expense Classifier API"}
)

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")

elevenlabs_client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))

app = Flask(__name__)
CORS(app)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

DEFAULT_CATEGORIES = ["going out", "house expense", "groceries"]

####### Speech to text endpoint #######
@app.route('/speech-to-text', methods=['POST'])
def speech_to_text():
    """
    Receives audio file from frontend, converts to text using ElevenLabs Scribe,
    then classifies the expense using the existing classify_expense flow.
    """
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files['audio']
    transcript = None

    try:
        # Get categories from form data first
        categories = request.form.getlist('categories')
        if not categories:
            categories = DEFAULT_CATEGORIES
        
        logger.info(f"Processing audio file: {audio_file.filename}")
        logger.info(f"File size: {audio_file.content_length}")
        logger.info(f"Content type: {audio_file.content_type}")

        try:
            # Try ElevenLabs SDK first
            logger.info("Attempting ElevenLabs SDK transcription...")
            
            # Reset file pointer to beginning
            audio_file.seek(0)
            
            transcript_response = elevenlabs_client.speech_to_text.convert(
                file=audio_file,
                model_id="scribe_v1",
                language_code=None,  # Auto-detect
                timestamps_granularity="word",
                diarize=False,  # Simplified - disable speaker detection for now
                tag_audio_events=False,  # Simplified - disable audio events for now
            )
            
            # Extract transcript text
            if hasattr(transcript_response, 'text'):
                transcript = transcript_response.text
            elif hasattr(transcript_response, 'transcript'):
                transcript = transcript_response.transcript
            else:
                transcript = str(transcript_response)
                
            logger.info(f"SDK transcription successful: '{transcript}'")
            
        except Exception as sdk_error:
            logger.error(f"ElevenLabs SDK failed: {sdk_error}")
            
            try:
                # Fallback to direct API call
                logger.info("Attempting direct API call to ElevenLabs...")
                
                # Reset file pointer again
                audio_file.seek(0)
                
                import requests
                
                url = "https://api.elevenlabs.io/v1/speech-to-text"
                headers = {
                    "xi-api-key": os.getenv('ELEVENLABS_API_KEY')
                }
                
                files = {
                    "file": (audio_file.filename, audio_file, audio_file.content_type)
                }
                
                data = {
                    "model_id": "scribe_v1",
                    "timestamps_granularity": "word"
                }
                
                response = requests.post(url, headers=headers, files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    transcript = result.get('text', '')
                    logger.info(f"API transcription successful: '{transcript}'")
                else:
                    logger.error(f"API call failed with status {response.status_code}: {response.text}")
                    raise Exception(f"API call failed: {response.status_code}")
                    
            except Exception as api_error:
                logger.error(f"Direct API call also failed: {api_error}")
                
                # Ultimate fallback - return error but allow manual text input
                return jsonify({
                    "error": "Speech-to-text service unavailable",
                    "details": f"Both SDK and API failed. SDK: {str(sdk_error)}, API: {str(api_error)}",
                    "suggestion": "Please try using the text classification endpoint directly",
                    "fallback_transcript": "Could not transcribe audio"
                }), 500

        # Validate transcript
        if not transcript or not transcript.strip():
            logger.warning("Empty transcript received")
            return jsonify({
                "error": "No speech detected",
                "details": "The audio file did not produce any transcribed text",
                "original_text": "",
                "translated_text": "",
                "classified_items": []
            }), 400

        transcript = transcript.strip()
        logger.info(f"Final transcript: '{transcript}' (length: {len(transcript)})")

        # Step 1: Translate text if needed
        logger.info("Starting translation...")
        translation = translate_text(transcript, categories)
        logger.info(f"Translation result: {translation}")
        
        if translation.get('status') == 'error':
            logger.error(f"Translation failed: {translation.get('error')}")
            return jsonify({
                "error": "Translation failed", 
                "details": translation.get('error'),
                "original_text": transcript,
                "translated_text": "",
                "classified_items": []
            }), 500

        # Step 2: Classify
        translated_text = translation.get('translated_text', transcript)
        logger.info(f"Classifying text: '{translated_text}'")
        
        classification_list = classify_expense(translated_text, categories)
        logger.info(f"Classification result: {classification_list}")

        if not classification_list:
            logger.warning("Classification returned empty list")
            # Create a fallback classification
            classification_list = [{
                "category": categories[0],
                "item": translated_text[:50],
                "amount": 0
            }]

        return jsonify({
            "original_text": transcript,
            "translated_text": translated_text,
            "classified_items": classification_list,
            "status": "success"
        })

    except Exception as e:
        logger.exception("Unexpected error in speech-to-text endpoint")
        return jsonify({
            "error": "Speech processing failed", 
            "details": str(e),
            "original_text": transcript or "",
            "debug_info": {
                "audio_filename": audio_file.filename if audio_file else None,
                "audio_content_type": audio_file.content_type if audio_file else None,
                "has_elevenlabs_key": bool(os.getenv('ELEVENLABS_API_KEY')),
                "categories": categories if 'categories' in locals() else []
            }
        }), 500


# Simple test endpoint to verify ElevenLabs connection
@app.route('/test-elevenlabs', methods=['GET'])
def test_elevenlabs():
    """Test ElevenLabs API connection"""
    try:
        # Test if we can create a client
        client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))
        
        return jsonify({
            "status": "success",
            "message": "ElevenLabs client created successfully",
            "has_api_key": bool(os.getenv('ELEVENLABS_API_KEY'))
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "has_api_key": bool(os.getenv('ELEVENLABS_API_KEY'))
        }), 500


#### CLASSIFY BY CATEGORIES TEXT #####
@app.route('/classify-expense', methods=['POST'])
def classify():
    """Main endpoint"""
    data = request.get_json()
    
    text = data.get('text', '').strip()
    categories = data.get('categories', [])
    
    if not text or not categories:
        return jsonify({"error": "Missing text or categories"}), 400
    
    # Step 1: Translate
    translation = translate_text(text, categories)
    if translation.get('status') == 'error':
        return jsonify({"error": "Translation failed", "details": translation.get('error')}), 500
    
    # Step 2: Classify
    classification_list = classify_expense(translation['translated_text'], categories)
    if not classification_list:
        return jsonify({"error": "Classification failed", "details": "Empty list returned"}), 500
    
    result = {
        "original_text": text,
        "translated_text": translation['translated_text'],
        "classified_items": classification_list,
        "status": "success"
    }
    return jsonify(result)

##### HOME ROUTE #####
@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "running"})

if __name__ == '__main__':
    app.run(debug=True, port=5050)