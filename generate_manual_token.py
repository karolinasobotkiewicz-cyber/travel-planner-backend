"""
Generate JWT token manually using PyJWT
"""
import jwt
import datetime
import uuid

# Supabase JWT Secret
JWT_SECRET = "pvaAG1JoRNPiJf7ySWPJVnNOn4NfT4MiIOXAuIUgZdYrgYlSphNzqhkfuvelA5KLUG+O5gKoZNok1wn2uJ6DaA=="

# Create JWT payload (simulating Supabase user)
user_id = str(uuid.uuid4())
now = datetime.datetime.now(datetime.timezone.utc)
exp = now + datetime.timedelta(hours=2)  # 2 hours from now

payload = {
    "aud": "authenticated",
    "exp": int(exp.timestamp()),
    "iat": int(now.timestamp()),
    "iss": "https://usztzcigcnsyyatguxay.supabase.co/auth/v1",
    "sub": user_id,
    "email": "manual.test@travelplanner.pl",
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

print("🔐 TOKEN JWT WYGENEROWANY (RĘCZNIE)!\n")
print("User ID:", user_id)
print("Email:", payload["email"])
print("Wygasa za:", "1 godzinę")
print("\n" + "=" * 80)
print(token)
print("=" * 80)
print("\n💡 Skopiuj powyższy token i wklej do test_platnosci.html")
print("⏱️ Token ważny przez: ~1 godzinę\n")
