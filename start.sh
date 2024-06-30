#!/bin/bash

# Instala las dependencias necesarias para OpenCV
apt-get update && apt-get install -y libgl1-mesa-glx

# Ejecuta la aplicación
python main.py
