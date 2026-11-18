import argparse
import inspect
import os
import sys
from pathlib import Path

import torch
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import GRPOConfig, GRPOTrainer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "correctness"))
from test_helpers import resolve_model

from data import load_problems, load_references, load_tests, build_prompt
from reward import (health_check, measure_remote, measure_batch, extract_code,
                    pass_fraction, composite_reward, FAILURE_BASE, FAILURE_SLOPE, SERVER)

CODE_ONLY = ("\n\nRespond with ONLY the complete Python solution inside a single "
             "```python code block. No explanation, just the code.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", required=True)
    ap.add_argument("-o", "--out", default="./grpo_out")
    ap.add_argument("--steps", type=int, default=50)
    ap.add_argument("--group-size", type=int, default=4)
    ap.add_argument("--max-completion-length", type=int, default=512)
    ap.add_argument("-n", "--limit", type=int, default=0)
    a = ap.parse_args()

    model_name = resolve_model(a.model)

    h = health_check()
    if not h or not h.get("perf_available"):
        raise SystemExit(f"Chameleon energy server not ready at {SERVER}: {h}")
    print("Chameleon OK:", h)

    problems = load_problems(a.limit)
    refs = load_references()
    tests = load_tests()

    print("measuring reference solution per problem (one-time baseline)...")
    ref_meas = {}
    for p in problems:
        pid = p["problem_id"]
        code = refs.get(pid)
        if code is None:
            ref_meas[pid] = None
            continue
        ref_meas[pid] = measure_remote(code, tests.get(pid, []))

    tok = AutoTokenizer.from_pretrained(model_name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def to_prompt(p):
        return tok.apply_chat_template(
            [{"role": "user", "content": build_prompt(p) + CODE_ONLY}],
            tokenize=False, add_generation_prompt=True)

    ds = Dataset.from_list([{"prompt": to_prompt(p), "pid": p["problem_id"]} for p in problems])
    by_id = {p["problem_id"]: p for p in problems}

    def reward_fn(prompts, completions, pid, **kwargs):
        rewards = [None] * len(completions)
        batch_idx, batch_codes, batch_tests = [], [], []

        for i, (comp, this_pid) in enumerate(zip(completions, pid)):
            code = extract_code(comp)
            if not code or ("def " not in code and "class Solution" not in code):
                rewards[i] = FAILURE_BASE
                continue
            t = tests.get(this_pid, [])
            f = pass_fraction(code, t)
            if f < 1.0:
                rewards[i] = FAILURE_BASE + FAILURE_SLOPE * f
                continue
            batch_idx.append(i)
            batch_codes.append(code)
            batch_tests.append(t)

        if batch_codes:
            measured = measure_batch(batch_codes, batch_tests)
            for i, meas in zip(batch_idx, measured):
                ref = ref_meas.get(pid[i])
                if not meas or not meas.get("ok") or ref is None or not ref.get("ok"):
                    rewards[i] = 0.5
                else:
                    r, g = composite_reward(meas, ref)
                    rewards[i] = r

        return rewards

    model = AutoModelForCausalLM.from_pretrained(
        model_name, torch_dtype=torch.bfloat16,
        device_map="auto" if torch.cuda.is_available() else None)

    cfg_kwargs = dict(
        output_dir=a.out + "_ckpt",
        per_device_train_batch_size=len(problems),
        num_generations=a.group_size,
        max_steps=a.steps,
        max_completion_length=a.max_completion_length,
        learning_rate=1e-5,
        logging_steps=1,
        save_strategy="no",
        bf16=torch.cuda.is_available(),
        report_to=[],
    )
    if "scale_rewards" in inspect.signature(GRPOConfig.__init__).parameters:
        cfg_kwargs["scale_rewards"] = False

    trainer = GRPOTrainer(model=model, args=GRPOConfig(**cfg_kwargs),
                          train_dataset=ds, reward_funcs=reward_fn, processing_class=tok)
    trainer.train()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(out)
    tok.save_pretrained(out)
    print("model saved to", out.resolve())


if __name__ == "__main__":
    main()
