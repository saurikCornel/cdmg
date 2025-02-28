#!/bin/bash

# Параметры
BUNDLE_ID="com.gmsllani.games"
APPLE_ID="6742645706"
REMOTE_URL="git@github.com:saurikCornel/Ilani-Games.git"
PROJECT_NAME="Ilani Games"
SCHEME_NAME="project"

# Создание codemagic.yml
cat <<EOL > codemagic.yml
workflows:
    ios-workflow:
      name: iOS Workflow
      environment:
        groups:
          - app_store_credentials # <-- (APP_STORE_CONNECT_ISSUER_ID, APP_STORE_CONNECT_KEY_IDENTIFIER, APP_STORE_CONNECT_PRIVATE_KEY)
          - certificate_credentials # <-- (CERTIFICATE_PRIVATE_KEY)
        vars:
          XCODE_PROJECT: "$PROJECT_NAME.xcodeproj"
          XCODE_SCHEME: "$SCHEME_NAME"
          BUNDLE_ID: "$BUNDLE_ID"
          APP_STORE_APPLE_ID: $APPLE_ID
        xcode: latest
        cocoapods: default
      triggering:
        events:
          - push
          - tag
          - pull_request
        branch_patterns:
          - pattern: 'develop'
            include: true
            source: true
      scripts:
        - name: Set up keychain
          script: keychain initialize
        - name: Fetch signing files
          script: app-store-connect fetch-signing-files \$BUNDLE_ID --type IOS_APP_STORE --platform=IOS --create --certificate-key-password='700700'
        - name: Use system default keychain
          script: keychain add-certificates
        - name: Set up code signing
          script: xcode-project use-profiles
        - name: Increment build number
          script: agvtool new-version -all \$((\$(app-store-connect get-latest-testflight-build-number "\$APP_STORE_APPLE_ID") + 1))
        - name: Build ipa
          script: xcode-project build-ipa --project "\$XCODE_PROJECT" --scheme "\$XCODE_SCHEME"
      artifacts:
        - build/ios/ipa/*.ipa
        - \$HOME/Library/Developer/Xcode/DerivedData/**/Build/**/*.dSYM
      publishing:
        app_store_connect:
            api_key: \$APP_STORE_CONNECT_PRIVATE_KEY
            key_id: \$APP_STORE_CONNECT_KEY_IDENTIFIER
            issuer_id: \$APP_STORE_CONNECT_ISSUER_ID
            submit_to_testflight: true
        email:
            recipients:
              - someEmail@rmail.com
            notify:
              success: true
              failure: true
        slack:
            channel: '#builds'
            notify_on_build_start: true
            notify:
              success: false
              failure: false
EOL

# Инициализация Git
git init
git checkout -b main
git add .
git commit -m "Initial commit with codemagic.yml"
git remote add origin "$REMOTE_URL"
git push -u origin main

echo "Codemagic.yml created, Git initialized, and pushed."
