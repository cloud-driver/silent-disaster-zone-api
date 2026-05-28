# Model Card: Silent Risk MLP

## Model Type

This project uses a small `MLPRegressor` neural network as the scoring layer for silent disaster risk.

## Purpose

The model converts village-level features into a `silent_risk_nn_score`.

It is designed as a replaceable scoring layer. The feature pipeline can stay the same while the model can later be retrained with real disaster labels.

## Important Limitation

The current MVP model is not trained on real disaster ground truth.

It is trained using pseudo-labels generated from the rule-based MVP formula. Therefore, the model should be interpreted as a proof-of-concept AI scoring layer, not as a verified disaster prediction model.

## Features

- static_risk_score
- sensor_gap_score
- sensor_realtime_score
- realtime_event_score
- rainfall_realtime_score
- landslide_realtime_score
- road_realtime_score
- report_count_6h
- report_count_24h
- elderly_ratio
- flood_risk_model
- debris_risk_model

## Output

- silent_risk_nn_score

## Training Command

```bash
python3 scripts/train_silent_risk_nn.py
````

## Inference Command

```bash
python3 scripts/apply_silent_risk_nn.py
```

## Future Training Labels

Future versions should use real labels such as:

* confirmed disaster reports
* field inspection results
* rescue dispatch records
* delayed-report disaster zones
* expert-labeled priority-check villages