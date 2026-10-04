#!/bin/sh
# Start the local Paper server. Java 25 from Homebrew; 2 GB heap is plenty for a flat arena world.
cd "$(dirname "$0")"
exec /opt/homebrew/opt/openjdk@25/bin/java -Xms1G -Xmx2G -XX:+UseG1GC -jar paper.jar --nogui
