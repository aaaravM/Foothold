"""Heterogeneous graph recommender (brief 6.3). SYNTHETIC learners, real course/job/skill taxonomy.

Graph (data/processed): learner-has-skill, course-teaches-skill, job-requires-skill,
learner-completed-course, learner-placed-in-job (+ reverse edges for message passing).
Talent-pool cards (incl. the demo personas' cards cand_maya / cand_dev / cand_luis) join the
graph as feature-only learner nodes (skill edges, no supervision, never evaluated).

Split (seeded):
  * warm test: one completed course held out per learner with >= 2 courses; the placed job held
    out for 30% of placed learners. Skills that ONLY the held-out course teaches (among the
    learner's courses) are removed from that learner's training skills, because the synthetic
    generator derives skills from completed courses (otherwise the answer leaks through features).
  * cold-start test: 15% of learners with interactions lose ALL course/job links in training
    (and every skill their courses teach); they keep target career + remaining prior skills.
    (The data's own cold_start learners have no interactions, so they cannot be scored.)

Models: PyG HeteroConv(SAGEConv) full batch + BPR (falls back to a LightGCN-style pure PyTorch
model if PyG fails to import, recorded as model_type); BPR-MF; popularity.
Metrics: recall@10, NDCG@10 (train items excluded from ranking), courses and jobs, warm + cold.

Run:  C:/Users/MUTTA/.venvs/foothold/Scripts/python.exe ml/train_recommender.py
Writes ml/artifacts/recommender.npz + recommender.json and the "recommender" key of metrics.json.
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS_DIR, ROOT, now_iso, seed_everything, write_json, write_metrics  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

SEED = 7
DIM = 64
EPOCHS = 200
LR = 0.01
K = 10
COLD_FRAC = 0.15
JOB_HOLDOUT = 0.30
PROC = ROOT / "data" / "processed"


def _load(name):
    return json.loads((PROC / name).read_text(encoding="utf-8"))


def _list(obj, *keys):
    if isinstance(obj, list):
        return obj
    for k in keys:
        if isinstance(obj.get(k), list):
            return obj[k]
    return []


def build():
    skills = [s["id"] for s in _load("skills.json")]
    sidx = {s: i for i, s in enumerate(skills)}
    courses = _load("courses.json")
    jobs = _list(_load("jobs.json"), "jobs")
    careers = [c["id"] for c in _list(_load("careers.json"), "careers")]
    cidx = {c: i for i, c in enumerate(careers)}
    learners = _list(_load("synthetic/learners.json"), "learners")
    pool = _list(_load("synthetic/talent_pool.json"), "candidates")
    course_ids = [c["id"] for c in courses]
    job_ids = [j["id"] for j in jobs]
    co_idx = {c: i for i, c in enumerate(course_ids)}
    jo_idx = {j: i for i, j in enumerate(job_ids)}
    course_sk = [[s for s in c.get("skills", []) if s in sidx] for c in courses]
    job_sk = [[s for s in j.get("required_skills", []) if s in sidx] for j in jobs]

    raw = []
    for l in learners:
        raw.append((set(s for s in l["skills"] if s in sidx), [co_idx[c] for c in l["completed_courses"] if c in co_idx],
                    jo_idx.get(l.get("placed_job")) if l.get("placed_job") else None))
    lnodes = [l["id"] for l in learners]
    lcareer = [l.get("target_career") for l in learners]
    lskills, train_c, train_j, test_c, test_j, is_cold = holdout(raw, course_sk, random.Random(SEED))
    n_syn = len(lnodes)
    for card in pool:
        b = card.get("blind") or {}
        lnodes.append("tp:" + card["id"])
        lskills.append(sorted(s for s in b.get("demonstrated_skills", []) if s in sidx))
        lcareer.append(b.get("target_career"))
        is_cold.append(False)
    return dict(raw=raw, skills=skills, sidx=sidx, careers=careers, cidx=cidx, course_ids=course_ids, job_ids=job_ids,
                course_sk=course_sk, job_sk=job_sk, lnodes=lnodes, lskills=lskills, lcareer=lcareer, n_syn=n_syn,
                train_c=train_c, train_j=train_j, test_c=test_c, test_j=test_j, is_cold=is_cold,
                n_learners_data=len(learners), n_pool=len(pool))


def holdout(raw, course_sk, rng):
    """raw[i] = (skills set, course idx list, job idx|None) -> train/test split (see module docstring)."""
    interacting = [i for i, (_, cs, jb) in enumerate(raw) if cs or jb is not None]
    cold = set(rng.sample(interacting, int(round(COLD_FRAC * len(interacting)))))
    lskills, train_c, train_j, test_c, test_j, is_cold = [], [], [], {}, {}, []
    for i, (sk0, cs0, jb) in enumerate(raw):
        sk, cs = set(sk0), list(cs0)
        held_c, held_j = [], []
        if i in cold:
            held_c, cs = cs, []
            if jb is not None:
                held_j, jb = [jb], None
            for c in held_c:
                sk -= set(course_sk[c])
        else:
            if len(cs) >= 2:
                h = cs.pop(rng.randrange(len(cs)))
                held_c = [h]
                keep = set().union(*[set(course_sk[c]) for c in cs]) if cs else set()
                sk -= (set(course_sk[h]) - keep)
            if jb is not None and rng.random() < JOB_HOLDOUT:
                held_j, jb = [jb], None
        lskills.append(sorted(sk))
        is_cold.append(i in cold)
        train_c += [(i, c) for c in cs]
        if jb is not None:
            train_j.append((i, jb))
        if held_c:
            test_c[i] = held_c
        if held_j:
            test_j[i] = held_j
    return lskills, train_c, train_j, test_c, test_j, is_cold


def validation_split(G):
    """Carve a validation split out of the TRAINING data only (same procedure, different seed)."""
    tc, tj = {}, {}
    for u, c in G["train_c"]:
        tc.setdefault(u, []).append(c)
    for u, j in G["train_j"]:
        tj[u] = j
    raw = [(set(G["lskills"][i]), tc.get(i, []), tj.get(i)) for i in range(G["n_syn"])]
    lsk, trc, trj, vc, vj, cold = holdout(raw, G["course_sk"], random.Random(SEED + 1))
    V = dict(G)
    V.update(lskills=lsk + G["lskills"][G["n_syn"]:], train_c=trc, train_j=trj, test_c=vc, test_j=vj,
             is_cold=cold + G["is_cold"][G["n_syn"]:])
    return V


def multihot(rows, idx, n):
    x = torch.zeros(len(rows), n)
    for r, items in enumerate(rows):
        for s in items:
            if s in idx:
                x[r, idx[s]] = 1.0
    return x


def tensors(G, interactions=True):
    nS, nC = len(G["skills"]), len(G["careers"])
    xl = torch.cat([multihot(G["lskills"], G["sidx"], nS), multihot([[c] if c else [] for c in G["lcareer"]], G["cidx"], nC)], 1)
    xc = multihot(G["course_sk"], G["sidx"], nS)
    xj = multihot(G["job_sk"], G["sidx"], nS)

    def ei(pairs):
        if not pairs:
            return torch.zeros(2, 0, dtype=torch.long)
        return torch.tensor(pairs, dtype=torch.long).t().contiguous()

    ls = [(i, G["sidx"][s]) for i, sk in enumerate(G["lskills"]) for s in sk]
    cs = [(i, G["sidx"][s]) for i, sk in enumerate(G["course_sk"]) for s in sk]
    js = [(i, G["sidx"][s]) for i, sk in enumerate(G["job_sk"]) for s in sk]
    E = {
        ("learner", "has", "skill"): ei(ls), ("course", "teaches", "skill"): ei(cs), ("job", "requires", "skill"): ei(js),
    }
    if interactions:  # learner-course / learner-job edges also used for message passing (else supervision only)
        E[("learner", "completed", "course")] = ei(G["train_c"])
        E[("learner", "placed", "job")] = ei(G["train_j"])
    for (a, r, b), e in list(E.items()):
        E[(b, "rev_" + r, a)] = e.flip(0)
    return {"learner": xl, "course": xc, "job": xj}, E


class HeteroGNN(nn.Module):
    def __init__(self, x, E, n_skill, model_type, use_id=True):
        super().__init__()
        self.model_type = model_type
        self.use_id = use_id
        self.bias = nn.ParameterDict({"course": nn.Parameter(torch.zeros(x["course"].shape[0], 1)),
                                      "job": nn.Parameter(torch.zeros(x["job"].shape[0], 1))})
        self.proj = nn.ModuleDict({t: nn.Linear(v.shape[1], DIM) for t, v in x.items()})
        self.id_emb = nn.ModuleDict({"course": nn.Embedding(x["course"].shape[0], DIM),
                                     "job": nn.Embedding(x["job"].shape[0], DIM), "skill": nn.Embedding(n_skill, DIM)})
        for e in self.id_emb.values():
            nn.init.normal_(e.weight, std=0.1)
        self.n_skill = n_skill
        self.etypes = list(E.keys())
        if model_type.startswith("pyg"):
            from torch_geometric.nn import HeteroConv, SAGEConv
            self.convs = nn.ModuleList([HeteroConv({et: SAGEConv((-1, -1), DIM) for et in self.etypes}, aggr="sum")
                                        for _ in range(2)])

    def inputs(self, x):
        h = {t: self.proj[t](v) for t, v in x.items()}
        if self.use_id:
            h["course"] = h["course"] + self.id_emb["course"].weight
            h["job"] = h["job"] + self.id_emb["job"].weight
        h["skill"] = self.id_emb["skill"].weight
        return h

    def forward(self, x, E):
        h = self._embed(x, E)
        # learnable item bias folded into the dot product: learner gets a constant 1 column
        return {"learner": torch.cat([h["learner"], torch.ones(h["learner"].shape[0], 1)], 1),
                "course": torch.cat([h["course"], self.bias["course"]], 1),
                "job": torch.cat([h["job"], self.bias["job"]], 1)}

    def _embed(self, x, E):
        h0 = self.inputs(x)
        if self.model_type.startswith("pyg"):
            h = h0
            for li, conv in enumerate(self.convs):
                h = conv(h, E)
                if li == 0:
                    h = {t: F.relu(v) for t, v in h.items()}
            return {t: h[t] + h0[t] for t in h0}
        # LightGCN-style fallback: mean propagation over the same typed edges, 2 hops, layer average
        layers = [h0]
        h = h0
        for _ in range(2):
            out = {t: torch.zeros_like(v) for t, v in h.items()}
            deg = {t: torch.zeros(v.shape[0], 1) for t, v in h.items()}
            for (a, _r, b), e in E.items():
                out[b].index_add_(0, e[1], h[a][e[0]])
                deg[b].index_add_(0, e[1], torch.ones(e.shape[1], 1))
            h = {t: out[t] / deg[t].clamp(min=1) for t in out}
            layers.append(h)
        return {t: sum(L[t] for L in layers) / len(layers) for t in h0}


class MF(nn.Module):
    def __init__(self, nl, nc, nj):
        super().__init__()
        self.bc, self.bj = nn.Parameter(torch.zeros(nc, 1)), nn.Parameter(torch.zeros(nj, 1))
        self.l, self.c, self.j = nn.Embedding(nl, DIM), nn.Embedding(nc, DIM), nn.Embedding(nj, DIM)
        for e in (self.l, self.c, self.j):
            nn.init.normal_(e.weight, std=0.1)

    def forward(self, *_):
        return {"learner": torch.cat([self.l.weight, torch.ones(self.l.weight.shape[0], 1)], 1),
                "course": torch.cat([self.c.weight, self.bc], 1), "job": torch.cat([self.j.weight, self.bj], 1)}


def bpr(h, pairs, kind, n_items, gen):
    if not pairs:
        return torch.tensor(0.0)
    p = torch.tensor(pairs)
    u, i = p[:, 0], p[:, 1]
    neg = torch.randint(0, n_items, (len(pairs),), generator=gen)
    hu = h["learner"][u]
    pos = (hu * h[kind][i]).sum(-1)
    ng = (hu * h[kind][neg]).sum(-1)
    return -F.logsigmoid(pos - ng).mean()


def train(model, x, E, G, wd, epochs=EPOCHS):
    gen = torch.Generator().manual_seed(SEED)
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=wd)
    nC, nJ = len(G["course_ids"]), len(G["job_ids"])
    losses = []
    for ep in range(epochs):
        model.train()
        opt.zero_grad()
        h = model(x, E)
        loss = bpr(h, G["train_c"], "course", nC, gen) + bpr(h, G["train_j"], "job", nJ, gen)
        loss.backward()
        opt.step()
        if ep % 20 == 0 or ep == epochs - 1:
            losses.append([ep, round(float(loss.detach()), 4)])
    model.eval()
    with torch.no_grad():
        h = model(x, E)
    return {t: v.detach().numpy().astype(np.float32) for t, v in h.items()}, losses


def evaluate(score_fn, G):
    """score_fn(learner_idx, kind) -> np.array over items. Returns metrics dict."""
    train_items = {"course": {}, "job": {}}
    for u, c in G["train_c"]:
        train_items["course"].setdefault(u, set()).add(c)
    for u, j in G["train_j"]:
        train_items["job"].setdefault(u, set()).add(j)
    acc = {(seg, kind): [] for seg in ("warm", "cold") for kind in ("course", "job")}
    for kind, tests in (("course", G["test_c"]), ("job", G["test_j"])):
        for u, targets in tests.items():
            s = score_fn(u, kind).astype(np.float64).copy()
            for t in train_items[kind].get(u, ()):
                s[t] = -np.inf
            top = np.argsort(-s, kind="stable")[:K]
            tset = set(targets)
            hits = [1.0 if t in tset else 0.0 for t in top]
            recall = sum(hits) / len(tset)
            dcg = sum(h / math.log2(r + 2) for r, h in enumerate(hits))
            idcg = sum(1 / math.log2(r + 2) for r in range(min(len(tset), K)))
            acc[("cold" if G["is_cold"][u] else "warm", kind)].append((recall, dcg / idcg))

    def agg(rows):
        if not rows:
            return {"recall@10": None, "ndcg@10": None, "n": 0}
        a = np.array(rows)
        return {"recall@10": round(float(a[:, 0].mean()), 4), "ndcg@10": round(float(a[:, 1].mean()), 4), "n": len(rows)}

    out = {}
    for seg in ("warm", "cold"):
        out[seg] = {"all": agg(acc[(seg, "course")] + acc[(seg, "job")]),
                    "courses": agg(acc[(seg, "course")]), "jobs": agg(acc[(seg, "job")])}
    return out


def main():
    t0 = time.time()
    seed_everything(SEED)
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    G = build()
    x, E = tensors(G)
    try:
        import torch_geometric  # noqa: F401
        from torch_geometric.nn import HeteroConv, SAGEConv  # noqa: F401
        model_type = "pyg_heteroconv_sage"
    except Exception as exc:  # noqa: BLE001
        print(f"PyG unavailable ({type(exc).__name__}); using LightGCN-style pure PyTorch fallback")
        model_type = "lightgcn_style_pytorch"

    def make_gnn(xx, EE, cfg):
        seed_everything(SEED)
        m = HeteroGNN(xx, EE, len(G["skills"]), model_type, use_id=cfg["use_id"])
        with torch.no_grad():
            m(xx, EE)  # materialize lazy (-1) shapes before the optimizer sees the params
        return m

    def make_mf(_xx, _EE, _cfg):
        seed_everything(SEED)
        return MF(len(G["lnodes"]), len(G["course_ids"]), len(G["job_ids"]))

    def dot(H):
        return lambda u, kind: H[kind] @ H["learner"][u]

    # model selection on a validation split carved from TRAINING data (the test split is never used here)
    V = validation_split(G)
    TV = {mp: tensors(V, interactions=mp) for mp in (True, False)}
    grids = {
        "gnn": [{"epochs": e, "wd": w, "use_id": u, "mp_interactions": mp}
                for e in (100, 300) for w in (1e-5, 1e-4) for u in (True, False) for mp in (True, False)],
        "mf": [{"epochs": e, "wd": w} for e in (100, 300) for w in (1e-5, 1e-4)],
    }
    selection, best = {}, {}
    for name, make in (("gnn", make_gnn), ("mf", make_mf)):
        rows = []
        for cfg in grids[name]:
            xv, Ev = TV[cfg.get("mp_interactions", True)]
            Hv, _ = train(make(xv, Ev, cfg), xv, Ev, V, wd=cfg["wd"], epochs=cfg["epochs"])
            r = evaluate(dot(Hv), V)
            val = (r["warm"]["all"]["ndcg@10"] + r["cold"]["all"]["ndcg@10"]) / 2
            rows.append({**cfg, "val_ndcg@10_mean_warm_cold": round(val, 4)})
        rows.sort(key=lambda z: -z["val_ndcg@10_mean_warm_cold"])
        selection[name], best[name] = rows, rows[0]
        print("selected", name, rows[0]); print("  grid", rows)

    tg = time.time()
    cg = best["gnn"]
    xg, Eg = tensors(G, interactions=cg["mp_interactions"])
    H_gnn, loss_gnn = train(make_gnn(xg, Eg, cg), xg, Eg, G, wd=cg["wd"], epochs=cg["epochs"])
    gnn_s = time.time() - tg
    tm = time.time()
    cm = best["mf"]
    H_mf, loss_mf = train(make_mf(x, E, cm), x, E, G, wd=cm["wd"], epochs=cm["epochs"])
    mf_s = time.time() - tm

    pop_c = np.zeros(len(G["course_ids"]), np.float32)
    pop_j = np.zeros(len(G["job_ids"]), np.float32)
    for _, c in G["train_c"]:
        pop_c[c] += 1
    for _, j in G["train_j"]:
        pop_j[j] += 1

    res = {"gnn": evaluate(dot(H_gnn), G), "mf": evaluate(dot(H_mf), G),
           "popularity": evaluate(lambda u, kind: (pop_c if kind == "course" else pop_j), G)}
    winner = {seg: max(res, key=lambda m: res[m][seg]["all"]["ndcg@10"] or 0) for seg in ("warm", "cold")}

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        ARTIFACTS_DIR / "recommender.npz",
        gnn_learner=H_gnn["learner"], gnn_course=H_gnn["course"], gnn_job=H_gnn["job"],
        mf_learner=H_mf["learner"], mf_course=H_mf["course"], mf_job=H_mf["job"],
        pop_course=pop_c, pop_job=pop_j,
    )
    train_items = {}
    for u, c in G["train_c"]:
        train_items.setdefault(G["lnodes"][u], {"courses": [], "jobs": []})["courses"].append(G["course_ids"][c])
    for u, j in G["train_j"]:
        train_items.setdefault(G["lnodes"][u], {"courses": [], "jobs": []})["jobs"].append(G["job_ids"][j])
    elapsed = round(time.time() - t0, 1)
    sidecar = {
        "model_type": model_type, "dim": DIM, "config": best, "lr": LR, "seed": SEED, "k": K,
        "learner_ids": G["lnodes"], "course_ids": G["course_ids"], "job_ids": G["job_ids"],
        "n_synthetic_learners": G["n_syn"], "learner_skills_train": dict(zip(G["lnodes"], G["lskills"])),
        "train_items": train_items, "cold_eval_learners": [G["lnodes"][i] for i in range(G["n_syn"]) if G["is_cold"][i]],
        "metrics": res, "winner": winner, "trained_at": now_iso(), "train_seconds": elapsed,
        "provenance": "SYNTHETIC", "fictional": True,
    }
    write_json(ARTIFACTS_DIR / "recommender.json", sidecar)

    nE = {"/".join(k): int(v.shape[1]) for k, v in E.items() if not k[1].startswith("rev_")}
    block = {
        "status": "trained", "provenance": "SYNTHETIC", "seed": SEED, "trained_at": now_iso(),
        "data": {"learners": G["n_learners_data"], "talent_cards_feature_only": G["n_pool"], "skills": len(G["skills"]),
                 "courses": len(G["course_ids"]), "jobs": len(G["job_ids"]), "edges": nE,
                 "test_courses": len(G["test_c"]), "test_jobs": len(G["test_j"]),
                 "cold_start_eval_learners": sum(G["is_cold"][: G["n_syn"]]),
                 "source": "data/processed (synthetic learners; course/job/skill taxonomy)"},
        "reproduce": "C:/Users/MUTTA/.venvs/foothold/Scripts/python.exe ml/train_recommender.py",
        "model_type": model_type,
        "gnn": res["gnn"], "mf": res["mf"], "popularity": res["popularity"],
        "winner": winner,
        "selection": {"method": "grid search on a validation split carved from training data (seed 8); test untouched",
                      "gnn": selection["gnn"], "mf": selection["mf"]},
        "train_seconds": {"total": elapsed, "gnn": round(gnn_s, 1), "mf": round(mf_s, 1)},
        "loss_curve": {"gnn": loss_gnn, "mf": loss_mf},
        "note": ("Synthetic learners whose skills were generated from their completed courses; skills only a held-out "
                 "course teaches are removed from training features. Cold-start = 15% of interacting learners with all "
                 "course/job links (and their course-taught skills) hidden. Ranking excludes training items."),
    }
    write_metrics("recommender", block)
    print(json.dumps({"model_type": model_type, "seconds": elapsed, "winner": winner,
                      **{m: {seg: res[m][seg]["all"] for seg in ("warm", "cold")} for m in res}}, indent=1))
    for m in res:
        for seg in ("warm", "cold"):
            print(m, seg, "courses", res[m][seg]["courses"], "jobs", res[m][seg]["jobs"])


if __name__ == "__main__":
    main()
