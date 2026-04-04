
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
                 min_confluencias: int   = MIN_CONFLUENCIAS):

        self.datos            = datos.copy()
        self.capital          = capital
        self.riesgo           = riesgo
        self.min_confluencias = min_confluencias

        # Estado interno — se rellenan al llamar a ejecutar()
        self.indicadores       = {}
        self.confluencias_long  = []
        self.confluencias_short = []
        self.patron            = None
        self.decision          = None

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

        # Volumen Medio
        self.indicadores['volumen_medio'] = calcular_volumen_medio(self.datos)

        print("   [OK] EMA 20 / 50 / 200")
        print("   [OK] MACD (12, 26, 9)")
        print("   [OK] RSI (14)")
        print("   [OK] Bandas de Bollinger (20, 2)")
        print("   [OK] ATR (14)")
        print("   [OK] Volumen Medio (20)")

    # ── 2. Detección de patrón de vela ───────────────────────────────────────
    def detectar_patron(self) -> str:
        """Detecta el patrón de vela de la última vela y lo almacena."""
        self.patron = detectar_patron(self.datos)
        return self.patron

    # ── 3. Evaluación de entrada ──────────────────────────────────────────────
    def evaluar_entrada(self) -> dict:
        """
        Cuenta las confluencias alcistas y bajistas y decide si operar,
        en qué dirección y con qué gestión de riesgo.

        Returns:
            Diccionario con la decisión completa de la operación
        """
        resultado = contar_confluencias(self.datos, self.indicadores)

        self.confluencias_long  = resultado['long']
        self.confluencias_short = resultado['short']
        total_long              = resultado['total_long']
        total_short             = resultado['total_short']

        precio   = self.datos['close'].iloc[-1]
        atr      = self.indicadores['atr'].iloc[-1]
        decision = {
            'direccion':   'NEUTRAL',
            'total_long':  total_long,
            'total_short': total_short,
            'gestion':     None,
            'razon':       '',
        }

        # Lógica de decisión: más confluencias en una dirección y supera el mínimo
        if total_long >= self.min_confluencias and total_long > total_short:
            decision['direccion'] = 'LONG'
            decision['gestion']   = calcular_gestion_riesgo(
                'LONG', precio, atr, self.capital, riesgo=self.riesgo)
            decision['razon'] = f"Señal LONG con {total_long} confluencias alcistas"

        elif total_short >= self.min_confluencias and total_short > total_long:
            decision['direccion'] = 'SHORT'
            decision['gestion']   = calcular_gestion_riesgo(
                'SHORT', precio, atr, self.capital, riesgo=self.riesgo)
            decision['razon'] = f"Señal SHORT con {total_short} confluencias bajistas"

        elif total_long >= self.min_confluencias and total_short >= self.min_confluencias:
            decision['razon'] = "Señales contradictorias — Mercado indeciso, no operar"
        else:
            decision['razon'] = (
                f"Confluencias insuficientes "
                f"(LONG: {total_long} | SHORT: {total_short} | Mín: {self.min_confluencias})"
            )

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

        print(f"\nCONFLUENCIAS BAJISTAS ({len(self.confluencias_short)}):")
        if self.confluencias_short:
            for c in self.confluencias_short:
                print(f"   {c}")
        else:
            print("   [MISS] Ninguna")

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
