"""
ADC 制御スレッド — P制御 + 時間ベース待機 + 詳細ログ
"""
import threading
import time
import numpy as np

# ---------------------------------------------------------------------------
ADC_LEARNING_RATE: float = 0.3
ADC_MIN_STEP_PULSES: int = 1
ADC_MAX_STEP_PULSES: int = 10000
ADC_PULSES_PER_UNIT: float = round(1000 / 2.74, 2)
ADC_CONVERGENCE_THR: float = 0.01
ADC_SAMPLE_PERIOD: float = 0.5

MOTOR_HZ: float = 1500.0
AC_PERIOD: float = 0.5
FAR_KP: float = 0.9
NEAR_MULT: float = 5.0
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
        self.learning_rate_x: float = ADC_LEARNING_RATE
        self.learning_rate_y: float = ADC_LEARNING_RATE
        self.min_step_pulses: int = ADC_MIN_STEP_PULSES
        self.max_step_pulses: int = ADC_MAX_STEP_PULSES
        self.convergence_threshold: float = ADC_CONVERGENCE_THR
        self.settle_time: float = 0.0

        self.prev_error_x: float = 0.0
        self.prev_error_y: float = 0.0
        self.prev_pulses_x: int = 0
        self.prev_pulses_y: int = 0

    def run(self) -> None:
        self.running = True
        iteration = 0
        print("ADC control thread started")
        print(f"  pulses_per_unit={self.pulses_per_unit}")
        print(f"  lr_x={self.learning_rate_x}, lr_y={self.learning_rate_y}")
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

    def _calc_pulses(self, error: float, learning_rate: float) -> int:
        if abs(error) <= self.convergence_threshold:
            return 0
        near_zone = self.convergence_threshold * NEAR_MULT
        kp = FAR_KP if abs(error) > near_zone else learning_rate
        pulses = -int(round(kp * error * self.pulses_per_unit))
        if abs(error) <= near_zone:
            pulses = int(np.clip(pulses, -self.max_step_pulses, self.max_step_pulses))
        if abs(pulses) < self.min_step_pulses:
            pulses = self.min_step_pulses if error < 0 else -self.min_step_pulses
        return pulses

    def _apply_reverse(self, pulses: int, axis: int) -> int:
        if axis == 1 and self.master.reverse_axis1:
            return -pulses
        if axis == 2 and self.master.reverse_axis2:
            return -pulses
        return pulses

    def _move_and_wait(self, axis: int, pulses: int) -> bool:
        pamc = self.master.pamc
        if not pamc.is_connected:
            return False
        ok = pamc.move_relative(axis, pulses)
        if not ok:
            print(f"  [FAIL] move_relative ch{axis} {pulses:+d}")
            return False
        drive_time = abs(pulses) / MOTOR_HZ
        time.sleep(drive_time + AC_PERIOD)
        return True

    def _control_step(self, iteration: int) -> None:
        pamc = self.master.pamc
        if not pamc.is_connected:
            return

        axis_x, axis_y = self._get_axes()
        error_x, error_y = self._read_errors()
        self.master.ADC_error_x = error_x
        self.master.ADC_error_y = error_y

        pulses_x_raw = self._calc_pulses(error_x, self.learning_rate_x)
        pulses_x = self._apply_reverse(pulses_x_raw, axis_x)

        pulses_y_raw = self._calc_pulses(error_y, self.learning_rate_y)
        pulses_y = self._apply_reverse(pulses_y_raw, axis_y)

        print(f"ADC [{iteration}] X: err={error_x:+.4f} raw={pulses_x_raw:+d} rev={pulses_x:+d} ch{axis_x} | "
              f"Y: err={error_y:+.4f} raw={pulses_y_raw:+d} rev={pulses_y:+d} ch{axis_y}")

        if pulses_x != 0:
            self._move_and_wait(axis_x, pulses_x)
            self.master.ADC_total_pulses_x += pulses_x

        if not self.running:
            return

        if pulses_y != 0:
            self._move_and_wait(axis_y, pulses_y)
            self.master.ADC_total_pulses_y += pulses_y

        self.prev_error_x = error_x
        self.prev_error_y = error_y

        if abs(error_x) <= self.convergence_threshold and abs(error_y) <= self.convergence_threshold:
            print(f"ADC [{iteration}] CONVERGED")
            self.master.after(0, self.master._on_ADC_converged)
            self.running = False
            return

        self.master.after(0, self.master.update_ADC_display)

    def stop(self) -> None:
        self.running = False
