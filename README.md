# Self Stabilizer

オートコリメータ + ピエゾモーター (PAMC-204) による自動アライメント収束制御システム。

## 必要環境

- Windows, Python 3.10+, `pamc204.dll`

```bash
pip install pyserial numpy
```

---

## CLI（収束制御）

```bash
# 収束制御（target=0,0 に自動収束、閾値内で自動終了）
python cli.py adc --rev1 --kp 0.7 --ppu 37 --threshold 0.1

# 現在値確認
python cli.py status

# 方向テスト（駆動前後のAC値を表示）
python cli.py test_dir 1 3000

# 相対移動 / 停止
python cli.py move 1 3000
python cli.py stop_all
```

### ADC パラメータ

| パラメータ | デフォルト | 説明 |
|---|---|---|
| `--target_x/y` | 0.0 | 目標位置 (um) |
| `--kp` | 0.5 | 比例ゲイン (0.5〜0.9推奨) |
| `--ppu` | 9996.0 | Piezo calibration (pulses/um) |
| `--threshold` | 0.1 | 収束閾値 (um)。範囲内で自動終了 |
| `--max_step` | 50000 | 1ステップ最大パルス数 |
| `--max_iter` | 200 | 最大イテレーション数 |
| `--swap` | off | X/Y軸入替 |
| `--rev1/--rev2` | off | Axis 1/2 反転 |
| `--ac_port` | COM11 | オートコリメータCOMポート |
| `--addr` | 2 | PAMC-204 アドレス |
| `--distance` | 50.0 | センサー距離 (mm) |

### 現在の実機設定

```
python cli.py adc --rev1 --kp 0.7 --ppu 37 --threshold 0.1
# addr=2, ac_port=COM11, swap=なし, rev1=あり, rev2=なし, ppu≈37
```

---

## GUI

```bash
python main.py                          # PAMC-204 (デフォルト)
python main.py --mode pamc104 --port COM3  # PAMC-104
```

---

## ファイル構成

| ファイル | 説明 |
|---|---|
| `cli.py` | CLI収束制御ツール |
| `main.py` | GUIエントリーポイント |
| `gui.py` | GUI (ADCGUI) |
| `adc_thread.py` | ADC制御スレッド (GUI用) |
| `ac_thread.py` | オートコリメータ読み取りスレッド |
| `pamc204_wrapper.py` | PAMC-204 DLLラッパー |
| `pamc104_wrapper.py` | PAMC-104 RS232Cラッパー |
| `auto_divisioner.py` | 自動軸振り分け |
| `ADC_CONTROL.md` | ADC制御方式ドキュメント |
