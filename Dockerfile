# Usamos una imagen de Python oficial y ligera
FROM python:3.9-slim

# Creamos un directorio de trabajo dentro del servidor
WORKDIR /code

# Copiamos el archivo de librerías primero para instalar todo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de los archivos (tu app.py, carpetas templates, etc.)
COPY . .

# Comando para arrancar tu app en el puerto 7860
CMD ["python", "app.py"]