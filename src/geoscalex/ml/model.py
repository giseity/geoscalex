from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import torch
from torch import nn

from geoscalex.ml.features import FEATURE_DIM


@dataclass(frozen=True)
class ModelConfig:
    feature_dim: int = FEATURE_DIM
    hidden_dim: int = 128
    layers: int = 4
    heads: int = 4
    feedforward_dim: int = 512
    dropout: float = 0.1

    def dict(self) -> dict[str, Any]:
        return asdict(self)


class RemoveMoveEncoder(nn.Module):
    def __init__(self, config: ModelConfig | None = None) -> None:
        super().__init__()
        self.config = config or ModelConfig()
        self.projection = nn.Linear(self.config.feature_dim, self.config.hidden_dim)
        self.position_projection = nn.Linear(1, self.config.hidden_dim)
        layer = nn.TransformerEncoderLayer(
            d_model=self.config.hidden_dim,
            nhead=self.config.heads,
            dim_feedforward=self.config.feedforward_dim,
            dropout=self.config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=self.config.layers)
        self.importance_head = nn.Linear(self.config.hidden_dim, 1)
        self.movement_output = nn.Linear(self.config.hidden_dim, 2)
        self.movement_head = nn.Sequential(
            nn.Linear(self.config.hidden_dim + 1, self.config.hidden_dim),
            nn.GELU(),
            self.movement_output,
        )
        nn.init.zeros_(self.movement_output.weight)
        nn.init.zeros_(self.movement_output.bias)

    def forward(
        self,
        features: torch.Tensor,
        padding_mask: torch.Tensor,
        budget_ratio: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        hidden = self.projection(features)
        hidden = hidden + self.position_projection(features[..., 10:11])
        hidden = self.encoder(hidden, src_key_padding_mask=padding_mask)
        importance = self.importance_head(hidden).squeeze(-1)
        budget = budget_ratio[:, None, None].expand(-1, hidden.shape[1], 1)
        displacement = torch.tanh(self.movement_head(torch.cat([hidden, budget], dim=-1))) * 0.05
        return importance, displacement
