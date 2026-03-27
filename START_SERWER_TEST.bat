@echo off
echo ==========================================
echo   TEST PLATNOSCI - SERWER HTTP
echo ==========================================
echo.
echo Uruchamiam serwer na porcie 3000...
echo.
echo KROK 1: Serwer startuje
echo KROK 2: Otworz przegladarke: http://localhost:3000/test_platnosci.html
echo.
echo WAZNE: NIE zamykaj tego okna podczas testow!
echo.
echo ==========================================
echo.
cd travel-planner-backend
python -m http.server 3000
pause
