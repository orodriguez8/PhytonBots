import time

# --- Circuit Breaker State ---
CIRCUIT_MAX_FAILURES = 5
_consecutive_failures = 0
_is_paused = False
_pause_until = 0

def get_circuit_breaker_status():
    """Devuelve si el sistema está en pausa por errores técnicos."""
    global _is_paused, _pause_until
    if _is_paused and time.time() > _pause_until:
        _is_paused = False # Reset automático tras el tiempo de espera
        # No reseteamos _consecutive_failures aquí para que si falla el primer intento
        # vuelva a saltar el breaker de inmediato.
    return _is_paused

def record_success():
    global _consecutive_failures, _is_paused
    _consecutive_failures = 0
    _is_paused = False

def record_failure():
    global _consecutive_failures, _is_paused, _pause_until
    _consecutive_failures += 1
    if _consecutive_failures >= CIRCUIT_MAX_FAILURES and not _is_paused:
        _is_paused = True
        _pause_until = time.time() + 300 # Pausa de 5 minutos
        print(f"🚨 CIRCUIT BREAKER TRIP: {CIRCUIT_MAX_FAILURES} errores seguidos. Pausando 5min.")
