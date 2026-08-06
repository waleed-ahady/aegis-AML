from __future__ import annotations

import math

from aegis_aml.data.contracts import clean
from aegis_aml.data.generate import generate_demo_transactions
from aegis_aml.features.transaction import MODEL_FEATURES, FeatureState, build_causal_features


def test_offline_and_online_feature_parity_for_next_transaction() -> None:
    cleaned, _ = clean(generate_demo_transactions(rows=500, seed=3))
    history = cleaned.iloc[:-1].copy()
    current = cleaned.iloc[-1]
    offline = build_causal_features(cleaned).iloc[-1]
    state = FeatureState.from_frame(history)
    online = state.make_features(current.to_dict())

    for feature in MODEL_FEATURES:
        if isinstance(online[feature], str):
            assert online[feature] == offline[feature]
        else:
            assert math.isclose(
                float(online[feature]), float(offline[feature]), rel_tol=1e-8, abs_tol=1e-8
            )


def test_current_transaction_is_not_counted_in_its_own_history() -> None:
    cleaned, _ = clean(generate_demo_transactions(rows=200, seed=4))
    features = build_causal_features(cleaned)
    first_sender_row = features.groupby("from_account", sort=False).head(1)
    assert (first_sender_row["sender_prev_tx_count"] == 0).all()
