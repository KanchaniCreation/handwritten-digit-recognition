#!/usr/bin/env bash
# Builds (if needed) and starts the Swing client. Needs JDK 11+ (Maven optional).
cd "$(dirname "$0")/client"
mkdir -p target/classes
javac -d target/classes src/main/java/com/kanchani/digit/*.java && \
java -cp target/classes com.kanchani.digit.MainApp
