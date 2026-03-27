$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzcyMTEwODg3LCJpYXQiOjE3NzIxMDM2ODcsImlzcyI6Imh0dHBzOi8vdXN6dHpjaWdjbnN5eWF0Z3V4YXkuc3VwYWJhc2UuY28vYXV0aC92MSIsInN1YiI6ImNiMWQ5YTBlLWZkZGUtNGY0Mi1hOGE0LTJlMWIyMGI2OGQ2OSIsImVtYWlsIjoibWFudWFsLnRlc3RAdHJhdmVscGxhbm5lci5wbCIsInBob25lIjoiIiwiYXBwX21ldGFkYXRhIjp7InByb3ZpZGVyIjoiZW1haWwiLCJwcm92aWRlcnMiOlsiZW1haWwiXX0sInVzZXJfbWV0YWRhdGEiOnt9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6InBhc3N3b3JkIiwidGltZXN0YW1wIjoxNzcyMTAzNjg3fV0sInNlc3Npb25faWQiOiJkYzk4YzlkZi0wM2M4LTQ0ZTItOWE5Ni03YTEwYjU1NzhjNGYifQ.EohR4oXoiL9hQ6sUo4MCdr7DJ2BcMVV3ju9AgZ7VG8c"

Write-Host "Testing /plan/preview endpoint..." -ForegroundColor Yellow

$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $token"
}

$body = @{
    location = "Kraków"
    groupType = "couple"
    daysCount = 2
    budget = 2
    preferences = @{
        pace = "relaxed"
        interests = @("culture")
    }
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri "https://travel-planner-backend-xbsp.onrender.com/plan/preview" -Method Post -Headers $headers -Body $body -UseBasicParsing
    Write-Host "SUCCESS! Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host $response.Content
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response: $responseBody" -ForegroundColor Red
    }
}
