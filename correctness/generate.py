import argparse
import json
import os
import time
from pathlib import Path

import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

from test_helpers import resolve_model

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATASET = ROOT / "dataset" / "problems.jsonl"
PROMPT_FILE = ROOT / "prompts" / "prompt_04_user.txt"
SYSTEM_FILE = ROOT / "prompts" / "prompt_04_system.txt"


def load_dataset():
    with open(DATASET) as f:
        return [json.loads(line) for line in f]


def load_prompt():
    system = SYSTEM_FILE.read_text().strip()
    user = PROMPT_FILE.read_text()
    return system, user


def build_prompt(user, entry):
    test_case = "\n".join(entry["small_test_cases"])
    return (f"{user}\n"
            f"# Task description:\n```python\n{entry['problem_description']}\n```\n"
            f"# Test case:\n```python\n{test_case}\n```")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-m", "--model", required=True)
    ap.add_argument("-r", "--run", type=int, required=True)
    ap.add_argument("-n", "--limit", type=int, default=0)
    a = ap.parse_args()

    model_name = resolve_model(a.model)
    model_id = model_name.split("/")[-1]
    out_dir = HERE / "results" / model_id / f"{model_id}_{a.run}"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "gen_log.txt"

    dataset = load_dataset()
    if a.limit:
        dataset = dataset[:a.limit]
    system, user = load_prompt()

    tok = AutoTokenizer.from_pretrained(model_name)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.bfloat16,
                                                 device_map="auto")
    model.eval()

    start = time.time()
    total_pure = 0.0
    total_in = 0
    total_out = 0

    with open(log_path, "w") as log:
        for entry in tqdm(dataset, desc="generating"):
            prompt = build_prompt(user, entry)
            messages = [{"role": "system", "content": system},
                        {"role": "user", "content": prompt}]
            text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            ids = tok(text, return_tensors="pt").to(model.device)

            t0 = time.time()
            with torch.no_grad():
                out = model.generate(**ids, max_new_tokens=768, do_sample=False,
                                     pad_token_id=tok.pad_token_id)
            pure = time.time() - t0

            in_tok = ids["input_ids"].shape[1]
            gen = out[0][in_tok:]
            completion = tok.decode(gen, skip_special_tokens=True).strip()

            entry["completion"] = completion
            entry["input_tokens"] = int(in_tok)
            entry["output_tokens"] = int(gen.shape[0])
            entry["pure_execution_time"] = round(pure, 4)

            total_in += int(in_tok)
            total_out += int(gen.shape[0])
            total_pure += pure
            log.write(f"problem_idx {entry['problem_id']}  in={in_tok} out={gen.shape[0]} t={pure:.2f}s\n")
            log.flush()

    runtime = round(time.time() - start, 2)

    with open(out_dir / f"{model_id}_{a.run}.json", "w") as f:
        json.dump(dataset, f, indent=4)

    with open(out_dir / f"{model_id}_{a.run}_token_stats.json", "w") as f:
        json.dump({"total_input_tokens": total_in, "total_output_tokens": total_out,
                   "grand_total_tokens": total_in + total_out}, f, indent=4)

    with open(out_dir / f"{model_id}_{a.run}_total_runtime.json", "w") as f:
        json.dump({"total_runtime_seconds": runtime,
                   "total_runtime_minutes": round(runtime / 60, 2),
                   "pure_execution_time_seconds": round(total_pure, 2),
                   "pure_execution_time_minutes": round(total_pure / 60, 2)}, f, indent=4)

    print(f"saved {out_dir}/{model_id}_{a.run}.json  ({len(dataset)} problems)")


if __name__ == "__main__":
    main()
