from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
import os
import io
import zipfile
import shutil
from mimetypes import guess_type
from werkzeug.utils import secure_filename
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'  # Измените на случайный ключ!

# Конфигурация
UPLOAD_FOLDER = 'uploads'
TEACHER_FOLDER = os.path.join(UPLOAD_FOLDER, 'teacher')
STUDENT_FOLDER = os.path.join(UPLOAD_FOLDER, 'students')

# Базовая структура классов (основные папки 11, 10, 9, 8, 7)
CLASS_DIRECTORIES = ['11', '10', '9', '8', '7']

# Разрешённые к загрузке расширения
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
    'zip', 'rar', 'jpg', 'jpeg', 'png', 'py', 'cpp', 'java',
    'html', 'css', 'js'
}

# Создаем необходимые папки
for folder in [UPLOAD_FOLDER, TEACHER_FOLDER, STUDENT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Создаем фиксированную структуру классов внутри папки учителя
for class_dir in CLASS_DIRECTORIES:
    os.makedirs(os.path.join(TEACHER_FOLDER, class_dir), exist_ok=True)

# Простая база данных пользователей (в реальном проекте используйте SQLite или другую БД)
USERS = {
    'teacher': {'password': 'teacher123', 'role': 'teacher'},
    'student1': {'password': 'student123', 'role': 'student'},
    'student2': {'password': 'student123', 'role': 'student'},
    # Добавьте больше пользователей по необходимости
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_teacher_files():
    """Получить список файлов, загруженных учителем (включая подкаталоги).

    name содержит относительный путь внутри TEACHER_FOLDER, чтобы было видно структуру.
    """
    files = []
    if os.path.exists(TEACHER_FOLDER):
        for root, _, filenames in os.walk(TEACHER_FOLDER):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                relpath = os.path.relpath(filepath, TEACHER_FOLDER)
                stat = os.stat(filepath)
                files.append({
                    'name': relpath.replace('\\', '/'),
                    'size': stat.st_size,
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    return sorted(files, key=lambda x: x['date'], reverse=True)


def get_teacher_tree():
    """
    Построить дерево файлов/папок для учителя, чтобы отображать как в проводнике.

    Основная структура: фиксированные папки классов 11, 10, 9, 8, 7 (в таком порядке).
    Эти корневые папки нельзя удалить, но содержимое внутри них может меняться.
    """

    def build_children(abs_dir, rel_dir):
        """Построить список дочерних элементов (папок и файлов) для заданной директории."""
        items = []
        if not os.path.exists(abs_dir):
            return items

        for name in sorted(os.listdir(abs_dir)):
            abs_path = os.path.join(abs_dir, name)
            rel_path = os.path.join(rel_dir, name)
            rel_path = rel_path.replace("\\", "/")

            if os.path.isdir(abs_path):
                items.append({
                    'type': 'dir',
                    'name': name,
                    'path': rel_path,
                    'children': build_children(abs_path, rel_path)
                })
            else:
                stat = os.stat(abs_path)
                items.append({
                    'type': 'file',
                    'name': name,
                    'path': rel_path,
                    'size': stat.st_size,
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        return items

    tree = []

    # Добавляем фиксированные папки классов в нужном порядке
    for class_name in CLASS_DIRECTORIES:
        rel_dir = class_name
        abs_dir = os.path.join(TEACHER_FOLDER, class_name)
        children = build_children(abs_dir, rel_dir)
        tree.append({
            'type': 'dir',
            'name': class_name,
            'path': rel_dir,
            'is_root_class': True,
            'children': children
        })

    return tree

def get_student_files():
    """Получить список файлов, загруженных учениками"""
    files = []
    if os.path.exists(STUDENT_FOLDER):
        for filename in os.listdir(STUDENT_FOLDER):
            filepath = os.path.join(STUDENT_FOLDER, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stat.st_size,
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    return sorted(files, key=lambda x: x['date'], reverse=True)

@app.route('/')
def index():
    if 'username' in session:
        if session['role'] == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in USERS and USERS[username]['password'] == password:
            session['username'] = username
            session['role'] = USERS[username]['role']
            if USERS[username]['role'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Неверное имя пользователя или пароль!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('login'))

@app.route('/teacher')
def teacher_dashboard():
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    teacher_files = get_teacher_files()
    teacher_tree = get_teacher_tree()
    student_files = get_student_files()
    
    return render_template(
        'teacher.html',
        teacher_files=teacher_files,
        teacher_tree=teacher_tree,
        student_files=student_files,
        username=session['username']
    )

def _save_teacher_file_with_structure(file_storage, class_folder):
    """
    Сохраняет файл учителя, полностью повторяя структуру загружаемой папки.

    Правила:
    - Если загружается ОДИН файл (без webkitdirectory) → файл попадает прямо в
      uploads/teacher/<КЛАСС>/<имя_файла>
    - Если загружается папка (webkitdirectory) → полностью сохраняется её структура:
      uploads/teacher/<КЛАСС>/<корневая_папка>/<внутренние_папки...>/<имя_файла>
    """
    raw_name = file_storage.filename
    if raw_name == '':
        return False, 'Файл не выбран!'

    # Нормализуем относительный путь (для webkitdirectory может быть "Папка/подпапка/файл.ext")
    rel_path = raw_name.replace('\\', '/')
    parts = [secure_filename(p) for p in rel_path.split('/') if p]

    if not parts:
        return False, 'Некорректное имя файла!'

    # Отдельно обрабатываем имя файла
    *dir_parts, base_name = parts

    # Класс, в папку которого кладём задание
    if class_folder not in CLASS_DIRECTORIES:
        class_folder = CLASS_DIRECTORIES[0]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = f"{timestamp}_{base_name}"

    # Собираем путь: /КЛАСС/(все внутренние папки).../имя_файла
    rel_parts = [class_folder]
    if dir_parts:
        rel_parts.extend(dir_parts)
    rel_parts.append(safe_filename)

    rel_safe_path = os.path.join(*rel_parts)

    dest_path = os.path.join(TEACHER_FOLDER, rel_safe_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    file_storage.save(dest_path)
    return True, raw_name


@app.route('/teacher/upload', methods=['POST'])
def teacher_upload():
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    # Класс, в который кладём загружаемый файл/папку
    class_folder = request.form.get('class_folder')
    if class_folder not in CLASS_DIRECTORIES:
        class_folder = CLASS_DIRECTORIES[0]

    # Поддерживаем как одиночный файл, так и список файлов (при загрузке папки)
    files = request.files.getlist('file')
    if not files:
        flash('Файл(ы) не выбраны!', 'error')
        return redirect(url_for('teacher_dashboard'))

    success_count = 0
    error_messages = []

    for f in files:
        ok, msg = _save_teacher_file_with_structure(f, class_folder=class_folder)
        if ok:
            success_count += 1
        else:
            error_messages.append(msg)

    if success_count:
        flash(f'Успешно загружено файлов: {success_count}', 'success')
    if error_messages:
        flash(' ; '.join(error_messages), 'error')
    
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/download/<path:filename>')
def teacher_download(filename):
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    # Поддержка относительных путей (структура папок)
    safe_path = filename.replace('\\', '/')
    filepath = os.path.join(TEACHER_FOLDER, safe_path)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash('Файл не найден!', 'error')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/view/<path:filename>')
def teacher_view_file(filename):
    if 'username' not in session:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))

    # Разрешаем относительные пути внутри TEACHER_FOLDER, но не выходим за его пределы
    rel_path = filename.replace('\\', '/')
    base_dir = os.path.abspath(TEACHER_FOLDER)
    filepath = os.path.abspath(os.path.join(base_dir, rel_path))

    # Запрет выхода за пределы TEACHER_FOLDER
    if not filepath.startswith(base_dir):
        dest = 'teacher_dashboard' if session.get('role') == 'teacher' else 'student_dashboard'
        flash('Недопустимый путь к файлу!', 'error')
        return redirect(url_for(dest))

    if not os.path.exists(filepath):
        dest = 'teacher_dashboard' if session.get('role') == 'teacher' else 'student_dashboard'
        flash('Файл не найден!', 'error')
        return redirect(url_for(dest))

    mimetype, _ = guess_type(filepath)
    return send_file(filepath, mimetype=mimetype or 'application/octet-stream', as_attachment=False)

@app.route('/teacher/download_student/<path:filename>')
def teacher_download_student(filename):
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    filepath = os.path.join(STUDENT_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash('Файл не найден!', 'error')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/download_all_students')
def download_all_students():
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        if os.path.exists(STUDENT_FOLDER):
            for filename in os.listdir(STUDENT_FOLDER):
                filepath = os.path.join(STUDENT_FOLDER, filename)
                if os.path.isfile(filepath):
                    zip_file.write(filepath, arcname=filename)

    buffer.seek(0)
    archive_name = f"student_works_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(buffer, mimetype='application/zip', as_attachment=True, download_name=archive_name)

@app.route('/teacher/delete/<path:filename>')
def teacher_delete(filename):
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    # Нормализуем путь и проверяем, что он внутри TEACHER_FOLDER
    rel_path = filename.replace('\\', '/')
    base_dir = os.path.abspath(TEACHER_FOLDER)
    target_path = os.path.abspath(os.path.join(base_dir, rel_path))

    if not target_path.startswith(base_dir):
        flash('Недопустимый путь для удаления!', 'error')
        return redirect(url_for('teacher_dashboard'))

    # Относительный путь от TEACHER_FOLDER
    rel_from_teacher = os.path.relpath(target_path, base_dir).replace('\\', '/')

    # Защита от удаления корневых папок классов
    if rel_from_teacher in CLASS_DIRECTORIES:
        flash('Нельзя удалить корневую папку класса!', 'error')
        return redirect(url_for('teacher_dashboard'))

    success = False
    message = ''

    if os.path.isdir(target_path):
        shutil.rmtree(target_path)
        message = f'Папка "{rel_from_teacher}" и всё её содержимое удалены!'
        flash(message, 'success')
        success = True
    elif os.path.isfile(target_path):
        os.remove(target_path)
        message = f'Файл "{rel_from_teacher}" удален!'
        flash(message, 'success')
        success = True
    else:
        message = 'Файл или папка не найдены!'
        flash(message, 'error')

    # Если запрос пришёл через fetch/AJAX, возвращаем JSON и НЕ перезагружаем страницу
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        status = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status

    return redirect(url_for('teacher_dashboard'))


@app.route('/teacher/clear_class/<class_name>')
def teacher_clear_class(class_name):
    """Очистить корневую папку выбранного класса (удалить все вложенные файлы и папки)."""
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))

    if class_name not in CLASS_DIRECTORIES:
        flash('Некорректный класс для очистки!', 'error')
        return redirect(url_for('teacher_dashboard'))

    class_dir = os.path.join(TEACHER_FOLDER, class_name)
    if not os.path.exists(class_dir):
        flash('Папка класса не найдена!', 'error')
        return redirect(url_for('teacher_dashboard'))

    # Удаляем всё содержимое, но оставляем саму папку класса
    success = True
    message = ''

    for entry in os.listdir(class_dir):
        entry_path = os.path.join(class_dir, entry)
        try:
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path)
            else:
                os.remove(entry_path)
        except Exception as e:
            success = False
            message = f'Ошибка при удалении "{entry}": {e}'
            flash(message, 'error')
            break

    if success:
        message = f'Папка класса "{class_name}" успешно очищена.'
        flash(message, 'success')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        status = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status

    return redirect(url_for('teacher_dashboard'))

@app.route('/student')
def student_dashboard():
    if 'username' not in session or session['role'] != 'student':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    teacher_files = get_teacher_files()
    teacher_tree = get_teacher_tree()
    student_files = get_student_files()
    
    return render_template(
        'student.html',
        teacher_files=teacher_files,
        teacher_tree=teacher_tree,
        student_files=student_files,
        username=session['username']
    )

@app.route('/student/upload', methods=['POST'])
def student_upload():
    if 'username' not in session or session['role'] != 'student':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    if 'file' not in request.files:
        flash('Файл не выбран!', 'error')
        return redirect(url_for('student_dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран!', 'error')
        return redirect(url_for('student_dashboard'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(STUDENT_FOLDER, filename)
        file.save(filepath)
        flash(f'Файл "{file.filename}" успешно загружен!', 'success')
    else:
        flash('Недопустимый тип файла!', 'error')
    
    return redirect(url_for('student_dashboard'))

@app.route('/student/download/<filename>')
def student_download(filename):
    if 'username' not in session or session['role'] != 'student':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    filepath = os.path.join(TEACHER_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash('Файл не найден!', 'error')
    return redirect(url_for('student_dashboard'))

def format_size(size):
    """Форматирует размер файла в читаемый вид"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

# Добавляем полезные функции в контекст шаблонов
app.jinja_env.globals.update(
    format_size=format_size,
)

if __name__ == '__main__':
    import socket
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "localhost"
    
    local_ip = get_local_ip()
    print("=" * 50)
    print("Сервер запущен!")
    print("Откройте браузер и перейдите по адресу:")
    print("http://localhost:5000")
    if local_ip != "localhost":
        print(f"или")
        print(f"http://{local_ip}:5000")
    print("=" * 50)
    print("\nУчетные данные по умолчанию:")
    print("Учитель: teacher / teacher123")
    print("Ученик: student1 / student123")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)

