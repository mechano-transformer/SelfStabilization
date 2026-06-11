# ADC 制御方式ドキュメント

## 制御アーキテクチャ: 2フェーズ制御

誤差の大きさに応じて遠方/近傍の2フェーズで制御方式を切り替える。

```
|error| > threshold * 2  →  遠方フェーズ (FAR)
|error| <= threshold * 2  →  近傍フェーズ (NEAR)
|error| <= threshold      →  収束 → 自動停止 + ポップアップ通知
```

### 遠方フェーズ (FAR)

目標: 最速で近傍圏内に到達する。

- **ゲイン**: 10.0 (キャリブレーション値の10倍で補正)
- **パルス計算**: `pulses = 10.0 * error * pulses_per_unit`
- **駆動方式**: fire-and-forget (`move_relative` のみ、`wait_for_stop` しない)
- **ループ間隔**: 10ms (モーター動作中でも次の誤差を読んで追加補正)
- **max_step_pulses** でクランプ

### 近傍フェーズ (NEAR)

目標: オーバーシュートなく精密に収束させる。

- **ゲイン**: 適応学習率 `learning_rate * max(0.2, |error| / near_boundary)`
- **パルス計算**: `pulses = adaptive_lr * error * pulses_per_unit`
- **駆動方式**: `move_relative` + `wait_for_stop` (完了待ち)
- **ループ間隔**: `sample_period` (GUI設定値)
- **min_step_pulses** で最小パルスを保証

### 収束判定

両軸が `convergence_threshold` 以内に入ったら:

1. GUI ステータスを「ADC: Converged」(青) に更新
2. ADC を自動停止 (Start/Stop ボタンのインタロック復帰)
3. ポップアップで最終エラー値を表示

## パラメータ一覧

### コード定数 (`adc_thread.py`)

| パラメータ | デフォルト | 説明 |
|---|---|---|
| `ADC_LEARNING_RATE` | 0.7 | 近傍フェーズの補正ゲイン |
| `ADC_MIN_STEP_PULSES` | 1 | 最小補正パルス数 |
| `ADC_MAX_STEP_PULSES` | 10000 | 最大補正パルス数 |
| `ADC_PULSES_PER_UNIT` | ~365 | キャリブレーション (pulses/unit) |
| `ADC_CONVERGENCE_THR` | 0.01 | 収束判定閾値 |
| `ADC_SAMPLE_PERIOD` | 0.05 | 近傍フェーズのループ周期 (秒) |
| `FAR_GAIN` | 10.0 | 遠方フェーズのゲイン (`_calc_pulses` 内) |

### GUI デフォルト (`gui.py`)

| 項目 | デフォルト |
|---|---|
| Max Step (pulses) | 10000 |
| Convergence Threshold | 0.1 |

### フェーズ別の挙動まとめ

| | 遠方 (FAR) | 近傍 (NEAR) | 収束 |
|---|---|---|---|
| 条件 | `|error| > thr*2` | `thr < |error| <= thr*2` | `|error| <= thr` |
| ゲイン | 10.0 | 0.14 ~ 0.7 | - |
| 完了待ち | なし | あり | - |
| ループ間隔 | 10ms | sample_period | 自動停止 |

## 制御フロー図

```
Start ADC
  │
  ▼
誤差計算 (error_x, error_y)
  │
  ├─ 両軸 <= threshold ──→ 収束 → 自動停止 + ポップアップ
  │
  ├─ いずれか > threshold*2 ──→ [FAR] ゲイン10.0, fire-and-forget, 10ms後に再計算
  │
  └─ それ以外 ──→ [NEAR] 適応学習率, wait_for_stop, sample_period後に再計算
```
