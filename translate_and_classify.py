from logger import logger
import google.generativeai as genai
import os


LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME")

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
        logger.info(f"Translation response received: {response.text[:100]}...")  
        return {"translated_text": response.text.strip(), "status": "success"}
    except Exception as e:
        logger.exception("Error in translate_text")
        return {"translated_text": text, "status": "error", "error": str(e)}

def classify_expense(translated_text, categories):
    """
    Classify expense and extract items with their amounts into a structured list.
    """
    
    # Input validation
    if not translated_text or not translated_text.strip():
        logger.warning("Empty or whitespace-only translated_text provided")
        return []
    
    if not categories:
        logger.warning("No categories provided")
        return []
    
    # Clean the text
    translated_text = translated_text.strip()
    logger.info(f"Processing text for classification: '{translated_text}'")
    
    prompt = f"""
    You are an expense classification assistant.

    Expense description: "{translated_text}"
    Available categories: {categories}

    Task:
    1. Classify each individual expense into the most appropriate category from the list.
    2. Extract all monetary amounts and the corresponding items purchased.
    3. If no specific amount is mentioned, use 0 as the amount.
    4. If no specific item is mentioned, extract the general expense description.

    Rules:
    - Choose only from the provided categories: {categories}
    - Provide amounts as numbers (no currency symbols)
    - Return ONLY a valid JSON array, no markdown formatting, no code blocks, no additional text
    - If the text doesn't seem like an expense, still try to extract something meaningful
    - Always return at least one item in the array

    Respond strictly in this JSON format:
    [
        {{
            "category": "category_from_list",
            "item": "description_of_item_or_expense",
            "amount": 0
        }}
    ]

    IMPORTANT: Return only the JSON array above, no ```json``` markers, no explanations.
    """

    try:
        logger.debug("Initializing classification and extraction model...")
        model = genai.GenerativeModel(model_name=LLM_MODEL_NAME)
        response = model.generate_content(prompt)
        
        raw_response = response.text.strip()
        logger.info(f"Raw model response: '{raw_response}'")

        # Clean up the response - remove code block markers if present
        if raw_response.startswith('```json'):
            raw_response = raw_response.replace('```json', '').replace('```', '').strip()
        elif raw_response.startswith('```'):
            raw_response = raw_response.replace('```', '').strip()

        # Parse JSON safely
        import json
        try:
            result_list = json.loads(raw_response)
            logger.info(f"Parsed JSON successfully: {result_list}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse model output as JSON: {e}")
            logger.warning(f"Raw response was: '{raw_response}'")
            
            # Fallback: create a basic classification
            fallback_result = [{
                "category": categories[0],
                "item": translated_text[:50],  # First 50 chars
                "amount": 0
            }]
            logger.info(f"Using fallback result: {fallback_result}")
            return fallback_result

        # Validate that we got a list
        if not isinstance(result_list, list):
            logger.warning(f"Expected list but got {type(result_list)}")
            return [{
                "category": categories[0],
                "item": translated_text[:50],
                "amount": 0
            }]

        # Ensure we have at least one item
        if not result_list:
            logger.warning("Model returned empty list")
            return [{
                "category": categories[0],
                "item": translated_text[:50],
                "amount": 0
            }]

        # Clean up and validate each entry
        cleaned_results = []
        for entry in result_list:
            if not isinstance(entry, dict):
                continue
                
            # Ensure required fields exist
            category = entry.get("category", categories[0])
            item = entry.get("item", translated_text[:50])
            amount = entry.get("amount", 0)
            
            # Validate category is from the list
            category_found = False
            for valid_category in categories:
                if (category.lower() == valid_category.lower() or 
                    category.lower() in valid_category.lower() or
                    valid_category.lower() in category.lower()):
                    category = valid_category
                    category_found = True
                    break
            
            if not category_found:
                category = categories[0]  # Default to first category
            
            # Ensure amount is numeric
            try:
                amount = float(amount)
            except (ValueError, TypeError):
                amount = 0
                
            cleaned_results.append({
                "category": category,
                "item": str(item),
                "amount": amount
            })

        logger.info(f"Final cleaned results: {cleaned_results}")
        return cleaned_results if cleaned_results else [{
            "category": categories[0],
            "item": translated_text[:50],
            "amount": 0
        }]

    except Exception as e:
        logger.exception("Error in classify_expense")
        # Return a fallback result instead of error
        fallback_result = [{
            "category": categories[0], 
            "item": translated_text[:50] if translated_text else "unknown expense", 
            "amount": 0, 
            "error": str(e)
        }]
        logger.info(f"Exception fallback result: {fallback_result}")
        return fallback_result