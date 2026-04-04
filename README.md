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
   - `TRADING_MODE_CRYPTO`: `ALPACA`
   - `ALPACA_API_KEY`: tu API key de Alpaca.
   - `ALPACA_SECRET_KEY`: tu API secret de Alpaca.
   - `ALPACA_PAPER`: `True` para paper trading.
   - `ALPACA_BASE_URL`: opcional (por defecto usa paper).

Alternativa CCXT (si más adelante cambias de broker):
- `TRADING_MODE_CRYPTO`: `COINBASE` (u otro modo no-ALPACA)
- `CCXT_EXCHANGE_ID`, `CCXT_API_KEY`, `CCXT_SECRET_KEY`, `CCXT_TESTNET`

Compatibilidad legacy:
- Si ya tienes variables `COINBASE_API_KEY`, `COINBASE_SECRET_KEY` y `COINBASE_TESTNET`, siguen funcionando.

La aplicación arrancará automáticamente en el puerto 7860 y mostrará el panel premium interactivo.

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference
