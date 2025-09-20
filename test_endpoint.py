import requests
import json

def check_server():
    """Check if server is running"""
    try:
        response = requests.get("http://localhost:5000/")
        if response.status_code == 200:
            print("✅ Server is running!")
            print(response.json())
            return True
        else:
            print(f"❌ Server responded with status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        print("💡 Start server with: python app.py")
        return False

def test_api():
    """Test the API endpoint"""
    url = "http://localhost:5000/classify-expense"
    
    test_data = {
        "categories": ["going out", "house expense", "groceries"],
        "text": "Way brat azi am cheltuit 500 di lei pi ciupaciupsuri"
    }
    
    print("🧪 Testing expense classification...")
    print(f"📝 Input: {test_data['text']}")
    
    try:
        response = requests.post(url, json=test_data)
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"🔤 Translated: {result['translated_text']}")
            print(f"🏷️  Category: {result['predicted_category']}")
        else:
            print(f"❌ ERROR: Status {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    if check_server():
        test_api()
    else:
        print("\n💡 To start the server:")
        print("python app.py")