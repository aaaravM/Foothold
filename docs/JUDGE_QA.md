# Judge Q&A

Every number here comes from `ml/artifacts/metrics.json`, and every one of them was measured on **synthetic** data. Say that plainly whenever you quote one.

**Why a GNN, when matrix factorisation wins on your own test set?**
It doesn't win everywhere, and we report both sides. On warm learners (people with history), MF has higher recall@10 (0.4034 vs 0.3814), NDCG@10 is a tie (GNN 0.2268, MF 0.2263), and MF is clearly better on course recommendations (NDCG@10 0.1686 vs 0.1342). On cold-start courses, both popularity (0.1218) and MF (0.1212) beat the GNN (0.105). The GNN earns its place on **jobs** and on **cold-start learners overall**: cold-start NDCG@10 is GNN 0.2669 vs MF 0.1635 vs popularity 0.1809, and on cold-start jobs it's 0.707 vs 0.2783. That matters because most of our users are new, with no history, and a skills graph can still reason from their sim-demonstrated skills. It also gives a one-line reason for each pick, which we show in **Picked for you** on the report and on Path (the old skills-graph explorer was removed). If we shipped tomorrow, we'd probably blend in MF for courses. This is all synthetic data, so none of it is proof about real learners.

**Why a constraint solver instead of just asking the LLM for a plan?**
LLMs are bad at hard constraints like "no classes before 9am, under $4,000, 10 hours a week, bus only". So we use the LLM only for the language part: it turns what the learner says into rules, and the learner confirms them. OR-Tools CP-SAT then solves exactly, and a verifier re-checks every plan (100% of CP-SAT plans verified across 520 route solves). Against a greedy baseline, CP-SAT matched feasibility (0.4808 both). When both found a plan (n = 250), it saved 0.832 months on average (up to 19) and was strictly better 10.4% of the time, with $0 average cost difference. To be honest, the solver's main win is correctness and the reject-and-re-solve loop, not big savings. Speed: p50 15 ms, p95 189.6 ms per request.

**Is the data real?**
It depends on the field, and every number in the app carries a label. REAL: O*NET 31.0 work styles and skills, CA EDD OEWS 2026 Q1 wages for Stockton-Lodi, CA EDD projections, college fee pages and 60 verified course listings, all retrieved 2026-10-24 (see `data/SOURCES.md`). SAMPLE: program schedules and part of the skill taxonomy, each shown with a "verify" link. SYNTHETIC: all model training and evaluation data and the talent pool. FICTIONAL: every person and employer, including Maya, Dev, Luis and Tri-Valley Freight. We have no real learner data yet.

**Is it fair?**
We built the audit, and on our synthetic pool **it fails**. The ranking never sees the group label (0.7 demonstrated skills + 0.3 recommender score). Pooled across postings, the impact ratio is 0.8804, which is above the four-fifths line. But per posting, only 1 of 8 passes, and the worst ratio is 0.2104. With 150 candidates in groups of 53/61/36 and a top-15 shortlist, each group expects only 4-6 selections, so one or two people swing the ratio. None of the per-posting failures is significant at p < 0.05. Skill match alone passes 0 of 8, so the recommender isn't what causes the gap. The point is that the employer sees this audit every time, and we report the failure instead of hiding it. On real data you'd need larger pools and a mitigation step.

**Privacy and consent?**
Employers see blind cards only: skills and sim bands, with no name, contact details or group label. To reach someone, they send a consent request. Only that learner can accept it, in their own inbox, and acceptance reveals contact details to that one employer only. Identity always comes from a signed token, never from request parameters. Aggregates (gap report, fairness) need at least 5 people per group. Coach conversations aren't written to disk (memory is in-process, 2 h TTL, contact details redacted), and the coach is not allowed to promise confidentiality. The LLM cache stores responses only, never prompts.

**Isn't this just ChatGPT with a career prompt?**
No. The LLM writes words. It doesn't make the decisions. Career fit comes from a trained MLP on real O*NET profiles. The next sim moment comes from a Bayesian information-gain selector. Plans come from CP-SAT. Recommendations come from a GNN. Tavily research summaries cite their sources and drop unsupported numbers. Every number the LLM writes is checked against the data (on our synthetic attack set the verifier caught 100% of 563 wrong claims with 0 false positives, but that set is our own list of attacks). The whole app runs with no LLM at all (`LLM_MODE=mock`). And three human interrupts (confirm rules, approve plan, pick who to contact) plus learner consent keep people in charge.

**How does "Live in your area" avoid making things up?**
It's a separate LangGraph research agent. It runs 3 Tavily searches in parallel, ranks the sources, and the LLM writes a summary that cites them. Any number in that summary that the sources don't support is dropped before it's shown, and every claim links to its source. It's live web content, so we present it as that, not as verified data.

**How can you support "any career" if career fit only covers 42 occupations?**
Search covers every O*NET 31.0 occupation with complete work-style data. For a non-core career, the workday moments are generated live from that occupation's O*NET work styles plus Tavily web research about the job. The 8 core careers use the hand-built event set. Generated workdays are LLM content, so treat them like the DRAFT events: useful for trying a job, not a measurement.

**If you rewrite moments per user, doesn't that break the adaptive selector?**
No. Personalization only rewrites the words. Each choice keeps its original trait and stat deltas, so the Bayesian selector's expected-information-gain math is unchanged.

**What happens with the "Something else..." free-text answer?**
The LLM scores the learner's own words against the same 21 traits, so it counts as evidence like a numbered choice. Crisis language is checked first and routes to the 988 Lifeline instead of being scored.

**How do you know it works end to end?**
`pytest` runs the API test suite (231 passed), and `scripts/e2e_golden.py` drives the golden path against the running API with the demo accounts (25/25 steps pass).

**Why 21 work styles?**
That's how many the source has: the Work Styles domain in O*NET 31.0 has 21 elements. The database gives Work Styles Impact for each occupation, and we convert that to 0..1 percentile ranks across the 891 occupations with complete data. Using O*NET's own 21 means every trait we score maps directly to a public, licensed (CC BY 4.0) occupation profile, rather than a personality model we invented.

**How accurate is the career fit model?**
On 8,400 synthetic noisy profiles over 42 occupations: MLP top-1 0.7133 and top-3 0.9196, against a cosine-similarity baseline at 0.7033 and 0.9038. On the 8 Foothold careers, top-1 is 0.9344 vs 0.9225. The MLP beats a strong simple baseline by about one point. That measures recovering an occupation from a partial profile, not accuracy on real people.

**Does the adaptive selector actually help?**
In simulation, yes. It reaches a confident match in 12.755 events on average, against 13.366 for Thompson sampling, 16.851 for random and 17.133 for a fixed order, and it converges within 20 events for 67.35% of players vs 44.0% for random. The trade-off is that it's confidently wrong more often (22.05% vs 12.2% for random), because the simulated players follow our own model family. So we show careers as "top 3", not as a verdict. This isn't deep reinforcement learning. It's Bayesian inference with information-gain selection.

**What about someone in crisis?**
Crisis language ends the coach graph at its first node, before any LLM call, and shows the verified 988 Lifeline text (call or text 988, chat, Spanish option) plus "If you're in immediate danger, call 911." The coach also blocks diagnoses, medication or legal advice, and any "as your therapist" framing.

**Can it run without your laptop?**
Not yet. Netlify (https://foothold-valley.netlify.app) serves the static site and discovers the API URL at runtime, but the agent API (FastAPI + LangGraph + PyTorch + OR-Tools) runs on the laptop behind a tunnel, with Supabase as the data mirror. A hosted API is the first item on our roadmap.
