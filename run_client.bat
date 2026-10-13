@echo off
cd /d "%~dp0client"
if not exist target\classes mkdir target\classes
javac -d target\classes src\main\java\com\kanchani\digit\*.java && java -cp target\classes com.kanchani.digit.MainApp
