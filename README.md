---
title: Trading Bot Hub Premium
emoji: 📈
colorFrom: indigo
colorTo: blue
sdk: docker
app_file: app.py
pinned: false
---

# 🤖 Trading Bot Hub (Hugging Face Edition)

Este repositorio está optimizado para funcionar en **Hugging Face Spaces** usando Docker.

### 🚀 Despliegue en Hugging Face
1. Crea un nuevo **Space** en Hugging Face.
2. Selecciona **Docker** como SDK.
3. Sube todos los archivos de este repositorio.
4. Configura los **Secrets** en Hugging Face (Settings > Variables and secrets):
   - `ALPACA_API_KEY`: Tu clave de Alpaca.
   - `ALPACA_SECRET_KEY`: Tu clave secreta de Alpaca.
   - `ALPACA_SYMBOL`: (Opcional) Símbolo a operar (ej: `AAPL`).
   - `ALPACA_PAPER`: `True` para trading simulado.

La aplicación arrancará automáticamente en el puerto 7860 y mostrará el panel premium interactivo.

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
