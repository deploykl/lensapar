from datetime import datetime
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, send_from_directory, session, url_for
import sqlite3
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import cv2

app = Flask(__name__, template_folder='templates')
app.secret_key = '123132132131313131313'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Inicialización de VideoCapture y clasificadores de cascada
cap = cv2.VideoCapture(0)
face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")


# Función para superponer los lentes sobre los ojos detectados
def superponer_lentes(frame, x, y, w, h, producto_id):
    try:
        with sqlite3.connect("productos.db") as conn:
            cursor = conn.execute("SELECT imagen FROM Productos WHERE id = ?", (producto_id,))
            producto = cursor.fetchone()
            if producto and producto[0]:
                # Obtener solo el nombre del archivo sin la ruta completa
                gafas_filename = os.path.basename(producto[0])
                gafas_path = os.path.join(app.config['UPLOAD_FOLDER'], gafas_filename)
                
                gafas = cv2.imread(gafas_path, -1)
                if gafas is None:
                    return frame

                # Escalar los lentes para que se ajusten a la anchura de la cara
                scale_w = w / gafas.shape[1]
                scale_h = h / gafas.shape[0]
                scale = min(scale_w, scale_h)
                
                gafas_resized = cv2.resize(gafas, (0, 0), fx=scale, fy=scale)
                
                # Posición de los lentes para superponerlos sobre los ojos
                x_offset = x
                y_offset = y + int(h * 0.15)  # Ajusta la posición y para estar un poco más abajo
                
                # Área de interés para superponer los lentes
                roi = frame[y_offset:y_offset+gafas_resized.shape[0], x_offset:x_offset+gafas_resized.shape[1]]
                
                # Máscara alpha de los lentes
                gafas_alpha = gafas_resized[:, :, 3] / 255.0
                
                # Superponer los lentes utilizando la máscara alpha
                for c in range(0, 3):
                    roi[:, :, c] = (1 - gafas_alpha) * roi[:, :, c] + gafas_alpha * gafas_resized[:, :, c]

                return frame
            else:
                return frame
    except Exception as e:
        print(f"Error al superponer lentes: {str(e)}")
        return frame

# Función para generar el video con detección de rostros y superposición de lentes
def generate(producto_id):
    while True:
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detección de rostros
            faces = face_detector.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
            
            for (x, y, w, h) in faces:
                # Superponer los lentes sobre la cara
                frame = superponer_lentes(frame, x, y, w, h, producto_id)
            
            # Codificación del fotograma como JPEG
            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            
            if not flag:
                continue
            
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                   bytearray(encodedImage) + b'\r\n')

@app.route('/video_feed/<int:producto_id>')
def video_feed(producto_id):
    return Response(generate(producto_id), mimetype='multipart/x-mixed-replace; boundary=frame')

DB_FILE = "productos.db"

# Función para conectar a la base de datos
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Para retornar resultados como diccionarios
    return conn

# Crear tablas si no existen
def create_tables():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                nombre TEXT,
                apellido TEXT,
                telefono TEXT,
                correo TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                precio REAL,
                imagen TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Catalogo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER,
                categoria TEXT,
                FOREIGN KEY (producto_id) REFERENCES Productos(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS Favoritos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER,
                cliente_id INTEGER,
                fecha_agregado TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (producto_id) REFERENCES Productos(id),
                FOREIGN KEY (cliente_id) REFERENCES Clientes(id)
            )
        """)

@app.route('/cliente_registro', methods=['GET', 'POST'])
def cliente_registro():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        telefono = request.form.get('telefono')
        correo = request.form.get('correo')

        if not username or not password or not nombre or not correo:
            flash("Todos los campos son requeridos", "error")
            return redirect(url_for('cliente_registro'))

        hashed_password = generate_password_hash(password)

        try:
            with get_db_connection() as conn:            
                conn.execute("INSERT INTO Clientes (username, password, nombre, apellido, telefono, correo) VALUES (?, ?, ?, ?, ?, ?)",
                             (username, hashed_password, nombre, apellido, telefono, correo))
                conn.commit()

                flash("Registro exitoso. Por favor inicia sesión.", "success")
                return redirect(url_for('cliente_login'))
        except sqlite3.Error as e:
            flash(f"Error al registrar usuario: {str(e)}", "error")

    return render_template('cliente/cliente_registro.html')

@app.route('/cliente_login', methods=['GET', 'POST'])
def cliente_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash("Nombre de usuario y contraseña son requeridos", "error")
            return redirect(url_for('cliente_login'))

        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM Clientes WHERE username = ?", (username,))
            cliente = cursor.fetchone()

            if not cliente or not check_password_hash(cliente['password'], password):
                flash("Usuario o contraseña incorrectos", "error")
                return redirect(url_for('cliente_login'))

            # Guardar el cliente en la sesión
            session['cliente_id'] = cliente['id']
            session['cliente_nombre'] = cliente['nombre']

            return redirect(url_for('index'))

    return render_template('cliente/cliente_login.html')

@app.route('/logout_cliente')
def logout_cliente():
    session.pop('cliente_id', None)
    session.pop('cliente_nombre', None)
    return redirect(url_for('cliente_login'))

@app.route('/user')
def user():
    if 'user_id' in session:
        return render_template('user.html')
    else:
        return redirect(url_for('login'))

def crear_usuario(username, password):
    hashed_password = generate_password_hash(password)
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO Usuarios (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error al crear usuario: {str(e)}")
        return False

@app.route('/crear_usuario', methods=['POST'])
def crear_usuario_route():
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        flash("Username and password are required", "error")
        return redirect(url_for('user'))

    if crear_usuario(username, password):
        flash(f"Usuario {username} creado correctamente", "success")
    else:
        flash("Error al crear usuario", "error")
    
    return redirect(url_for('user'))

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('login.html', error="Username and password are required")

        with get_db_connection() as conn:
            cursor = conn.execute("SELECT * FROM Usuarios WHERE username = ?", (username,))
            usuario = cursor.fetchone()

            if not usuario or not check_password_hash(usuario['password'], password):
                error = "Invalid username or password"
                return render_template('login.html', error=error)

            session['user_id'] = usuario['id']
            return redirect(url_for('admin'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.before_request
def require_login():
    if request.endpoint in ['admin'] and 'user_id' not in session:
        return redirect(url_for('login'))

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/', methods=['GET'])
def index():
    return render_template('catalogo.html')

# Ruta para servir admin.html y archivos estáticos
@app.route('/admin', methods=['GET'])
def admin():
    return render_template('admin.html')
# Ruta para obtener todos los productos
@app.route('/api/productos', methods=['GET'])
def get_productos():
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM Productos")
        productos = cursor.fetchall()
        productos = [dict(row) for row in productos]
        for producto in productos:
            if producto['imagen']:
                producto['imagen'] = url_for('uploaded_file', filename=os.path.basename(producto['imagen']))
        return jsonify(productos)

@app.route('/api/productos/<int:producto_id>', methods=['GET'])
def obtener_producto(producto_id):
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM Productos WHERE id = ?", (producto_id,))
        producto = cursor.fetchone()
        if not producto:
            return jsonify({"error": "Producto no encontrado"}), 404
        producto = dict(producto)
        if producto['imagen']:
            producto['imagen'] = url_for('uploaded_file', filename=os.path.basename(producto['imagen']))
        return jsonify(producto)

@app.route('/api/productos/<int:producto_id>', methods=['PUT'])
def actualizar_producto(producto_id):
    nuevo_producto = request.form
    imagen = request.files.get('imagen')

    # Obtener producto actual para la ruta de la imagen
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM Productos WHERE id = ?", (producto_id,))
        producto_actual = cursor.fetchone()

    if not producto_actual:
        return jsonify({"error": "Producto no encontrado"}), 404

    # Guardar la imagen si se proporciona una nueva
    imagen_path = producto_actual['imagen']
    if imagen:
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    # Actualizar datos del producto en la base de datos
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE Productos
            SET nombre = ?, descripcion = ?, precio = ?, imagen = ?
            WHERE id = ?
        """, (nuevo_producto['nombre'], nuevo_producto['descripcion'], nuevo_producto['precio'], imagen_path, producto_id))
        conn.commit()

    return jsonify({"message": "Producto actualizado correctamente"}), 200

@app.route('/api/productos/<int:producto_id>', methods=['DELETE'])
def eliminar_producto(producto_id):
    with get_db_connection() as conn:
        conn.execute("DELETE FROM Productos WHERE id = ?", (producto_id,))
        conn.commit()
        return jsonify({"message": "Producto eliminado correctamente"}), 200

@app.route('/api/productos', methods=['POST'])
def crear_producto():
    nuevo_producto = request.form
    imagen = request.files.get('imagen')

    # Guardar la imagen en el servidor si se proporciona
    if imagen:
        filename = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        imagen_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    else:
        imagen_path = None

    # Guardar datos del producto en la base de datos
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO Productos (nombre, descripcion, precio, imagen)
            VALUES (?, ?, ?, ?)
        """, (nuevo_producto['nombre'], nuevo_producto['descripcion'], nuevo_producto['precio'], imagen_path))
        conn.commit()

    return jsonify({"message": "Producto creado correctamente"}), 201

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ///////////////// favoritos 
@app.route('/api/productos/<int:producto_id>/favorito', methods=['POST', 'DELETE'])
def toggle_producto_favorito(producto_id):
    if 'cliente_id' not in session:
        return jsonify({"error": "Usuario no autenticado"}), 401

    cliente_id = session['cliente_id']

    if request.method == 'POST':
        # Marcar como favorito
        try:
            with get_db_connection() as conn:
                conn.execute("INSERT INTO Favoritos (producto_id, cliente_id) VALUES (?, ?)", (producto_id, cliente_id))
                conn.commit()
            return jsonify({"message": "Producto marcado como favorito"}), 200
        except Exception as e:
            return jsonify({"error": f"Error al marcar favorito: {str(e)}"}), 500

    elif request.method == 'DELETE':
        # Desmarcar como favorito
        try:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM Favoritos WHERE producto_id = ? AND cliente_id = ?", (producto_id, cliente_id))
                conn.commit()
            return jsonify({"message": "Producto desmarcado como favorito"}), 200
        except Exception as e:
            return jsonify({"error": f"Error al desmarcar favorito: {str(e)}"}), 500
    
@app.route('/api/cliente/favoritos', methods=['GET'])
def get_productos_favoritos():
    try:
        if 'cliente_id' not in session:
            return jsonify({"error": "Usuario no autenticado"}), 401
        
        cliente_id = session['cliente_id']

        with get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT p.id, p.nombre, p.descripcion, p.precio, p.imagen
                FROM Productos p
                INNER JOIN Favoritos f ON p.id = f.producto_id
                WHERE f.cliente_id = ?
            """, (cliente_id,))
            favoritos = cursor.fetchall()
            favoritos = [dict(row) for row in favoritos]

            for favorito in favoritos:
                if favorito['imagen']:
                    favorito['imagen'] = url_for('static', filename=favorito['imagen'])
            
            return jsonify(favoritos)

    except Exception as e:
        print(f"Error al obtener productos favoritos: {str(e)}")
        return jsonify({"error": "Error al obtener productos favoritos"}), 500


@app.route('/favoritos', methods=['GET'])
def ver_favoritos():
    if 'cliente_id' not in session:
        flash("Debes iniciar sesión para ver tus favoritos.", "error")
        return redirect(url_for('cliente_login'))

    try:
        with get_db_connection() as conn:
            cliente_id = session['cliente_id']
            cursor = conn.execute("""
                SELECT p.id, p.nombre, p.descripcion, p.precio, p.imagen
                FROM Productos p
                INNER JOIN Favoritos f ON p.id = f.producto_id
                WHERE f.cliente_id = ?
            """, (cliente_id,))
            productos = cursor.fetchall()

            return render_template('cliente/favoritos.html', productos=productos)

    except sqlite3.Error as e:
        flash(f"Error al obtener tus favoritos: {str(e)}", "error")

    return redirect(url_for('catalogo'))  # Redirigir a la página de catálogo si hay algún error


@app.route('/api/productos/<int:producto_id>/favorito', methods=['POST', 'DELETE'])
def gestionar_favorito(producto_id):
    if 'cliente_id' not in session:
        return jsonify({"error": "Usuario no autenticado"}), 401

    cliente_id = session['cliente_id']

    if request.method == 'POST':
        # Guardar producto como favorito
        try:
            with get_db_connection() as conn:
                conn.execute("INSERT INTO Favoritos (cliente_id, producto_id) VALUES (?, ?)", (cliente_id, producto_id))
                conn.commit()
                return jsonify({"message": "Producto guardado como favorito"})
        except Exception as e:
            return jsonify({"error": f"Error al guardar favorito: {str(e)}"}), 500

    elif request.method == 'DELETE':
        # Eliminar producto de favoritos
        try:
            with get_db_connection() as conn:
                conn.execute("DELETE FROM Favoritos WHERE cliente_id = ? AND producto_id = ?", (cliente_id, producto_id))
                conn.commit()
                return jsonify({"message": "Producto eliminado de favoritos"})
        except Exception as e:
            return jsonify({"error": f"Error al eliminar favorito: {str(e)}"}), 500

# Configurar las tablas al iniciar la aplicación
if __name__ == '__main__':
    if not os.path.exists(DB_FILE):
        create_tables()
    app.run(debug=True)

cap.release()