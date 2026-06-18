"""
ADC 制御スレッド — 単純P制御 + 時間ベース待機（CLI版と同一ロジック）
"""
import threading
import time

# ---------------------------------------------------------------------------
# CLI の cmd_adc と同一のデフォルト値
ADC_KP: float = 0.7
ADC_MAX_STEP_PULSES: int = 50000
ADC_PULSES_PER_UNIT: float = 37.0
ADC_CONVERGENCE_THR: float = 0.1
ADC_SAMPLE_PERIOD: float = 0.5

MOTOR_HZ: float = 1500.0
SETTLE_TIME: float = 0.5
# ---------------------------------------------------------------------------


class ADCControlThread(threading.Thread):

    def __init__(self, master, sample_period: float = ADC_SAMPLE_PERIOD):
        super().__init__()
        self.daemon = True
        self.master = master
        self.sample_period = float(sample_period)
        self.running = False
        self.paused = False

        self.pulses_per_unit: float = ADC_PULSES_PER_UNIT
        self.kp: float = ADC_KP
        self.max_step_pulses: int = ADC_MAX_STEP_PULSES
        self.convergence_threshold: float = ADC_CONVERGENCE_THR

    def run(self) -> None:
        self.running = True
        iteration = 0
        print("ADC control thread started")
        print(f"  kp={self.kp}, ppu={self.pulses_per_unit}")
        print(f"  max_step={self.max_step_pulses}, threshold={self.convergence_threshold}")
        print(f"  swap_axes={self.master.swap_axes}")
        print(f"  reverse_axis1={self.master.reverse_axis1}, reverse_axis2={self.master.reverse_axis2}")

        while self.running:
            if not self.paused and self.master.ADC_active:
                try:
                    self._control_step(iteration)
                    iteration += 1
                except Exception as e:
                    print(f"ADC control error: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                time.sleep(0.1)

        print("ADC control thread stopped")

    def _read_errors(self):
        current_x = self.master.alnx_smooth if self.master.smoothing_enabled else self.master.alnx
        current_y = self.master.alny_smooth if self.master.smoothing_enabled else self.master.alny
        return current_x - self.master.ADC_target_x, current_y - self.master.ADC_target_y

    def _get_axes(self):
        if self.master.swap_axes:
            return 1, 2
        return 2, 1

    def _control_step(self, iteration: int) -> None:
        pamc = self.master.pamc
        if not pamc.is_connected:
            return

        axis_x, axis_y = self._get_axes()
        error_x, error_y = self._read_errors()
        self.master.ADC_error_x = error_x
        self.master.ADC_error_y = error_y

        # 収束判定
        if abs(error_x) <= self.convergence_threshold and abs(error_y) <= self.convergence_threshold:
            print(f"ADC [{iteration}] CONVERGED  X={error_x:+.4f} Y={error_y:+.4f}")
            self.master.after(0, self.master._on_ADC_converged)
            self.running = False
            return

        # X パルス計算（CLIと同一: -round(kp * error * ppu), clamp, reverse）
        pulses_x = 0
        if abs(error_x) > self.convergence_threshold:
            pulses_x = -int(round(self.kp * error_x * self.pulses_per_unit))
            pulses_x = max(-self.max_step_pulses, min(self.max_step_pulses, pulses_x))
            if axis_x == 1 and self.master.reverse_axis1:
                pulses_x = -pulses_x
            elif axis_x == 2 and self.master.reverse_axis2:
                pulses_x = -pulses_x

        # Y パルス計算
        pulses_y = 0
        if abs(error_y) > self.convergence_threshold:
            pulses_y = -int(round(self.kp * error_y * self.pulses_per_unit))
            pulses_y = max(-self.max_step_pulses, min(self.max_step_pulses, pulses_y))
            if axis_y == 1 and self.master.reverse_axis1:
                pulses_y = -pulses_y
            elif axis_y == 2 and self.master.reverse_axis2:
                pulses_y = -pulses_y

        print(f"ADC [{iteration}] X: err={error_x:+.4f} pls={pulses_x:+d} ch{axis_x} | "
              f"Y: err={error_y:+.4f} pls={pulses_y:+d} ch{axis_y}")

        # X 駆動 → 待ち → Y 駆動 → 待ち（CLIと同一の順次駆動）
        if pulses_x != 0:
            pamc.move_relative(axis_x, pulses_x)
            self.master.ADC_total_pulses_x += pulses_x
            time.sleep(abs(pulses_x) / MOTOR_HZ + SETTLE_TIME)

        if not self.running:
            return

        if pulses_y != 0:
            pamc.move_relative(axis_y, pulses_y)
            self.master.ADC_total_pulses_y += pulses_y
            time.sleep(abs(pulses_y) / MOTOR_HZ + SETTLE_TIME)

        self.master.after(0, self.master.update_ADC_display)

    def stop(self) -> None:
        self.running = False
