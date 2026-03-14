import logging

# Configurar logs básicos
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def notify_signal(strategy_name, signal, symbol):
    """
    Función simple para notificar señales. 
    Puedes expandir esto para enviar mensajes a Telegram, Discord, etc.
    """
    if signal != "HOLD":
        message = f"🚨 SEÑAL EN {symbol} | ESTRATEGIA: {strategy_name} | ACCIÓN: {signal}"
        logger.warning(message)
        # Aquí podrías añadir una llamada a un bot de Telegram o similar
        # send_telegram_message(message)
