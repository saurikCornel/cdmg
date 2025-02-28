import os
import re
import zipfile
import subprocess
import shutil
import uuid
from flask import Flask, request, render_template, send_file, after_this_request, redirect, url_for, flash
from pathlib import Path
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Для flash-сообщений

# Временная директория
TEMP_DIR = "tmp"
os.makedirs(TEMP_DIR, exist_ok=True)

# Регулярные выражения для валидации
uuid_pattern = re.compile(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')
key_id_pattern = re.compile(r'^(?=.*[A-Z])[A-Z0-9]{10}$')
apple_id_pattern = re.compile(r'^\d{10}$')

# Генерация SSH-ключа
def generate_ssh_key(password, request_dir):
    key_file = os.path.join(request_dir, "id_rsa")
    subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "2048", "-m", "PEM", "-f", key_file, "-N", password], check=True)
    with open(key_file, "r") as f:
        private_key = f.read()
    os.remove(key_file)
    os.remove(f"{key_file}.pub")
    return private_key

# Поиск первой схемы в проекте Xcode
def get_first_scheme(project_dir):
    schemes_dir = Path(project_dir) / "xcshareddata" / "xcschemes"
    project_name = os.path.basename(project_dir)
    if not schemes_dir.exists():
        return project_name
    scheme_files = list(schemes_dir.glob("*.xcscheme"))
    if not scheme_files:
        return project_name
    return scheme_files[0].stem

# Создание .sh-скрипта
def create_bash_script(data, project_name, scheme_name, request_dir):
    script_filename = f"setup_{project_name}.sh"
    script_path = os.path.join(request_dir, script_filename)
    with open(script_path, "w") as f:
        f.write(f"""#!/bin/bash

# Параметры
BUNDLE_ID="{data['bundle_id']}"
APPLE_ID="{data['apple_id']}"
REMOTE_URL="{data['remote_url']}"
PROJECT_NAME="{project_name}"
SCHEME_NAME="{scheme_name}"

# Создание codemagic.yaml
cat <<EOL > codemagic.yaml
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
git commit -m "Initial commit with codemagic.yaml"
git remote add origin "$REMOTE_URL"
git push -u origin main

echo "Codemagic.yaml created, Git initialized, and pushed."
""")
    os.chmod(script_path, 0o755)
    return script_filename

# Валидация данных
def validate_data(data):
    errors = []
    if not uuid_pattern.match(data['issuer_id']):
        errors.append("Неверный формат Issuer ID")
    if not key_id_pattern.match(data['key_id']):
        errors.append("Неверный формат Key ID")
    if not apple_id_pattern.match(data['apple_id']):
        errors.append("Неверный формат Apple ID")
    return errors

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Проверка файлов
        project_zip = request.files.get('project_zip')
        p8_file = request.files.get('p8_file')
        if not project_zip or not p8_file:
            flash("Загрузите оба файла!", "error")
            return redirect(url_for('index'))

        # Создание уникальной директории для запроса
        request_id = str(uuid.uuid4())
        request_dir = os.path.join(TEMP_DIR, request_id)
        os.makedirs(request_dir, exist_ok=True)

        # Сохранение файлов
        zip_path = os.path.join(request_dir, secure_filename(project_zip.filename))
        project_zip.save(zip_path)
        p8_path = os.path.join(request_dir, secure_filename(p8_file.filename))
        p8_file.save(p8_path)

        # Распаковка ZIP
        project_subdir = os.path.join(request_dir, "project")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(project_subdir)

        # Поиск .xcodeproj файла
        xcodeproj_files = list(Path(project_subdir).rglob("*.xcodeproj"))
        if not xcodeproj_files:
            flash("В ZIP-файле не найден .xcodeproj файл!", "error")
            return redirect(url_for('index'))
        project_dir = xcodeproj_files[0].parent
        project_name = xcodeproj_files[0].stem

        # Получение scheme_name
        scheme_name = get_first_scheme(project_dir)

        # Данные из формы
        data = {
            'app_name': request.form['app_name'],
            'issuer_id': request.form['issuer_id'],
            'key_id': request.form['key_id'],
            'apple_id': request.form['apple_id'],
            'bundle_id': request.form['bundle_id'],
            'remote_url': request.form['remote_url']
        }

        # Валидация
        errors = validate_data(data)
        if errors:
            for error in errors:
                flash(error, "error")
            return redirect(url_for('index'))

        # Чтение .p8 файла
        with open(p8_path, "r") as f:
            app_store_connect_private_key = f.read()

        # Генерация SSH-ключа
        ssh_key = generate_ssh_key("700700", request_dir)

        # Создание .sh-скрипта
        script_filename = create_bash_script(data, project_name, scheme_name, request_dir)

        # Создание списка переменных
        variables = [
            {"Name": "CERTIFICATE_PRIVATE_KEY", "Value": ssh_key, "Variable group": "certificate_credentials"},
            {"Name": "APP_STORE_CONNECT_KEY_IDENTIFIER", "Value": data['key_id'], "Variable group": "app_store_credentials"},
            {"Name": "APP_STORE_CONNECT_ISSUER_ID", "Value": data['issuer_id'], "Variable group": "app_store_credentials"},
            {"Name": "APP_STORE_CONNECT_PRIVATE_KEY", "Value": app_store_connect_private_key, "Variable group": "app_store_credentials"},
            {"Name": "BUNDLE_ID", "Value": data['bundle_id'], "Variable group": "app_store_credentials"},
            {"Name": "APP_STORE_APPLE_ID", "Value": data['apple_id'], "Variable group": "app_store_credentials"},
            {"Name": "APP_NAME", "Value": data['app_name'], "Variable group": "app_store_credentials"}
        ]

        # Удаление временных файлов
        os.remove(zip_path)
        os.remove(p8_path)
        shutil.rmtree(project_subdir, ignore_errors=True)

        return render_template('result.html', script_filename=f"{request_id}/{script_filename}", variables=variables)

    return render_template('index.html')

@app.route('/download/<path:filename>')
def download_file(filename):
    file_path = os.path.join(TEMP_DIR, filename)
    @after_this_request
    def remove_file(response):
        try:
            os.remove(file_path)
            request_dir = os.path.dirname(file_path)
            if not os.listdir(request_dir):
                os.rmdir(request_dir)
        except Exception as e:
            app.logger.error(f"Ошибка при удалении файла или директории: {e}")
        return response
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=80)