
# =============================================================================
# CLASE PRINCIPAL: TradingBot
# =============================================================================
# Este archivo es el orquestador. No contiene lógica propia de indicadores
# ni de estrategia — simplemente coordina todos los módulos especializados
# y mantiene el estado de la sesión de trading.
#
# Flujo de ejecución:
#   1. calcular_indicadores()  → Rellena self.indicadores
#   2. detectar_patron()       → Identifica patrón de vela actual
#   3. evaluar_entrada()       → Cuenta confluencias y decide dirección
#   4. imprimir_resumen()      → Muestra el estado completo en consola
# =============================================================================

import pandas as pd
from src.core.config import MIN_CONFLUENCIAS, CAPITAL_INICIAL, RIESGO_POR_OPERACION

from src.strategies.indicators.medias_moviles import calcular_emas
from src.strategies.indicators.macd           import calcular_macd
from src.strategies.indicators.rsi            import calcular_rsi, zona_rsi
from src.strategies.indicators.bollinger      import calcular_bollinger, posicion_en_banda
from src.strategies.indicators.atr            import calcular_atr
from src.strategies.indicators.volumen        import calcular_volumen_medio
from src.strategies.indicators.adx            import calcular_adx
from src.strategies.indicators.vwap           import calcular_vwap
from src.strategies.indicators.obv            import calcular_obv


from src.strategies.patterns.velas             import detectar_patron
from src.strategies.strategies.confluencias    import contar_confluencias
from src.risk.management                       import calcular_gestion_riesgo


class TradingBot:
    """
    Clase principal del bot de trading algorítmico.

    Coordina el cálculo de indicadores, la detección de patrones,
    el conteo de confluencias y la gestión de riesgo.

    Atributos:
        datos            : DataFrame OHLCV con los datos de mercado
        capital          : Capital total disponible
        riesgo           : Fracción del capital a arriesgar por operación
        min_confluencias : Número mínimo de confluencias para entrar al mercado
        indicadores      : Diccionario con todas las series de indicadores
        confluencias_long : Lista de confluencias alcistas detectadas
        confluencias_short: Lista de confluencias bajistas detectadas
        patron           : Patrón de vela detectado en la última vela
        decision         : Resultado final del análisis (dirección + gestión)
    """

    def __init__(self, datos: pd.DataFrame,
                 capital: float          = CAPITAL_INICIAL,
                 riesgo: float           = RIESGO_POR_OPERACION,
                 min_confluencias: int   = MIN_CONFLUENCIAS,
                 is_crypto: bool         = False):

        self.datos            = datos.copy()
        self.capital          = capital
        self.riesgo           = riesgo
        self.min_confluencias = min_confluencias
        self.is_crypto        = is_crypto

        # Estado interno — se rellenan al llamar a ejecutar()
        self.indicadores       = {}
        self.confluencias_long  = []
        self.confluencias_short = []
        self.patron            = None
        self.decision          = None
        self.regime            = None
        self.adx_val           = 0.0

        self._imprimir_cabecera()

    # ── Cabecera de inicio ────────────────────────────────────────────────────
    def _imprimir_cabecera(self):
        sep = "=" * 60
        print(f"\n{sep}")
        print("   BOT DE TRADING ALGORITMICO  -  Análisis Tecnico")
        print(sep)
        print(f"   Capital:              ${self.capital:,.2f}")
        print(f"   Riesgo por operacion: {self.riesgo * 100:.1f}%")
        print(f"   Confluencias minimas: {self.min_confluencias}")
        print(f"   Velas cargadas:       {len(self.datos)}")
        print(sep)

    # ── 1. Cálculo de indicadores ────────────────────────────────────────────
    def calcular_indicadores(self):
        """
        Calcula todos los indicadores técnicos y los almacena en
        self.indicadores para su uso posterior por el resto de métodos.
        """
        print("\n[INDICADORES] Calculando indicadores...")

        # Medias Móviles Exponenciales
        self.indicadores.update(calcular_emas(self.datos))

        # MACD
        macd_d = calcular_macd(self.datos)
        self.indicadores['macd']           = macd_d['macd']
        self.indicadores['macd_signal']    = macd_d['signal']
        self.indicadores['macd_histogram'] = macd_d['histogram']

        # RSI
        self.indicadores['rsi'] = calcular_rsi(self.datos)

        # Bandas de Bollinger
        bb_d = calcular_bollinger(self.datos)
        self.indicadores['bb_superior'] = bb_d['banda_superior']
        self.indicadores['bb_media']    = bb_d['banda_media']
        self.indicadores['bb_inferior'] = bb_d['banda_inferior']
        self.indicadores['bb_ancho']    = bb_d['ancho']

        # ATR
        self.indicadores['atr'] = calcular_atr(self.datos)

        # ADX
        self.indicadores['adx'] = calcular_adx(self.datos)

        # VWAP
        vwap_series = calcular_vwap(self.datos)
        self.indicadores['vwap'] = vwap_series

        # OBV
        self.indicadores['obv'] = calcular_obv(self.datos)

        # Volumen Medio
        self.indicadores['volumen_medio'] = calcular_volumen_medio(self.datos)

        print("   [OK] EMA 20 / 50 / 200")
        print("   [OK] MACD (12, 26, 9)")
        print("   [OK] RSI (14)")
        print("   [OK] Bandas de Bollinger (20, 2)")
        print("   [OK] ATR (14)")
        print("   [OK] ADX (14)")
        print("   [OK] VWAP")
        print("   [OK] OBV")
        print("   [OK] Volumen Medio (20)")

    # ── 2. Detección de patrón de vela ───────────────────────────────────────
    def detectar_patron(self) -> str:
        """Detecta el patrón de vela de la última vela y lo almacena."""
        self.patron = detectar_patron(self.datos)
        return self.patron

    # ── 3. Evaluación de entrada ──────────────────────────────────────────────
    def evaluar_entrada(self) -> dict:
        """
        Evalúa la entrada usando el sistema experto de puntuación para acciones
        o la lógica conservadora para cripto.
        """
        resultado = contar_confluencias(self.datos, self.indicadores, is_crypto=self.is_crypto)

        self.confluencias_long  = resultado['long']
        self.confluencias_short = resultado['short']
        total_long              = resultado['total_long']
        total_short             = resultado['total_short']
        self.regime             = resultado.get('regime')
        self.adx_val            = resultado.get('adx')

        precio   = self.datos['close'].iloc[-1]
        atr      = self.indicadores['atr'].iloc[-1]
        
        # Umbral dinámico basado en la configuración
        umbral = self.min_confluencias

        decision = {
            'direccion':   'NEUTRAL',
            'total_long':  total_long,
            'total_short': total_short,
            'gestion':     None,
            'razon':       '',
            'expert_json': None
        }

        # Lógica de decisión
        if total_long >= umbral and total_long > total_short:
            decision['direccion'] = 'LONG'
            decision['gestion']   = calcular_gestion_riesgo(
                'LONG', precio, atr, self.capital, riesgo=self.riesgo, is_crypto=self.is_crypto)
            decision['razon'] = f"Señal LONG con score {total_long}/10"

        elif total_short >= umbral and total_short > total_long:
            decision['direccion'] = 'SHORT'
            decision['gestion']   = calcular_gestion_riesgo(
                'SHORT', precio, atr, self.capital, riesgo=self.riesgo, is_crypto=self.is_crypto)
            decision['razon'] = f"Señal SHORT con score {total_short}/10"

        # Generar OUTPUT REQUERIDO (JSON) para Acciones
        if not self.is_crypto:
            import json
            expert_output = {
                "signal": decision['direccion'],
                "ticker": "STOCK", # Podría pasarse el símbolo
                "timeframe_bias": {"daily": "N/A", "1h": "N/A"}, # Requiere MTF core
                "entry_price": round(float(precio), 4),
                "stop_loss": round(float(decision['gestion']['stop_loss']), 4) if decision['gestion'] else 0,
                "take_profit_1": round(float(decision['gestion']['take_profit']), 4) if decision['gestion'] else 0,
                "take_profit_2": round(float(precio + (precio - decision['gestion']['take_profit']) * -1.5), 4) if decision['gestion'] else 0,
                "score": float(max(total_long, total_short)),
                "position_size_pct": self.riesgo * 100,
                "confidence": round(max(total_long, total_short) / 10, 2),
                "reason": decision['razon'],
                "invalidation": "Cierre bajo EMA200 o cambio de régimen ADX"
            }
            print("[EXPERT ANALYSIS JSON]:")
            print(json.dumps(expert_output, indent=2))
        
        elif self.is_crypto:
            import json
            adx_val = self.indicadores.get('adx', pd.Series(0, index=self.datos.index)).iloc[-1]
            regime = "TREND" if adx_val > 25 else "MEAN_REV" if adx_val < 20 else "HYBRID"
            
            expert_output = {
                "signal": decision['direccion'],
                "ticker": "CRYPTO",
                "macro_trend": "bull" if self.indicadores['ema_50'].iloc[-1] > self.indicadores['ema_200'].iloc[-1] else "neutral",
                "regime": regime,
                "entry_price": round(float(precio), 4),
                "entry_2_price": round(float(precio * 1.002), 4),
                "stop_loss": round(float(decision['gestion']['stop_loss']), 4) if decision['gestion'] else 0,
                "take_profit_1": round(float(decision['gestion']['take_profit']), 4) if decision['gestion'] else 0,
                "take_profit_2": round(float(precio + (precio - decision['gestion']['take_profit']) * -1.5), 4) if decision['gestion'] else 0,
                "score": float(total_long),
                "position_size_pct": self.riesgo * 100,
                "confidence": round(total_long / 10, 2),
                "reason": decision['razon'],
                "invalidation": "Macro Bearish flip or RSI divergence against"
            }
            decision['expert_json'] = expert_output
            print("\n[CRYPTO EXPERT JSON]:")
            print(json.dumps(expert_output, indent=2))

        self.decision = decision
        return decision

    # ── 4. Bucle principal ────────────────────────────────────────────────────
    def ejecutar(self):
        """
        Orquesta la ejecución completa del ciclo de análisis del bot.
        En un bot real este método se llamaría en cada nueva vela.
        """
        print("\n[BOT] Iniciando ciclo de analisis...")
        self.calcular_indicadores()

        print(f"\n[VELA] Detectando patron de vela...")
        patron = self.detectar_patron()
        print(f"   -> {patron}")

        print("\n[ESTRATEGIA] Evaluando confluencias y señales...")
        self.evaluar_entrada()

        self.imprimir_resumen()

    # ── 5. Resumen en consola ─────────────────────────────────────────────────
    def imprimir_resumen(self):
        """Imprime el resumen completo del análisis en consola."""
        sep = "=" * 60
        precio  = self.datos['close'].iloc[-1]
        volumen = self.datos['volume'].iloc[-1]
        vol_med = self.indicadores['volumen_medio'].iloc[-1]

        # -- Datos del precio --------------------------------------------------
        print(f"\n{sep}")
        print("   RESUMEN DEL ANALISIS")
        print(sep)
        print("\nULTIMA VELA:")
        print(f"   Open:    ${self.datos['open'].iloc[-1]:>10.4f}")
        print(f"   High:    ${self.datos['high'].iloc[-1]:>10.4f}")
        print(f"   Low:     ${self.datos['low'].iloc[-1]:>10.4f}")
        print(f"   Close:   ${precio:>10.4f}")
        print(f"   Volume:  {volumen:>10,.0f}  (x{volumen/vol_med:.2f} del promedio)")

        # -- Indicadores -------------------------------------------------------
        print("\nINDICADORES:")
        ind = self.indicadores
        print(f"   EMA 20:          ${ind['ema_20'].iloc[-1]:>10.4f}")
        print(f"   EMA 50:          ${ind['ema_50'].iloc[-1]:>10.4f}")
        print(f"   EMA 200:         ${ind['ema_200'].iloc[-1]:>10.4f}")
        print(f"   MACD:            {ind['macd'].iloc[-1]:>+10.4f}")
        print(f"   MACD Señal:      {ind['macd_signal'].iloc[-1]:>+10.4f}")
        print(f"   MACD Histograma: {ind['macd_histogram'].iloc[-1]:>+10.4f}")
        print(f"   RSI (14):        {zona_rsi(ind['rsi'].iloc[-1])}")
        print(f"   BB Superior:     ${ind['bb_superior'].iloc[-1]:>10.4f}")
        print(f"   BB Media:        ${ind['bb_media'].iloc[-1]:>10.4f}")
        print(f"   BB Inferior:     ${ind['bb_inferior'].iloc[-1]:>10.4f}")
        print(f"   BB Posición:     {posicion_en_banda(precio, ind['bb_superior'].iloc[-1], ind['bb_inferior'].iloc[-1])}")
        print(f"   ATR (14):        ${ind['atr'].iloc[-1]:>10.4f}")

        # -- Patrón -----------------------------------------------------------
        print(f"\nPATRON DE VELA:  {self.patron}")

        # -- Confluencias ------------------------------------------------------
        print(f"\nCONFLUENCIAS ALCISTAS ({len(self.confluencias_long)}):")
        if self.confluencias_long:
            for c in self.confluencias_long:
                print(f"   {c}")
        else:
            print("   [MISS] Ninguna")
        print(f"   TOTAL SCORE: {self.decision['total_long']}/10")

        print(f"\nCONFLUENCIAS BAJISTAS ({len(self.confluencias_short)}):")
        if self.confluencias_short:
            for c in self.confluencias_short:
                print(f"   {c}")
        else:
            print("   [MISS] Ninguna")
        print(f"   TOTAL SCORE: {self.decision['total_short']}/10")

        if self.regime:
            print(f"\n🔍 Régimen detectado: {self.regime} (ADX: {self.adx_val:.1f})")

        # -- Decisión ---------------------------------------------------------
        print(f"\n{sep}")
        print("   DECISION FINAL")
        print(sep)
        dir_ = self.decision['direccion']
        if dir_ == 'LONG':
            print("   -> SEÑAL: COMPRA (LONG)")
        elif dir_ == 'SHORT':
            print("   -> SEÑAL: VENTA (SHORT)")
        else:
            print("   -> SEÑAL: SIN OPERACION")
        print(f"   📝 {self.decision['razon']}")

        # ── Gestión de riesgo ─────────────────────────────────────────────────
        if dir_ in ('LONG', 'SHORT') and self.decision['gestion']:
            g = self.decision['gestion']
            print(f"\n💰 GESTIÓN DE RIESGO:")
            print(f"   Precio entrada:       ${g['precio_entrada']:>10.4f}")
            print(f"   Stop Loss:            ${g['stop_loss']:>10.4f}  "
                  f"(distancia: {abs(g['precio_entrada'] - g['stop_loss']):.4f})")
            print(f"   Take Profit:          ${g['take_profit']:>10.4f}  "
                  f"(distancia: {abs(g['take_profit'] - g['precio_entrada']):.4f})")
            print(f"   ATR usado:            ${g['atr']:>10.4f}")
            print(f"   Capital total:        ${g['capital_total']:>10,.2f}")
            print(f"   Capital en riesgo:    ${g['capital_en_riesgo']:>10.2f}  "
                  f"({self.riesgo * 100:.1f}%)")
            print(f"   Tamaño posición:      {g['tamano_posicion']:>10.2f} unidades")
            print(f"   Valor posición:       ${g['valor_posicion']:>10,.2f}")
            print(f"   Ratio Riesgo:Beneficio  1 : {g['ratio_riesgo']:.2f}")

        print(f"\n{sep}")
        print("   ANALISIS COMPLETADO")
        print(sep + "\n")
