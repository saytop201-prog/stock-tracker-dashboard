@echo off
cd /d "C:\Users\Jang Won\Documents\antigravity\beautiful-meitner"
echo Starting daily stock tracking...
python naver_tracker.py
python report_tracker.py
python dart_tracker.py
echo Pushing updates to GitHub...
"C:\Program Files\Git\cmd\git.exe" add tracking.db
"C:\Program Files\Git\cmd\git.exe" commit -m "Daily morning update"
"C:\Program Files\Git\cmd\git.exe" push origin main
echo Done!
