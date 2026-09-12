' sessiz_dinleme_baslat.vbs — sessiz_dinleme.py'yi tamamen gizli (konsolsuz,
' penceresiz) calistirir. Baslangic (Startup) klasorune kopyalanip oturum
' acilisinda otomatik tetiklenmesi icin kullanilir (bkz. sessiz_dinleme_kur.vbs).
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\nu\JARVIS"
WshShell.Run """D:\nu\JARVIS\.venv\Scripts\pythonw.exe"" ""D:\nu\JARVIS\sessiz_dinleme.py""", 0, False
