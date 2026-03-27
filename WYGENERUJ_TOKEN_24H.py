"""
Generate JWT token with 24 hour expiration for klientka testing
"""
import jwt
import datetime
import uuid

# Supabase JWT Secret
JWT_SECRET = "pvaAG1JoRNPiJf7ySWPJVnNOn4NfT4MiIOXAuIUgZdYrgYlSphNzqhkfuvelA5KLUG+O5gKoZNok1wn2uJ6DaA=="

# Create JWT payload (simulating Supabase user)
user_id = str(uuid.uuid4())
now = datetime.datetime.now(datetime.timezone.utc)
exp = now + datetime.timedelta(hours=24)  # 24 hours validity for testing

payload = {
    "aud": "authenticated",
    "exp": int(exp.timestamp()),
    "iat": int(now.timestamp()),
    "iss": "https://usztzcigcnsyyatguxay.supabase.co/auth/v1",
    "sub": user_id,
    "email": "klientka.test@travelplanner.pl",
    "phone": "",
    "app_metadata": {
        "provider": "email",
        "providers": ["email"]
    },
    "user_metadata": {},
    "role": "authenticated",
    "aal": "aal1",
    "amr": [{"method": "password", "timestamp": int(now.timestamp())}],
    "session_id": str(uuid.uuid4())
}

# Generate JWT token
token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# Format expiration time
exp_time = exp.strftime("%Y-%m-%d %H:%M:%S UTC")

print("=" * 80)
print("🔐 TOKEN JWT DLA KLIENTKI (WAŻNY 24H)")
print("=" * 80)
print()
print(f"📧 Email: {payload['email']}")
print(f"🆔 User ID: {user_id}")
print(f"⏱️  Wygasa: {exp_time}")
print()
print("=" * 80)
print("TOKEN (skopiuj poniższy tekst):")
print("=" * 80)
print(token)
print("=" * 80)
print()
print("💡 INSTRUKCJA:")
print("   1. Skopiuj powyższy token (cała długa linia)")
print("   2. Uruchom START_SERWER_TEST.bat")
print("   3. Otwórz http://localhost:3000/test_platnosci.html")
print("   4. Wklej token w pole 'JWT Token'")
print("   5. Kliknij 'Rozpocznij Test Płatności'")
print()
