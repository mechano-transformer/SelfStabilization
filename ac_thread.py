"""
オートコリメータ読み取りスレッド
tkinter メインループをブロックせずにデータを収集する
"""
import threading
import time
from datetime import datetime
import math


class AcThread(threading.Thread):
    """オートコリメータからデータを収集するスレッド。"""

    def __init__(self, master, sample_period=0.1):
        super().__init__()
        self.daemon = True
        self.master = master
        self.sample_period = float(sample_period)
        self.running = False
        self.paused = False
        # スムージングバッファ
        self.x_buffer = []
        self.y_buffer = []

    def run(self):
        self.running = True
        while self.running:
            if not self.paused:
                self.read_ac_data()
            time.sleep(self.sample_period)

    def read_ac_data(self):
        try:
            if self.master.AC.is_open:
                self.master.AC.write("G\r\n".encode())
                output = str(self.master.AC.readline().decode("ascii")).split(",")

                dis= int(self.master.distance_box.get())
                # X 軸読み取り
                try:
                    self.master.xinrange= True

                    raw_x = float(output[2].strip())
                    self.master.angx=raw_x
                    #angle to distance 20260331 add
                    raw_x = dis* 1000 * math.tan(raw_x/1000)
                    
                    self.master.alnx = raw_x
                    if self.master.smoothing_enabled:
                        self.x_buffer.append(raw_x)
                        window = self.master.smoothing_window
                        if len(self.x_buffer) > window:
                            self.x_buffer.pop(0)
                        self.master.alnx_smooth = sum(self.x_buffer) / len(self.x_buffer)
                    else:
                        self.master.alnx_smooth = raw_x
                        self.x_buffer = []
                except:
                    self.master.xinrange = False
                    pass

                # Y 軸読み取り
                try:
                    self.master.yinrange= True
                    
                    raw_y = float(output[3].strip())
                    self.master.angy=raw_y
                    #angle to distance 20260331 add
                    raw_y = dis* 1000 * math.tan(raw_y/1000)
                    
                    self.master.alny = raw_y
                    if self.master.smoothing_enabled:
                        self.y_buffer.append(raw_y)
                        window = self.master.smoothing_window
                        if len(self.y_buffer) > window:
                            self.y_buffer.pop(0)
                        self.master.alny_smooth = sum(self.y_buffer) / len(self.y_buffer)
                    else:
                        self.master.alny_smooth = raw_y
                        self.y_buffer = []
                except:
                    self.master.yinrange= False
                    pass

                self.master.after(0, self.master.update_display)

                
                log_d_x = self.master.alnx_smooth if self.master.smoothing_enabled else self.master.alnx
                log_d_y = self.master.alny_smooth if self.master.smoothing_enabled else self.master.alny
                log_a_x = self.master.angx
                log_a_y = self.master.angy
                        
                if self.master.ADC_active:
                    stat = 1
                else:
                    stat = 0
                    self.master.ADC_error_x=log_d_x-self.master.ADC_target_x
                    self.master.ADC_error_y=log_d_y-self.master.ADC_target_y
                    self.master.after(0, self.master.update_ADC_display)

                # データロギング
                if self.master.test_running:
                    current_time = datetime.now()
                    if (self.master.last_log_time is None or
                            (current_time - self.master.last_log_time).total_seconds() >= self.master.logging_sample_period):
                        elapsed_time = (current_time - self.master.test_start_time).total_seconds()
                        self.master.logged_data.append({
                            'elapsed_time': elapsed_time,
                            'alnx': log_d_x,
                            'alny': log_d_y,
                            'angx': log_a_x,
                            'angy': log_a_y,
                            'errorx': self.master.ADC_error_x,
                            'errory': self.master.ADC_error_y,
                            'adc_stat':stat
                        })
                        self.master.last_log_time = current_time
        except Exception as e:
            print(f"Error reading AC data: {e}")

    def stop(self):
        self.running = False
