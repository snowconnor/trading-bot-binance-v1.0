import pandas as pd
import os
from datetime import datetime

class TradeLogger:
    def __init__(self, csv_file="trade_log.csv", excel_file="reporte_diario.xlsx"):
        self.csv_file = csv_file
        self.excel_file = excel_file

    def log_trade(self, symbol, strategy, action, price, sl, tp, qty, risk, order_id):
        """Registra el trade en CSV y actualiza el reporte diario."""
        data = {
            "fecha": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "par": [symbol],
            "estrategia": [strategy],
            "acción": [action],
            "precio_entrada": [price],
            "stop_loss": [sl],
            "take_profit": [tp],
            "cantidad": [qty],
            "riesgo_usdt": [risk],
            "order_id": [order_id]
        }
        df = pd.DataFrame(data)
        
        # Guardar en CSV
        file_exists = os.path.isfile(self.csv_file)
        df.to_csv(self.csv_file, mode='a', index=False, header=not file_exists)
        
        # Guardar resumen en Excel (una hoja por día)
        date_str = datetime.now().strftime("%Y-%m-%d")
        if os.path.isfile(self.excel_file):
            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                # Leer hoja existente si existe, o crearla
                try:
                    existing_df = pd.read_excel(self.excel_file, sheet_name=date_str)
                    combined_df = pd.concat([existing_df, df])
                    combined_df.to_excel(writer, sheet_name=date_str, index=False)
                except ValueError: # La hoja no existe
                    df.to_excel(writer, sheet_name=date_str, index=False)
        else:
            with pd.ExcelWriter(self.excel_file, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name=date_str, index=False)
