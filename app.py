from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import os
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
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'jpg', 'jpeg', 'png', 'py', 'cpp', 'java', 'html', 'css', 'js'}

# Создаем необходимые папки
for folder in [UPLOAD_FOLDER, TEACHER_FOLDER, STUDENT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

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
    """Получить список файлов, загруженных учителем"""
    files = []
    if os.path.exists(TEACHER_FOLDER):
        for filename in os.listdir(TEACHER_FOLDER):
            filepath = os.path.join(TEACHER_FOLDER, filename)
            if os.path.isfile(filepath):
                stat = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stat.st_size,
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
    return sorted(files, key=lambda x: x['date'], reverse=True)

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
    student_files = get_student_files()
    
    return render_template('teacher.html', 
                         teacher_files=teacher_files, 
                         student_files=student_files,
                         username=session['username'])

@app.route('/teacher/upload', methods=['POST'])
def teacher_upload():
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    if 'file' not in request.files:
        flash('Файл не выбран!', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран!', 'error')
        return redirect(url_for('teacher_dashboard'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Добавляем дату и время к имени файла для уникальности
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(TEACHER_FOLDER, filename)
        file.save(filepath)
        flash(f'Файл "{file.filename}" успешно загружен!', 'success')
    else:
        flash('Недопустимый тип файла!', 'error')
    
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/download/<filename>')
def teacher_download(filename):
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    filepath = os.path.join(TEACHER_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash('Файл не найден!', 'error')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/view/<path:filename>')
def teacher_view_file(filename):
    if 'username' not in session:
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))

    safe_name = os.path.basename(filename)
    filepath = os.path.join(TEACHER_FOLDER, safe_name)
    if not os.path.exists(filepath):
        dest = 'teacher_dashboard' if session.get('role') == 'teacher' else 'student_dashboard'
        flash('Файл не найден!', 'error')
        return redirect(url_for(dest))

    mimetype, _ = guess_type(filepath)
    return send_file(filepath, mimetype=mimetype or 'application/octet-stream', as_attachment=False)

@app.route('/teacher/download_student/<filename>')
def teacher_download_student(filename):
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    filepath = os.path.join(STUDENT_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    flash('Файл не найден!', 'error')
    return redirect(url_for('teacher_dashboard'))

@app.route('/teacher/delete/<filename>')
def teacher_delete(filename):
    if 'username' not in session or session['role'] != 'teacher':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    filepath = os.path.join(TEACHER_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f'Файл "{filename}" удален!', 'success')
    else:
        flash('Файл не найден!', 'error')
    
    return redirect(url_for('teacher_dashboard'))

@app.route('/student')
def student_dashboard():
    if 'username' not in session or session['role'] != 'student':
        flash('Доступ запрещен!', 'error')
        return redirect(url_for('login'))
    
    teacher_files = get_teacher_files()
    student_files = get_student_files()
    
    return render_template('student.html', 
                         teacher_files=teacher_files, 
                         student_files=student_files,
                         username=session['username'])

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
        # Добавляем имя пользователя и дату к имени файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        username = session['username']
        filename = f"{username}_{timestamp}_{filename}"
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

# Добавляем функцию форматирования в контекст шаблонов
app.jinja_env.globals.update(format_size=format_size)

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

