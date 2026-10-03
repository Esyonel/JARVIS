' JARVIS otomatik baslatici - Windows oturumu acilinca Jarvis'i konsolsuz baslatir.
Set sh = CreateObject("WScript.Shell")
sh.Environment("PROCESS")("PYTHONUTF8") = "1"
sh.Environment("PROCESS")("PYTHONIOENCODING") = "utf-8"
sh.CurrentDirectory = "D:\programlar\Jarvis"
sh.Run """D:\programlar\Jarvis\.venv\Scripts\pythonw.exe"" ""D:\programlar\Jarvis\main.py""", 1, False
