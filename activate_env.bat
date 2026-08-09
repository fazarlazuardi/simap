@echo off
echo ===========================================
echo Penyiapan Virtual Environment C:\Apps\simap\env
echo ===========================================
cd /d C:\Apps\simap
python create_env.py
call env\Scripts\activate
echo Virtual environment SIMAP aktif!
pause
