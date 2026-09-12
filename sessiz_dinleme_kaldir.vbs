' sessiz_dinleme_kaldir.vbs — sessiz_dinleme_kur.vbs ile Baslangic klasorune
' kopyalanan baslaticiyi siler. Cift tiklaninca HICBIR pencere/konsol acmaz.

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

startupDir = shell.SpecialFolders("Startup")
destFile = startupDir & "\JARVIS Gizli Dinleme.vbs"

On Error Resume Next
If fso.FileExists(destFile) Then
    fso.DeleteFile destFile, True
    result = "TAMAM - kaldirildi: " & destFile
Else
    result = "Zaten kurulu degildi."
End If
On Error Goto 0

Set logFile = fso.OpenTextFile("D:\nu\JARVIS\sessiz_dinleme_kurulum.log", 8, True)
logFile.WriteLine Now & " - " & result
logFile.Close
