import google.generativeai as genai
from flask import Flask, request, jsonify
from logger import logger
import os


from flask_swagger_ui import get_swaggerui_blueprint

SWAGGER_URL = '/docs'
API_URL = '/static/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Expense Classifier API"}
)


genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")

logger.info(f"GEMINI_API_KEY found: {bool(os.getenv('GEMINI_API_KEY'))}")
logger.info(f"LLM_MODEL_NAME: {LLM_MODEL_NAME}")

app = Flask(__name__)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)


def translate_text(text, categories):
    """Your original translation prompt"""
    prompt = f"""
    You are a helpful assistant that translates, clarifies, and categorizes user input for expense tracking.
    The input can be in English or Romanian.

    Task: Determine the language of the input and provide a clear translation in the other language (English ↔ Romanian), then identify the type of expense it represents.

    Original text: "{text}"

    Instructions:
    1. Detect the language of the text.
    2. If the text is in Romanian, translate it to clear English; if it is in English, translate it to clear Romanian.
    3. Convert informal or ambiguous expressions into proper, understandable language.
    4. Identify the type of expense (e.g., food, transport, office supplies, utilities, etc.).
    5. Preserve any mentioned amounts or numbers.
    6. Keep the meaning and context intact.

    Respond in the following format:
    - Translation: "<translated text>"
    - Expense type: "<expense category>"
    """
    
    try:
        logger.debug("Initializing translation model...")
        model = genai.GenerativeModel(model_name=LLM_MODEL_NAME)
        response = model.generate_content(prompt)
        logger.info(f"Translation response received: {response.text[:100]}...")  # log first 100 chars
        return {"translated_text": response.text.strip(), "status": "success"}
    except Exception as e:
        logger.exception("Error in translate_text")
        return {"translated_text": text, "status": "error", "error": str(e)}

def classify_expense(translated_text, categories):
    """Your original classification prompt"""
    prompt = f"""
    You are an expense classification assistant.
    
    Expense description: "{translated_text}"
    Available categories: {categories}
    
    Task: Classify this expense into the most appropriate category from the list.
    
    Rules:
    1. Choose only from the provided categories
    2. Consider the context and nature of the expense
    3. If uncertain between categories, choose the most likely one
    4. Respond with only the category name (exactly as provided in the list)
    
    Category:
    """
    
    try:
        logger.debug("Initializing classification model...")
        model = genai.GenerativeModel(model_name=LLM_MODEL_NAME)
        response = model.generate_content(prompt)
        predicted = response.text.strip().lower()
        logger.info(f"Classification raw prediction: {predicted}")
        
        # Find matching category
        for category in categories:
            if category.lower() == predicted or predicted in category.lower():
                logger.info(f"Matched category: {category}")
                return {"category": category, "status": "success"}
        
        logger.warning("No exact match found, falling back to first category")
        return {"category": categories[0], "status": "success"}  # fallback
    except Exception as e:
        logger.exception("Error in classify_expense")
        return {"category": categories[0], "status": "error", "error": str(e)}

@app.route('/classify-expense', methods=['POST'])
def classify():
    """Main endpoint"""
    data = request.get_json()
    logger.debug(f"Incoming request data: {data}")
    
    text = data.get('text', '').strip()
    categories = data.get('categories', [])
    
    if not text or not categories:
        logger.error("Missing text or categories in request")
        return jsonify({"error": "Missing text or categories"}), 400
    
    # Step 1: Translate
    translation = translate_text(text, categories)
    if translation['status'] == 'error':
        logger.error(f"Translation failed: {translation['error']}")
        return jsonify({"error": "Translation failed", "details": translation['error']}), 500
    
    # Step 2: Classify
    classification = classify_expense(translation['translated_text'], categories)
    if classification['status'] == 'error':
        logger.error(f"Classification failed: {classification['error']}")
        return jsonify({"error": "Classification failed", "details": classification['error']}), 500
    
    result = {
        "original_text": text,
        "translated_text": translation['translated_text'],
        "predicted_category": classification['category'],
        "status": "success"
    }
    logger.info(f"Final result: {result}")
    return jsonify(result)

@app.route('/', methods=['GET'])
def home():
    logger.debug("Health check called")
    return jsonify({"status": "running"})

def test():
    """Simple test function"""
    test_data = {
        "categories": ["going out", "house expense", "groceries"],
        "text": "Way brat azi am cheltuit 500 di lei pi ciupaciupsuri"
    }
    
    logger.info(f"Running test with: {test_data['text']}")
    
    translation = translate_text(test_data['text'], test_data['categories'])
    logger.info(f"Test Translation: {translation}")
    
    if translation['status'] == 'success':
        classification = classify_expense(translation['translated_text'], test_data['categories'])
        logger.info(f"Test Classification: {classification}")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test()
    else:
        logger.info("Starting Flask server on port 5000")
        app.run(debug=True, port=5000)
