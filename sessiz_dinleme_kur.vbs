' sessiz_dinleme_kur.vbs — sessiz_dinleme_baslat.vbs'i kullanicinin Baslangic
' (Startup) klasorune kopyalar. Cift tiklaninca HICBIR pencere/konsol acmaz
' (wscript.exe sessizce calisir); sonuc sessiz_dinleme_kurulum.log'a yazilir.
' Kaldirmak icin: sessiz_dinleme_kaldir.vbs

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

srcFile = "D:\nu\JARVIS\sessiz_dinleme_baslat.vbs"
startupDir = shell.SpecialFolders("Startup")
destFile = startupDir & "\JARVIS Gizli Dinleme.vbs"

On Error Resume Next
fso.CopyFile srcFile, destFile, True
If Err.Number = 0 Then
    result = "TAMAM - kuruldu: " & destFile
Else
    result = "HATA - " & Err.Description
End If
On Error Goto 0

Set logFile = fso.OpenTextFile("D:\nu\JARVIS\sessiz_dinleme_kurulum.log", 8, True)
logFile.WriteLine Now & " - " & result
logFile.Close
