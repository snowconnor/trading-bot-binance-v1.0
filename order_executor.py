import requests
import hmac
import hashlib
import time
import os
from urllib.parse import urlencode
from binance.client import Client
from binance.enums import *
from dotenv import load_dotenv

load_dotenv()

class OrderExecutor:
    """
    Gestiona la ejecución de órdenes en Binance Testnet utilizando requests para OCO avanzado.
    """
    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY")
        self.api_secret = os.getenv("BINANCE_API_SECRET")
        self.base_url = "https://testnet.binance.vision/api/v3"
        self.client = Client(self.api_key, self.api_secret, testnet=True)

    def round_price(self, price):
        """Redondea el precio a 2 decimales para cumplir con PRICE_FILTER."""
        return round(float(price), 2)

    def _sign_payload(self, params):
        params['timestamp'] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(self.api_secret.encode('utf-8'), 
                             query_string.encode('utf-8'), 
                             hashlib.sha256).hexdigest()
        params['signature'] = signature
        return params

    def get_balance(self, asset="USDT"):
        try:
            balance = self.client.get_asset_balance(asset=asset)
            return float(balance['free'])
        except Exception as e:
            print(f"Error consultando balance: {e}")
            return 0.0

    def execute_order(self, symbol, signal, levels):
        try:
            quantity = str(levels['position_size'])
            side = SIDE_BUY if signal == "BUY" else SIDE_SELL
            
            # 1. Ejecutar orden de mercado
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            print(f"Orden de mercado ejecutada: {order['orderId']}")

            # 2. Configurar OCO
            tp_price = self.round_price(levels['take_profit_price'])
            sl_price = self.round_price(levels['stop_loss_price'])
            
            if signal == "BUY":
                # Protegemos una posición larga vendiendo (SELL)
                # aboveType (TP): debe ser LIMIT_MAKER (mayor al precio)
                # belowType (SL): debe ser STOP_LOSS_LIMIT (menor al precio)
                params = {
                    "symbol": symbol,
                    "side": "SELL",
                    "quantity": quantity,
                    "aboveType": "LIMIT_MAKER",
                    "abovePrice": str(tp_price),
                    "belowType": "STOP_LOSS_LIMIT",
                    "belowStopPrice": str(sl_price),
                    "belowPrice": str(self.round_price(sl_price * 0.999)),
                    "belowTimeInForce": "GTC"
                }
            else:
                # Protegemos una posición corta comprando (BUY)
                # aboveType (SL): debe ser STOP_LOSS_LIMIT (mayor al precio)
                # belowType (TP): debe ser LIMIT_MAKER (menor al precio)
                params = {
                    "symbol": symbol,
                    "side": "BUY",
                    "quantity": quantity,
                    "aboveType": "STOP_LOSS_LIMIT",
                    "aboveStopPrice": str(sl_price),
                    "abovePrice": str(self.round_price(sl_price * 1.001)),
                    "aboveTimeInForce": "GTC",
                    "belowType": "LIMIT_MAKER",
                    "belowPrice": str(tp_price)
                }

            signed_params = self._sign_payload(params)
            headers = {'X-MBX-APIKEY': self.api_key}
            
            response = requests.post(f"{self.base_url}/orderList/oco", headers=headers, params=signed_params)
            
            if response.status_code == 200:
                print(f"Orden OCO colocada con éxito: {response.json()}")
            else:
                print(f"Error en OCO (Código {response.status_code}): {response.text}")
                
            return {"market": order, "oco": response.json() if response.status_code == 200 else None}

        except Exception as e:
            print(f"Error en ejecución OCO: {e}")
            return None
