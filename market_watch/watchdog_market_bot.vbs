' JARVIS piyasa/finans izleme botu icin baslatma/watchdog scripti - TAMAMEN
' VBScript, konsol penceresi acmaz. JARVIS'ten BAGIMSIZ calisir: JARVIS
' kapali olsa bile bu surec ayakta kalir (bkz. market_watch/monitor.py).
' Windows Gorev Zamanlayici tarafindan periyodik cagrilabilir (oturum
' acilista / crash sonrasi kendini toparlama). Zaten calisiyorsa hicbir sey
' yapmaz (idempotent) - Borsa_botu/watchdog_telegram_gizli.vbs ile ayni desen.

scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
jarvisDir = Left(scriptDir, InStrRev(Left(scriptDir, Len(scriptDir) - 1), "\"))

Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set procs = wmi.ExecQuery("SELECT CommandLine FROM Win32_Process WHERE Name='pythonw.exe'")

alreadyRunning = False
For Each p In procs
    cmd = p.CommandLine
    If InStr(1, cmd, "market_watch", vbTextCompare) > 0 And InStr(1, cmd, "monitor", vbTextCompare) > 0 Then
        alreadyRunning = True
        Exit For
    End If
Next

If Not alreadyRunning Then
    Set WshShell = CreateObject("WScript.Shell")
    WshShell.Environment("Process")("PYTHONIOENCODING") = "utf-8"
    WshShell.Environment("Process")("PYTHONUTF8") = "1"

    pythonwPath = """" & jarvisDir & ".venv\Scripts\pythonw.exe"""
    WshShell.CurrentDirectory = jarvisDir
    WshShell.Run pythonwPath & " -m market_watch.monitor", 0, False
End If
