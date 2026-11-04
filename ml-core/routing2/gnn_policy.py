"""GNN compression of the road network and the deep decision network for next-hop MARL.

The network is a line graph: one graph node per road link, one graph edge per allowed turn. Every
report period a GNN compresses the whole network into one embedding per link and one vector for
the network. Between periods the embeddings are reused, so a decision only runs the small
decision network. Messages go both ways: from downstream, the way jams spread back, and from
upstream, where the inflow comes from.

Actor input per link: congestion from fleet reports, fleet load, alley flag, length, free-flow time.
The critic is used in training only and also sees the true count and speed of all vehicles.
"""

from __future__ import annotations

import torch
import torch.nn as nn

N_DYN_ACTOR = 2  # congestion, fleet load
N_DYN_TRUE = 2  # all vehicles per 10 m, speed / free-flow speed
N_STATIC = 3  # alley flag, log length, free-flow minutes
N_LOCAL = 6  # per candidate, fresh at the decision
N_GLOBAL = 2  # time of day, share of the fleet p


def prep_local(feat: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Raw candidate features [M, D, sumo_env.N_FEAT] -> [M, D, N_LOCAL]. Relative to the best exit."""
    ff, tt, n, togo, length, intent, live_togo = feat.unbind(-1)
    big = torch.full_like(ff, 1e6)
    a = torch.where(mask, ff + togo, big)
    b = torch.where(mask, tt + live_togo, big)
    rel_ff = ((a - a.min(1, keepdim=True).values) / 60.0).clamp(max=10.0)
    rel_tt = ((b - b.min(1, keepdim=True).values) / 60.0).clamp(max=10.0)
    congestion = torch.log(tt.clamp(min=1e-3) / ff.clamp(min=1e-3)).clamp(-1.0, 4.0)
    load = ((n + intent) / length.clamp(min=5.0) * 10.0).clamp(max=5.0)
    x = torch.stack([rel_ff, rel_tt, congestion, load, togo / 600.0, live_togo / 600.0], -1)
    return torch.where(mask.unsqueeze(-1), x, torch.zeros_like(x))


class EdgeGNN(nn.Module):
    def __init__(self, n_in: int, hidden: int, layers: int, frm: torch.Tensor, to: torch.Tensor, n_edges: int):
        super().__init__()
        self.register_buffer("link_from", frm, persistent=False)
        self.register_buffer("link_to", to, persistent=False)
        one = torch.ones(len(frm))
        self.register_buffer("n_succ", torch.zeros(n_edges).index_add_(0, frm, one).clamp(min=1).view(1, -1, 1),
                             persistent=False)
        self.register_buffer("n_pred", torch.zeros(n_edges).index_add_(0, to, one).clamp(min=1).view(1, -1, 1),
                             persistent=False)
        self.enc = nn.Sequential(nn.Linear(n_in, hidden), nn.ReLU(), nn.Linear(hidden, hidden))
        self.mix = nn.ModuleList(
            nn.Sequential(nn.Linear(3 * hidden, hidden), nn.ReLU(), nn.Linear(hidden, hidden)) for _ in range(layers)
        )
        self.norm = nn.ModuleList(nn.LayerNorm(hidden) for _ in range(layers))
        self.att = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """x [B, E, n_in] -> link embeddings [B, E, H], network vector [B, H]."""
        h = self.enc(x)
        for mix, norm in zip(self.mix, self.norm):
            down = torch.zeros_like(h).index_add_(1, self.link_from, h[:, self.link_to]) / self.n_succ
            up = torch.zeros_like(h).index_add_(1, self.link_to, h[:, self.link_from]) / self.n_pred
            h = norm(h + mix(torch.cat([h, down, up], -1)))
        w = torch.softmax(self.att(h), 1)
        return h, (w * h).sum(1)


class RoutingNet(nn.Module):
    def __init__(self, frm: torch.Tensor, to: torch.Tensor, static: torch.Tensor, hidden: int = 64, layers: int = 3,
                 heads: int = 4):
        super().__init__()
        E = static.shape[0]
        self.register_buffer("static", static, persistent=False)
        self.actor_gnn = EdgeGNN(N_DYN_ACTOR + N_STATIC, hidden, layers, frm, to, E)
        self.critic_gnn = EdgeGNN(N_DYN_ACTOR + N_DYN_TRUE + N_STATIC, hidden, layers, frm, to, E)
        self.token = nn.Sequential(nn.Linear(hidden + N_LOCAL, hidden), nn.ReLU(), nn.Linear(hidden, hidden))
        self.query = nn.Sequential(nn.Linear(hidden + N_GLOBAL, hidden), nn.ReLU(), nn.Linear(hidden, hidden))
        self.attn = nn.MultiheadAttention(hidden, heads, batch_first=True)
        self.attn_norm = nn.LayerNorm(hidden)
        self.score = nn.Sequential(nn.Linear(2 * hidden, hidden), nn.ReLU(), nn.Linear(hidden, hidden), nn.ReLU(),
                                   nn.Linear(hidden, 1))
        self.value = nn.Sequential(nn.Linear(2 * hidden + N_LOCAL + N_GLOBAL, 2 * hidden), nn.ReLU(),
                                   nn.Linear(2 * hidden, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    @classmethod
    def from_env(cls, env, hidden: int = 64, layers: int = 3) -> RoutingNet:
        static = torch.stack([env.g.is_alley.cpu().float(), torch.log1p(env.length.float()) / 5.0,
                              env.ff_edge.float() / 60.0], -1)
        return cls(env.frm, env.to, static, hidden, layers)

    def param_groups(self, lr_actor: float, lr_critic: float) -> list[dict]:
        critic = list(self.critic_gnn.parameters()) + list(self.value.parameters())
        ids = {id(p) for p in critic}
        actor = [p for p in self.parameters() if id(p) not in ids]
        return [{"params": actor, "lr": lr_actor}, {"params": critic, "lr": lr_critic}]

    def encode_actor(self, dyn: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """dyn [B, E, N_DYN_ACTOR]."""
        s = self.static.unsqueeze(0).expand(dyn.shape[0], -1, -1)
        return self.actor_gnn(torch.cat([dyn, s], -1))

    def encode_critic(self, dyn: torch.Tensor, true: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        s = self.static.unsqueeze(0).expand(dyn.shape[0], -1, -1)
        return self.critic_gnn(torch.cat([dyn, true, s], -1))

    @staticmethod
    def _cand(h: torch.Tensor, cand: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        return h[b.unsqueeze(1), cand.clamp(min=0)]

    def policy(self, h, z, cand, local, glob, b) -> torch.Tensor:
        """Logits [M, D]. h [B, E, H], z [B, H], cand and local [M, D, ...], glob [M, N_GLOBAL], b [M] into B."""
        mask = cand >= 0
        tok = self.token(torch.cat([self._cand(h, cand, b), local], -1))
        cmp, _ = self.attn(tok, tok, tok, key_padding_mask=~mask, need_weights=False)
        tok = self.attn_norm(tok + cmp)
        q = self.query(torch.cat([z[b], glob], -1)).unsqueeze(1).expand_as(tok)
        logits = self.score(torch.cat([tok, q], -1)).squeeze(-1)
        return logits.masked_fill(~mask, -1e9)

    def critic(self, h, z, cand, local, glob, b) -> torch.Tensor:
        """V of the deciding vehicle [M]."""
        m = (cand >= 0).unsqueeze(-1).float()
        div = m.sum(1).clamp(min=1.0)
        mean_h = (self._cand(h, cand, b) * m).sum(1) / div
        mean_local = (local * m).sum(1) / div
        return self.value(torch.cat([z[b], mean_h, mean_local, glob], -1)).squeeze(-1)
