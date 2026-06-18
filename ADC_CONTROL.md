# ADC 制御方式ドキュメント

## 概要

オートコリメータの読み取り誤差をゼロに収束させる P 制御ループ。
CLI (`cli.py adc`) と GUI (`adc_thread.py`) で同一ロジックを使用する。

## 制御方式: 単純 P 制御 + 順次駆動

```
AC読み取り → 誤差計算 → パルス計算 → X軸駆動+待ち → Y軸駆動+待ち → 繰り返し
```

PAMC-204 は同時2軸駆動非対応のため、X → Y の順に順次駆動する。

### パルス計算

```
pulses = -round(Kp × error_um × ppu)
pulses = clamp(pulses, -max_step, +max_step)
if reverse: pulses = -pulses
```

- `error_um`: 現在位置 - 目標位置（um 単位）
- `ppu`: pulses per um（実測値 ≈ 37）
- `Kp`: 比例ゲイン（推奨 0.7）

### 待ち時間

各軸駆動後: `|pulses| / 1500 + 0.5s`

- 1500 Hz = モーター駆動速度（ハードウェア上限）
- 0.5s = 機械的セトル + AC 読み取り安定化

### 収束判定

両軸の |error| ≤ threshold で収束。CLI は自動終了、GUI は自動停止 + 表示更新。

## パラメータ

| パラメータ | 値 | 説明 |
|---|---|---|
| `Kp` | 0.7 | 比例ゲイン（GUI/CLI 共通デフォルト） |
| `ppu` | 37.0 | pulses/um（実測キャリブレーション値） |
| `threshold` | 0.1 um | 収束閾値 |
| `max_step` | 50000 | 1ステップ最大パルス数 |
| モーター速度 | 1500 Hz | ハードウェア上限、固定 |
| セトル時間 | 0.5s | 駆動後の待ち時間 |

## 軸構成（現在の実機）

| 設定 | 値 | 意味 |
|---|---|---|
| PAMC-204 Address | 2 (E02) | デバイスアドレス |
| Swap X/Y | OFF | X→ch2, Y→ch1 |
| Reverse Axis 1 | **ON** | ch1 +パルス → Y 減少方向 |
| Reverse Axis 2 | OFF | ch2 +パルス → X 増加方向 |
| AC Port | COM11 | オートコリメータ（38400bps） |
| PAMC-204 Port | COM10 | USB Serial (FTDI) |

## 使用コマンド (PAMC-204)

| コマンド | 構文 | 用途 |
|---|---|---|
| 相対移動 | `ExxmPRnnnn` | P制御によるステップ駆動 |
| 速度設定 | `ExxmVAnnnn` | connect() 時に 1500 Hz 固定 |
| 全軸停止 | `ExxAB` | 緊急停止 |

## 制御フロー図

```
Start ADC
  │
  ▼
AC読み取り (pos_x, pos_y in um) ←──────┐
  │                                      │
  ├─ err_x = pos_x - target_x           │
  ├─ err_y = pos_y - target_y           │
  │                                      │
  ├─ 両軸 |err| ≤ threshold             │
  │   → CONVERGED → 自動停止            │
  │                                      │
  ├─ |err_x| > threshold                │
  │   → pulses = -round(Kp*err*ppu)     │
  │   → move_relative(ch_x, pulses)     │
  │   → sleep(|pulses|/1500 + 0.5)      │
  │                                      │
  ├─ |err_y| > threshold                │
  │   → pulses = -round(Kp*err*ppu)     │
  │   → move_relative(ch_y, pulses)     │
  │   → sleep(|pulses|/1500 + 0.5)      │
  │                                      │
  └──────────────────────────────────────┘
```
