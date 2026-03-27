"""
Generate JWT token for testing
"""
import requests
import json

# Supabase credentials
SUPABASE_URL = "https://usztzcigcnsyyatguxay.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InVzenR6Y2lnY25zeXlhdGd1eGF5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA4ODgyNjQsImV4cCI6MjA4NjQ2NDI2NH0.wvvsDDS6TW78y-earAmInS-NQKGdY1QY-2ho8QSGRnU"

# Test user credentials  
import random
TEST_EMAIL = f"test{random.randint(1000, 9999)}@travelplanner.pl"
TEST_PASSWORD = "DevTest123!"

print("🔐 Generowanie tokenu JWT z Supabase...\n")
print(f"Email: {TEST_EMAIL}")
print(f"Password: {TEST_PASSWORD}\n")

# Try to sign up first (in case user doesn't exist)
print("📝 Próba utworzenia użytkownika testowego...")
signup_url = f"{SUPABASE_URL}/auth/v1/signup"
headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Content-Type": "application/json"
}
data = {
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD
}

try:
    signup_response = requests.post(signup_url, headers=headers, json=data)
    print(f"Signup status: {signup_response.status_code}")
    print(f"Signup response: {signup_response.text[:500]}\n")
    
    if signup_response.status_code == 200:
        print("✅ Użytkownik utworzony pomyślnie!\n")
        signup_result = signup_response.json()
        if "access_token" in signup_result:
            print("✅ TOKEN JWT OTRZYMANY Z REJESTRACJI!\n")
            print("=" * 80)
            print(signup_result["access_token"])
            print("=" * 80)
            print("\n💡 Skopiuj powyższy token i wklej do test_platnosci.html\n")
            print("⏱️ Token ważny przez: ~1 godzinę")
            exit(0)
    else:
        print(f"⚠️ Użytkownik już istnieje lub inny błąd (próbuję zalogować)\n")
except Exception as e:
    print(f"⚠️ Błąd podczas tworzenia użytkownika: {e}\n")

# Sign in with Supabase Auth API
print("🔑 Logowanie...")
auth_url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Content-Type": "application/json"
}
data = {
    "email": TEST_EMAIL,
    "password": TEST_PASSWORD
}

try:
    response = requests.post(auth_url, headers=headers, json=data)
    response.raise_for_status()
    
    result = response.json()
    access_token = result.get("access_token")
    
    if access_token:
        print("✅ TOKEN JWT WYGENEROWANY!\n")
        print("=" * 80)
        print(access_token)
        print("=" * 80)
        print("\n💡 Skopiuj powyższy token i wklej do test_platnosci.html\n")
        print("⏱️ Token ważny przez: ~1 godzinę")
    else:
        print("❌ Błąd: Brak tokenu w odpowiedzi")
        print(json.dumps(result, indent=2))
        
except requests.exceptions.HTTPError as e:
    print(f"❌ Błąd HTTP: {e}")
    print(f"Response: {e.response.text}")
except Exception as e:
    print(f"❌ Błąd: {e}")
