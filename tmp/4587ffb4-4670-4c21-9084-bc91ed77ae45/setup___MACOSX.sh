#!/bin/bash
BUNDLE_ID="com.gmsllani.games"
APPLE_ID="6742645706"
REMOTE_URL="git@github.com:saurikCornel/Ilani-Games.git"
PROJECT_NAME="__MACOSX"

cat <<EOL > codemagic.yml
workflows:
    ios-workflow:
      name: iOS Workflow
      environment:
        vars:
          BUNDLE_ID: "$BUNDLE_ID"
          APP_STORE_APPLE_ID: "$APPLE_ID"
      scripts:
        - echo "Building $PROJECT_NAME"
EOL

git init
git add .
git commit -m "Initial commit"
git remote add origin "$REMOTE_URL"
git push -u origin main
