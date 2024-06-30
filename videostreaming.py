from flask import Flask, render_template, Response
import cv2
import numpy as np

app = Flask(__name__)
# Inicialización de VideoCapture y clasificadores de cascada
cap = cv2.VideoCapture(0)
face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

# Cargar la imagen de los lentes
gafas = cv2.imread('gafa2.png', -1)

# Función para superponer los lentes sobre los ojos detectados
def superponer_lentes(frame, x, y, w, h):
    # Escalar los lentes para que se ajusten a la anchura de la cara
    scale_w = w / gafas.shape[1]
    scale_h = h / gafas.shape[0]
    scale = min(scale_w, scale_h)
    
    gafas_resized = cv2.resize(gafas, (0,0), fx=scale, fy=scale)
    
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

# Función para generar el video con detección de rostros y superposición de lentes
def generate():
    while True:
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detección de rostros
            faces = face_detector.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)
            
            for (x, y, w, h) in faces:
                # Dibujar un rectángulo verde alrededor del rostro detectado
                
                # Superponer los lentes sobre la cara
                frame = superponer_lentes(frame, x, y, w, h)
            
            # Codificación del fotograma como JPEG
            (flag, encodedImage) = cv2.imencode(".jpg", frame)
            
            if not flag:
                continue
            
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +
                   bytearray(encodedImage) + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    app.run(debug=True)
        # Ejecutar Flask en todas las interfaces de red local
    #app.run(host='0.0.0.0', port=5000, debug=True)

# Asegúrate de liberar la captura al finalizar la aplicación Flask
cap.release()
