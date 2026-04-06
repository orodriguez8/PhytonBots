import os
import sys
import pandas as pd
import datetime

# Aseguramos que la ruta raíz esté disponible para que los imports funcionen
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.data.alpaca import obtener_datos_alpaca
from src.bot.trading_bot import TradingBot
from src.core.config import WATCHLIST

def run_backtest_single(symbol, timeframe='1Hour', limit=2000):
    print(f"\n[Analizando] {symbol} ({limit} velas de {timeframe})...")
    
    # Suprimir warnings y logs sueltos
    sys.stdout = open(os.devnull, 'w')
    
    # Descargamos el histórico
    df = obtener_datos_alpaca(symbol=symbol, limit=limit, timeframe=timeframe)
    if df is None or df.empty:
        sys.stdout = sys.__stdout__
        print(f"[Error] No se obtuvieron datos para {symbol}.")
        return None
    
    capital_inicial = 10000.0
    capital = capital_inicial
    posicion = None  
    historial_trades = []
    
    is_crypto = '/' in symbol or 'USD' in symbol
    bot = TradingBot(df, capital, is_crypto=is_crypto)
    bot.calcular_indicadores()
    
    # Hacemos una copia del diccionario para no perder la referencia original
    ind_master = bot.indicadores.copy()
    
    for i in range(200, len(df)):
        vela = df.iloc[i]
        
        if posicion is not None:
            high = vela['high']
            low = vela['low']
            cerrar = False
            pnl = 0
            motivo = ""
            
            if posicion['side'] == 'LONG':
                if low <= posicion['sl']:
                    pnl = (posicion['sl'] - posicion['entry']) * posicion['qty']
                    cerrar, motivo = True, "Stop Loss"
                elif high >= posicion['tp']:
                    pnl = (posicion['tp'] - posicion['entry']) * posicion['qty']
                    cerrar, motivo = True, "Take Profit"
            elif posicion['side'] == 'SHORT':
                if high >= posicion['sl']:
                    pnl = (posicion['entry'] - posicion['sl']) * posicion['qty']
                    cerrar, motivo = True, "Stop Loss"
                elif low <= posicion['tp']:
                    pnl = (posicion['entry'] - posicion['tp']) * posicion['qty']
                    cerrar, motivo = True, "Take Profit"
            
            if cerrar:
                capital += pnl
                posicion['pnl'] = pnl
                historial_trades.append(posicion)
                posicion = None
            continue 
            
        df_corte = df.iloc[i-20:i+1]
        bot.datos = df_corte
        bot.indicadores = {} 
        for clave in ind_master:
            bot.indicadores[clave] = ind_master[clave].iloc[i-20:i+1]
            
        bot.detectar_patron()
        decision = bot.evaluar_entrada()
        
        if decision['direccion'] in ['LONG', 'SHORT'] and decision['gestion']:
            g = decision['gestion']
            posicion = {
                'side': decision['direccion'],
                'entry': g['precio_entrada'],
                'qty': g['tamano_posicion'],
                'sl': g['stop_loss'],
                'tp': g['take_profit']
            }

    # Restauramos la consola
    sys.stdout = sys.__stdout__
    
    trades_totales = len(historial_trades)
    ganadores = len([t for t in historial_trades if t['pnl'] > 0])
    
    delta_capital = capital - capital_inicial
    
    win_rate = (ganadores / trades_totales * 100) if trades_totales > 0 else 0
    
    print(f"[OK] {symbol} Terminado: {trades_totales} operaciones | WinRate: {win_rate:.1f}% | PnL: ${delta_capital:+,.2f}")
    
    return {
        'symbol': symbol,
        'pnl': delta_capital,
        'trades': trades_totales,
        'wins': ganadores
    }

if __name__ == "__main__":
    print("="*60)
    print(" INICIANDO MOTOR DE BACKTESTING MASIVO")
    print("="*60)
    
    # Parametros generales del backtest
    timeframe = '1Hour'
    limit = 2000
    
    crypto_watchlist = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'LTC/USD']
    print(f"Criptomonedas a analizar: {crypto_watchlist}")
    print(f"Acciones a analizar: {WATCHLIST}")
    
    resultados = []
    
    for symbol in WATCHLIST + crypto_watchlist:
        res = run_backtest_single(symbol, timeframe, limit)
        if res:
            resultados.append(res)
            
    # -- Imprimir Resumen General --
    if not resultados:
        print("\n[Vacio] No se obtuvieron resultados para procesar.")
        sys.exit()
        
    print("\n" + "="*60)
    print(" [RESUMEN GLOBAL (PORTAFOLIO)]")
    print("="*60)
    
    total_trades = sum(r['trades'] for r in resultados)
    total_wins = sum(r['wins'] for r in resultados)
    pnl_total = sum(r['pnl'] for r in resultados)
    capital_final_portfolio = (10000.0 * len(resultados)) + pnl_total # Si hubiéramos asignado 10k a cada activo
    
    print(f"   Activos analizados:  {len(resultados)}")
    print(f"   Trades Totales:      {total_trades}")
    if total_trades > 0:
        print(f"   Win Rate Global:     {(total_wins / total_trades) * 100:.1f}%")
    print(f"   Beneficio Neto:      ${pnl_total:+,.2f}")
    print("="*60)
